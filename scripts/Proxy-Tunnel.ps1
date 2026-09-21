#requires -Version 7.3
[CmdletBinding()]
param(
    [ValidateSet('Install','Start','Stop','Status')][string]$Action = 'Start',
    [string]$Distro = 'Ubuntu-24.04',
    [ValidateRange(1024,65535)][int]$ProxyPort = 7890
)
$ErrorActionPreference = 'Stop'
$OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::new()
$Root = Split-Path $PSScriptRoot -Parent
$StateDir = Join-Path $env:LOCALAPPDATA 'GlobalNewsNative/News-Proxy'
$SettingsPath = Join-Path $StateDir 'settings.json'
$PidPath = Join-Path $StateDir 'process.json'
$KeyPath = Join-Path $StateDir 'id_ed25519'
$KnownHosts = Join-Path $StateDir 'known_hosts'
$LogPath = Join-Path $StateDir 'ssh.log'
$Ssh = (Get-Command ssh.exe -ErrorAction Stop).Source

function Run-Wsl([string[]]$Arguments) {
    & wsl.exe -d $Distro -u root --exec @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Proxy tunnel WSL operation failed (exit $LASTEXITCODE)." }
}

function Get-ProxyArguments {
    @('-N','-n','-T','-F','none','-a','-i',$KeyPath,
            '-o','BatchMode=yes','-o','IdentitiesOnly=yes',
            '-o','ExitOnForwardFailure=yes','-o','StrictHostKeyChecking=yes',
            '-o',('UserKnownHostsFile=' + $KnownHosts.Replace('\','/')),
            '-o','GlobalKnownHostsFile=NUL','-o','ConnectTimeout=8',
            '-o','ServerAliveInterval=20','-o','ServerAliveCountMax=3',
            '-E',$LogPath,'-p','12222','-R',"127.0.0.1:17890:127.0.0.1:$ProxyPort",
            'news-proxy@127.0.0.1')
}

function Get-UtcTicks($Value) {
    # ConvertFrom-Json may return a DateTime instead of the original string.
    if ($Value -is [DateTimeOffset]) { return $Value.UtcDateTime.Ticks }
    if ($Value -is [DateTime]) { return $Value.ToUniversalTime().Ticks }
    return [DateTimeOffset]::Parse([string]$Value, [Globalization.CultureInfo]::InvariantCulture).UtcDateTime.Ticks
}

function Save-ProxyProcess([Diagnostics.Process]$Process) {
    @{pid=$Process.Id;started=$Process.StartTime.ToUniversalTime().ToString('o')} |
        ConvertTo-Json | Set-Content -LiteralPath $PidPath -Encoding UTF8
}

function Test-ProxyIdentity($Info) {
    if (-not $Info -or -not [string]::Equals($Info.ExecutablePath, $Ssh, [StringComparison]::OrdinalIgnoreCase)) {
        return $false
    }
    # Match the full project command, not a process name, port or key substring.
    $tokens = @($Ssh) + @(Get-ProxyArguments)
    $parts = foreach ($token in $tokens) {
        $escaped = [regex]::Escape($token)
        if ($token -match '\s') { '"' + $escaped + '"' }
        else { '(?:"' + $escaped + '"|' + $escaped + ')' }
    }
    return [regex]::IsMatch($Info.CommandLine, '^\s*' + ($parts -join '\s+') + '\s*$')
}

function Get-VerifiedProxyProcess([int]$ProcessId) {
    $process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if (-not $process) { return $null }
    if ($process.ProcessName -ne 'ssh') { $process.Dispose(); return $null }
    # Retain the process handle while validating identity and later stopping it.
    $null = $process.Handle
    $info = Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessId" -ErrorAction Stop
    $process.Refresh()
    if ($process.HasExited -or -not (Test-ProxyIdentity $info)) {
        $process.Dispose()
        return $null
    }
    return $process
}

function Get-ProxyProcess {
    if (Test-Path -LiteralPath $PidPath) {
        $state = Get-Content -LiteralPath $PidPath -Raw | ConvertFrom-Json
        $process = Get-VerifiedProxyProcess ([int]$state.pid)
        if ($process) {
            if ($process.StartTime.ToUniversalTime().Ticks -eq (Get-UtcTicks $state.started)) { return $process }
            $process.Dispose()
        }
    }
    # Recover stale ownership only from an exact project fingerprint.
    $candidates = @(Get-CimInstance Win32_Process -Filter "Name='ssh.exe'" -ErrorAction Stop |
        Where-Object { Test-ProxyIdentity $_ })
    if ($candidates.Count -gt 1) { throw 'Multiple matching News SSH clients exist. No process was stopped or adopted.' }
    if ($candidates.Count -eq 1) {
        $process = Get-VerifiedProxyProcess ([int]$candidates[0].ProcessId)
        if ($process) { Save-ProxyProcess $process; return $process }
    }
    return $null
}

function Assert-NoUnownedForward {
    & wsl.exe -d $Distro -u root --exec python3 "$LinuxRoot/scripts/native/proxy_tunnel.py" check
    if ($LASTEXITCODE -eq 0) {
        throw 'The forwarding port is occupied without a verified News SSH owner. Refusing to start or stop it.'
    }
    if ($LASTEXITCODE -ne 1) { throw "Cannot determine forwarding ownership (exit $LASTEXITCODE)." }
}

function Start-Proxy {
    Run-Wsl @('systemctl','start','news-proxy-sshd.service')
    $process = Get-ProxyProcess
    $created = $false
    try {
        if (-not $process) {
            Assert-NoUnownedForward
            $listener = [Net.Sockets.TcpClient]::new()
            try {
                if (-not $listener.ConnectAsync('127.0.0.1', $ProxyPort).Wait(3000)) {
                    throw 'The existing Windows loopback proxy is not available.'
                }
            } finally { $listener.Dispose() }
            $start = [Diagnostics.ProcessStartInfo]::new()
            $start.FileName = $Ssh
            $start.UseShellExecute = $false
            $start.CreateNoWindow = $true
            foreach($argument in (Get-ProxyArguments)) { $start.ArgumentList.Add($argument) }
            $process = [Diagnostics.Process]::Start($start)
            $created = $true
        }
        for($attempt=0; $attempt -lt 12; $attempt++) {
            $process.Refresh()
            if ($process.HasExited) { throw "SSH forwarding exited. See $LogPath" }
            & wsl.exe -d $Distro -u root --exec python3 "$LinuxRoot/scripts/native/proxy_tunnel.py" check
            $forwardStatus = $LASTEXITCODE
            if ($forwardStatus -notin @(0,1)) { throw "Cannot check SSH forwarding (exit $forwardStatus)." }
            if ($forwardStatus -eq 0) {
                if ($process.WaitForExit(300)) { throw "SSH forwarding exited during startup. See $LogPath" }
                Save-ProxyProcess $process
                Write-Host "Loopback proxy tunnel is ready (PID $($process.Id))."
                return
            }
            Start-Sleep -Milliseconds 500
        }
        throw "SSH forwarding did not become ready. See $LogPath"
    } catch {
        if ($created -and $process -and -not $process.HasExited) {
            $process.Kill()
            $null = $process.WaitForExit(5000)
        }
        throw
    }
}

if(Test-Path -LiteralPath $SettingsPath) {
    $settings = Get-Content -LiteralPath $SettingsPath -Raw | ConvertFrom-Json
    if($settings.project -ne $Root -or $settings.distro -ne $Distro) {
        throw 'This proxy tunnel belongs to another checkout or distribution.'
    }
    $ProxyPort = [int]$settings.proxy_port
} elseif($Action -ne 'Install') {
    throw 'Install the optional proxy tunnel before using it.'
}
$pathOutput = & wsl.exe -d $Distro --exec wslpath -a $Root
if($LASTEXITCODE -ne 0 -or -not $pathOutput) { throw 'Cannot resolve the WSL project path.' }
$LinuxRoot = ($pathOutput -join "`n").Trim()

if ($Action -eq 'Install') { New-Item -ItemType Directory -Path $StateDir -Force | Out-Null }
# A released file handle leaves no stale lock owner after a PowerShell exit.
$lifecycleLock = [IO.File]::Open((Join-Path $StateDir 'lifecycle.lock'), [IO.FileMode]::OpenOrCreate,
    [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
try {
switch($Action) {
    'Install' {
        New-Item -ItemType Directory -Path $StateDir -Force | Out-Null
        if(-not (Test-Path -LiteralPath $KeyPath)) {
            $keygen = [Diagnostics.ProcessStartInfo]::new()
            $keygen.FileName = (Get-Command ssh-keygen.exe).Source
            $keygen.UseShellExecute = $false
            $keygen.CreateNoWindow = $true
            foreach($argument in @('-q','-t','ed25519','-N','','-f',$KeyPath,'-C','global-news-native')) {
                $keygen.ArgumentList.Add($argument)
            }
            $child = [Diagnostics.Process]::Start($keygen)
            $child.WaitForExit()
            if($child.ExitCode -ne 0) { throw 'Unable to create the dedicated tunnel key.' }
        }
        $sid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
        & icacls.exe $KeyPath /inheritance:r /grant:r "*${sid}:(F)" '*S-1-5-18:(F)' | Out-Null
        if($LASTEXITCODE -ne 0) { throw 'Unable to restrict the private key ACL.' }
        $publicKey = (Get-Content -LiteralPath "$KeyPath.pub" -Raw).Trim()
        $request = @{project=$LinuxRoot;public_key=$publicKey} | ConvertTo-Json -Compress
        $setupOutput = $request | & wsl.exe -d $Distro -u root --exec python3 "$LinuxRoot/scripts/native/proxy_tunnel.py" configure
        if($LASTEXITCODE -ne 0) { throw 'Unable to configure the dedicated SSH endpoint.' }
        $setup = ($setupOutput -join "`n") | ConvertFrom-Json
        "[127.0.0.1]:12222 $($setup.host_key)" | Set-Content -LiteralPath $KnownHosts -Encoding ASCII
        @{project=$Root;distro=$Distro;proxy_port=$ProxyPort} | ConvertTo-Json |
            Set-Content -LiteralPath $SettingsPath -Encoding UTF8
        Start-Proxy
        Run-Wsl @('python3',"$LinuxRoot/scripts/native/proxy_tunnel.py",'enable')
        Write-Host 'Miniflux now uses the existing Windows proxy through a loopback-only tunnel.'
    }
    'Start' { Start-Proxy }
    'Stop' {
        $process = Get-ProxyProcess
        if($process) {
            $process.Kill()
            if (-not $process.WaitForExit(10000)) { throw 'The verified News SSH client did not exit.' }
        } else { Assert-NoUnownedForward }
        Run-Wsl @('systemctl','stop','news-proxy-sshd.service')
        if (Test-Path -LiteralPath $PidPath) { Remove-Item -LiteralPath $PidPath }
    }
    'Status' {
        $process = Get-ProxyProcess
        if(-not $process) { throw 'The managed SSH tunnel is not running. Use Native.ps1 -Action Start.' }
        Run-Wsl @('python3',"$LinuxRoot/scripts/native/proxy_tunnel.py",'check')
        $process.Refresh()
        if ($process.HasExited) { throw 'The verified SSH client exited during the status check.' }
        Write-Host "Managed SSH process and loopback forwarding are active (PID $($process.Id))."
    }
}
} finally { $lifecycleLock.Dispose() }
