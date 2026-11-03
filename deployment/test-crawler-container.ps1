param(
    [string]$Image = 'signal-crawler:local-check',
    [string]$ReaderUrl = 'http://host.docker.internal:8081'
)

$ErrorActionPreference = 'Stop'
$docker = (Get-Command docker -ErrorAction Stop).Source
$root = Split-Path $PSScriptRoot -Parent
$suffix = [Guid]::NewGuid().ToString('N').Substring(0, 12)
$storageName = "signal-storage-test-$suffix"
$workerName = "signal-worker-test-$suffix"
$apiName = "signal-api-test-$suffix"
$started = @()
$variables = @(
    'AZURITE_ACCOUNTS', 'SIGNAL_TEST_AZURITE_CONNECTION_STRING',
    'SIGNAL_TEST_READER_URL', 'SIGNAL_LOGIN_SECRET', 'SIGNAL_SESSION_SECRET'
)
$original = @{}
foreach ($name in $variables) { $original[$name] = [Environment]::GetEnvironmentVariable($name) }

try {
    $key = [Convert]::ToBase64String([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
    $env:AZURITE_ACCOUNTS = "signaltest:$key"
    $env:SIGNAL_LOGIN_SECRET = 'container-test-login-passphrase-with-32-characters'
    $env:SIGNAL_SESSION_SECRET = 'independent-container-signing-secret-with-32-characters'
    & $docker run --detach --rm --name $storageName --publish 127.0.0.1::10000 --env AZURITE_ACCOUNTS `
        mcr.microsoft.com/azure-storage/azurite azurite-blob --blobHost 0.0.0.0 --skipApiVersionCheck
    if ($LASTEXITCODE -ne 0) { throw 'Azurite could not start' }
    $started += $storageName
    $binding = & $docker port $storageName 10000/tcp
    $port = $binding.Split(':')[-1]
    $ready = $false
    for ($i = 0; $i -lt 20; $i++) {
        & curl.exe --silent --output NUL --max-time 2 "http://127.0.0.1:$port/signaltest"
        if ($LASTEXITCODE -eq 0) { $ready = $true; break }
        Start-Sleep -Seconds 1
    }
    if (-not $ready) { throw 'Azurite did not become responsive' }
    $env:SIGNAL_TEST_AZURITE_CONNECTION_STRING = "DefaultEndpointsProtocol=http;AccountName=signaltest;AccountKey=$key;BlobEndpoint=http://host.docker.internal:$port/signaltest;"
    $env:SIGNAL_TEST_READER_URL = $ReaderUrl
    New-Item -ItemType Directory -Force -Path "$root\frontend\test-results" | Out-Null
    & $docker run --rm --name $workerName --user 10001 `
        --env SIGNAL_TEST_AZURITE_CONNECTION_STRING --env SIGNAL_TEST_READER_URL `
        --env SIGNAL_LOGIN_SECRET --env SIGNAL_SESSION_SECRET `
        --mount "type=bind,source=$root\tests,target=/opt/signal/tests,readonly" `
        --mount "type=bind,source=$root\deployment,target=/opt/signal/deployment,readonly" `
        --mount "type=bind,source=$root\frontend\test-results,target=/opt/signal/frontend/test-results" `
        --entrypoint python $Image -m pytest tests/backend -q --basetemp=/tmp/signal-pytest -p no:cacheprovider
    if ($LASTEXITCODE -ne 0) { throw 'Container Blob-to-reader integration failed' }

    & $docker run --detach --name $apiName --publish 127.0.0.1::8000 `
        --env SIGNAL_LOGIN_SECRET --env SIGNAL_SESSION_SECRET $Image
    if ($LASTEXITCODE -ne 0) { throw 'API container could not start' }
    $started += $apiName
    $binding = & $docker port $apiName 8000/tcp
    if (-not $binding) {
        & $docker logs $apiName
        throw 'API port was not published; check the startup log above'
    }
    $port = $binding.Split(':')[-1]
    $ready = $false
    for ($i = 0; $i -lt 30; $i++) {
        $response = & curl.exe --silent --fail --max-time 2 "http://127.0.0.1:$port/api/health"
        if ($LASTEXITCODE -eq 0) {
            $health = $response | ConvertFrom-Json
            if ($health.status -eq 'ok' -and $health.storage -eq 'connected' -and $health.worker_image) {
                $ready = $true
                break
            }
        }
        Start-Sleep -Seconds 1
    }
    if (-not $ready) {
        & $docker logs $apiName
        throw 'Container startup/health did not succeed'
    }
    & $docker exec $apiName bash /home/site/wwwroot/App_Data/jobs/triggered/linkedin-crawler/run.sh
    if ($LASTEXITCODE -ne 0) { throw 'Published WebJob entry point failed' }
    & $docker exec $apiName pgrep -u 10001 -f gunicorn
    if ($LASTEXITCODE -ne 0) { throw 'API is not running as the non-root runtime user' }
    Write-Output 'Container startup, WebJob entry point and Blob-to-reader integration passed.'
}
finally {
    try {
        foreach ($name in $started) { & $docker rm --force $name | Out-Null }
        $remaining = & $docker container ls --all --filter "name=^/$workerName$" --format '{{.ID}}'
        if ($remaining) { & $docker rm --force $remaining | Out-Null }
    }
    finally {
        foreach ($name in $variables) { [Environment]::SetEnvironmentVariable($name, $original[$name]) }
    }
}
