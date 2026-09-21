# Generate local secrets without printing them; preserve existing database contents.
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $repo '.env'
$values = [ordered]@{}
if (Test-Path -LiteralPath $envPath) {
    foreach ($line in Get-Content -LiteralPath $envPath -Encoding UTF8) {
        if ($line -match '^([A-Z_0-9]+)=(.*)$') { $values[$Matches[1]] = $Matches[2] }
    }
}
function New-LocalSecret {
    $bytes = New-Object byte[] 32
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    return ([BitConverter]::ToString($bytes)).Replace('-', '').ToLowerInvariant()
}
foreach ($pair in @(@('POSTGRES_DB','global_news'),@('POSTGRES_USER','global_news'),@('COMPOSE_PROJECT_NAME','global-news'),@('MINIFLUX_ADMIN_USERNAME','admin'))) {
    if (-not $values[$pair[0]]) { $values[$pair[0]] = $pair[1] }
}
foreach ($name in @('POSTGRES_PASSWORD','MINIFLUX_ADMIN_PASSWORD','MINIFLUX_DB_PASSWORD')) {
    if (-not $values[$name] -or $values[$name] -match '^(change_me|GENERATE_LOCAL_SECRET)$') {
        $secret = New-LocalSecret
        if ($name -eq 'POSTGRES_PASSWORD' -and (Test-Path -LiteralPath $envPath)) {
            $dbUser = $values['POSTGRES_USER']
            if ($dbUser -notmatch '^[A-Za-z_][A-Za-z0-9_]*$') { throw 'Unsupported database username' }
            $running = & docker ps --filter "label=com.docker.compose.project=$($values['COMPOSE_PROJECT_NAME'])" --filter 'label=com.docker.compose.service=postgres' --format '{{.ID}}'
            if ($running) {
                "ALTER ROLE $dbUser WITH PASSWORD '$secret';" | & docker exec -i $running psql -U $dbUser -d $values['POSTGRES_DB'] -v ON_ERROR_STOP=1 -q
                if ($LASTEXITCODE -ne 0) { throw 'Database password update failed' }
            }
        }
        $values[$name] = $secret
    }
}
$values['APP_VERSION']='0.2.0'
$values['DATABASE_URL']=''
$values['DATABASE_URL_DOCKER']=''
$values['DATABASE_URL_LOCAL']=''
$values['NEWS_SYNC_INTERVAL_SECONDS']='60'
$values['NEWS_INITIAL_LOOKBACK_DAYS']='5'
$values['NEWS_INITIAL_FULL_REFRESH']='false'
$values['SOURCE_REGISTRY_PATH']='config/sources.yaml'
$values['MINIFLUX_URL']='http://miniflux:8080'
$values['RSSHUB_URL']='http://rsshub:1200'
$lines = foreach ($key in $values.Keys) { "$key=$($values[$key])" }
[IO.File]::WriteAllLines($envPath, $lines, [Text.UTF8Encoding]::new($false))
Write-Output 'Local environment initialized. Secret values were not printed.'