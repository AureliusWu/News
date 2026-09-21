#requires -Version 7.3
[CmdletBinding()]
param([string]$Distro = 'Ubuntu-24.04')

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path $PSScriptRoot -Parent
$Controller = Join-Path $PSScriptRoot 'Proxy-Tunnel.ps1'
$FixtureRoot = Join-Path $ProjectRoot ('artifacts/proxy-fixture-' + [guid]::NewGuid().ToString('N'))
$ReportPath = Join-Path $ProjectRoot 'artifacts/native-proxy-lifecycle-latest.json'
New-Item -ItemType Directory -Path $FixtureRoot -Force | Out-Null
$checks = [Collections.Generic.List[object]]::new()
$failure = $null
$restoreTunnel = $false

function Assert-Case([bool]$Condition, [string]$Name) {
    $checks.Add([ordered]@{name=$Name;pass=$Condition})
    if (-not $Condition) { throw "Proxy lifecycle regression failed: $Name" }
}

try {
    . $Controller -Action Status -Distro $Distro
    $initial = Get-ProxyProcess
    $initialId = $initial.Id
    $stamp = $initial.StartTime.ToUniversalTime()
    $roundTrip = (@{started=$stamp.ToString('o')} | ConvertTo-Json | ConvertFrom-Json).started
    $variants = @($stamp.ToString('o'), $stamp, [DateTimeOffset]$stamp, $roundTrip,
        ([DateTimeOffset]$stamp).ToOffset([TimeSpan]::FromHours(8)))
    $timestampsMatch = $true
    foreach ($value in $variants) { $timestampsMatch = $timestampsMatch -and ((Get-UtcTicks $value) -eq $stamp.Ticks) }
    Assert-Case $timestampsMatch 'utc_timestamp_representations'
    $info = Get-CimInstance Win32_Process -Filter "ProcessId=$initialId"
    Assert-Case (Test-ProxyIdentity $info) 'exact_process_fingerprint'
    $different = [pscustomobject]@{ExecutablePath=$info.ExecutablePath;CommandLine=$info.CommandLine+' extra-argument'}
    Assert-Case (-not (Test-ProxyIdentity $different)) 'extra_arguments_rejected'
    $different.CommandLine = $info.CommandLine.Replace($KeyPath, $KeyPath+'-unrelated')
    Assert-Case (-not (Test-ProxyIdentity $different)) 'foreign_key_rejected'

    # Inject metadata only in a fixture, never in the real process.json.
    $realPidPath = $PidPath
    $realKeyPath = $KeyPath
    try {
        $PidPath = Join-Path $FixtureRoot 'process.json'
        @{pid=$PID;started=[DateTime]::UtcNow.ToString('o')} |
            ConvertTo-Json | Set-Content -LiteralPath $PidPath -Encoding utf8
        $recovered = Get-ProxyProcess
        Assert-Case ($recovered -and $recovered.Id -eq $initialId) 'stale_fixture_pid_reconciled'
        $KeyPath = Join-Path $FixtureRoot 'unrelated_id_ed25519'
        $refused = $false
        try { Start-Proxy }
        catch {
            if ($_.Exception.Message -like '*occupied without a verified News SSH owner*') { $refused = $true }
            else { throw }
        }
        Assert-Case $refused 'unowned_forward_start_refused'
        $initial.Refresh()
        Assert-Case (-not $initial.HasExited) 'existing_process_preserved'
    } finally {
        $PidPath = $realPidPath
        $KeyPath = $realKeyPath
    }

    $heldLock = [IO.File]::Open((Join-Path $StateDir 'lifecycle.lock'),
        [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
    $lockRejected = $false
    try {
        try { & $Controller -Action Status -Distro $Distro }
        catch {
            if ($_.Exception.GetBaseException() -is [IO.IOException]) { $lockRejected = $true }
            else { throw }
        }
    } finally { $heldLock.Dispose() }
    Assert-Case $lockRejected 'concurrent_lifecycle_refused'

    $restoreTunnel = $true
    & $Controller -Action Stop -Distro $Distro
    $initial.Refresh()
    Assert-Case $initial.HasExited 'stop_exits_owned_process'
    & wsl.exe -d $Distro -u root --exec python3 "$LinuxRoot/scripts/native/proxy_tunnel.py" check
    Assert-Case ($LASTEXITCODE -eq 1) 'stop_closes_forward'
    $stoppedStatus = $false
    try { & $Controller -Action Status -Distro $Distro }
    catch {
        if ($_.Exception.Message -like '*managed SSH tunnel is not running*') { $stoppedStatus = $true }
        else { throw }
    }
    Assert-Case $stoppedStatus 'stopped_status_reports_absence'
    & $Controller -Action Stop -Distro $Distro
    Assert-Case $true 'repeated_stop_safe'
    & $Controller -Action Start -Distro $Distro
    $restarted = Get-ProxyProcess
    Assert-Case ($restarted -and $restarted.Id -ne $initialId) 'start_creates_new_owned_process'
    $restartId = $restarted.Id
    & $Controller -Action Start -Distro $Distro
    Assert-Case ((Get-ProxyProcess).Id -eq $restartId) 'repeated_start_reuses_process'
    & $Controller -Action Status -Distro $Distro
    Assert-Case $true 'running_status_passes'
    $http = & wsl.exe -d $Distro -u root --exec curl --proxy http://127.0.0.1:17890 --max-time 20 --fail --silent --show-error --output /dev/null --write-out '%{http_code}' https://feeds.bbci.co.uk/news/world/rss.xml
    Assert-Case ($LASTEXITCODE -eq 0 -and ($http -join '').Trim() -eq '200') 'rss_http_200_after_restart'
    $restoreTunnel = $false
} catch {
    $failure = $_
} finally {
    if ($restoreTunnel) {
        try { & $Controller -Action Start -Distro $Distro }
        catch { $checks.Add([ordered]@{name='restore_tunnel';pass=$false}); if (-not $failure) { $failure = $_ } }
    }
    [ordered]@{
        checked_at=(Get-Date).ToString('o')
        powershell=$PSVersionTable.PSVersion.ToString()
        fixture_metadata_only=$true
        initial_pid=$initialId
        restarted_pid=$restartId
        checks=$checks.ToArray()
        pass=($null -eq $failure)
        failure=$(if ($failure) {$failure.Exception.Message} else {$null})
    } | ConvertTo-Json -Depth 6 | Tee-Object -FilePath $ReportPath
}
if ($failure) { throw $failure }
