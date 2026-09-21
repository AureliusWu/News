[CmdletBinding()]
param(
    [ValidateSet('Install','Start','Stop','Restart','Status','Logs','Build','TestBackend','ValidateSources','VerifyPipeline')]
    [string]$Action = 'Start',
    [string]$Distro = 'Ubuntu-24.04'
)
$ErrorActionPreference = 'Stop'
$OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::new()
$Root = Split-Path $PSScriptRoot -Parent
$StatePath = Join-Path $Root 'artifacts/native-keeper.json'
$LinuxRootOutput = & wsl.exe -d $Distro --exec wslpath -a $Root
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace(($LinuxRootOutput -join "`n"))) {
    throw 'Cannot resolve the project path in the selected WSL distribution.'
}
$LinuxRoot = ($LinuxRootOutput -join "`n").Trim()

function Invoke-Native([string]$Command) {
    & wsl.exe -d $Distro -u root -- python3 "$LinuxRoot/scripts/native/manage.py" $Command
    if ($LASTEXITCODE -ne 0) { throw "Native command failed: $Command (exit $LASTEXITCODE)" }
}

function Get-Keeper {
    if (Test-Path -LiteralPath $StatePath) {
        $saved = Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json
        $process = Get-Process -Id $saved.pid -ErrorAction SilentlyContinue
        if ($process -and $process.ProcessName -eq 'wsl' -and $process.StartTime.ToUniversalTime().ToString('o') -eq $saved.started -and $saved.distro -eq $Distro) {
            return $process
        }
    }
    return $null
}

function Start-Keeper {
    if (-not (Get-Keeper)) {
        $process = Start-Process -FilePath 'wsl.exe' -ArgumentList @('-d', $Distro, '--exec', 'sleep', 'infinity') -WindowStyle Hidden -PassThru
        New-Item -ItemType Directory -Path (Split-Path $StatePath -Parent) -Force | Out-Null
        @{ pid = $process.Id; started = $process.StartTime.ToUniversalTime().ToString('o'); distro = $Distro } | ConvertTo-Json | Set-Content -LiteralPath $StatePath -Encoding UTF8
    }
    if (Test-Path -LiteralPath (Join-Path $env:LOCALAPPDATA 'GlobalNewsNative/News-Proxy/settings.json')) {
        & (Join-Path $PSScriptRoot 'Proxy-Tunnel.ps1') -Action Start -Distro $Distro
    }
}

function Build-Frontend {
    $savedApi = $env:VITE_API_BASE_URL
    try {
        $env:VITE_API_BASE_URL = ''
        Push-Location (Join-Path $Root 'frontend')
        try {
            if (-not (Test-Path -LiteralPath 'node_modules')) {
                & npm.cmd ci
                if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
            }
            & npm.cmd run build -- --base=/
            if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed; served files were not changed.' }
        } finally { Pop-Location }
    } finally { $env:VITE_API_BASE_URL = $savedApi }
}

switch ($Action) {
    'Install' {
        Start-Keeper
        & wsl.exe -d $Distro -u root -- bash "$LinuxRoot/scripts/native/install.sh" $LinuxRoot
        if ($LASTEXITCODE -ne 0) { throw 'Native installation stopped. Existing Docker data was not modified.' }
        Build-Frontend
        Invoke-Native 'build'
        Invoke-Native 'start'
        Write-Host 'Native services started. First news fetch may take several minutes.'
        Write-Host 'Website: http://127.0.0.1:8080/'
    }
    'Start' { Start-Keeper; Invoke-Native 'start'; Write-Host 'Website: http://127.0.0.1:8080/' }
    'Restart' { Start-Keeper; Invoke-Native 'restart' }
    'Stop' {
        Invoke-Native 'stop'
        if (Test-Path -LiteralPath (Join-Path $env:LOCALAPPDATA 'GlobalNewsNative/News-Proxy/settings.json')) {
            & (Join-Path $PSScriptRoot 'Proxy-Tunnel.ps1') -Action Stop -Distro $Distro
        }
        $keeper = Get-Keeper
        if ($keeper) { Stop-Process -Id $keeper.Id }
    }
    'Build' { Build-Frontend; Invoke-Native 'build' }
    'Status' { Invoke-Native 'status' }
    'Logs' { Invoke-Native 'logs' }
    'TestBackend' { Invoke-Native 'test-backend' }
    'ValidateSources' { Invoke-Native 'validate-sources' }
    'VerifyPipeline' { Invoke-Native 'verify-pipeline' }
}
