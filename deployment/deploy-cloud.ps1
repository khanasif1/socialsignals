param(
    [Parameter(Mandatory)][ValidateSet('Prepare', 'Validate', 'Deploy')][string]$Action,
    [Parameter(Mandatory)][guid]$SubscriptionId,
    [Parameter(Mandatory)][string]$ResourceGroup,
    [Parameter(Mandatory)][string]$AppName,
    [Parameter(Mandatory)][string]$StorageAccount,
    [string]$Location = 'australiaeast',
    [string]$ImageTag = 'latest'
)

$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$private = Join-Path $root ".azure\private\$SubscriptionId"
$parametersPath = Join-Path $private "$AppName.parameters.json"
$template = Join-Path $root 'infrastructure\bootstrap.bicep'
$deploymentName = "$AppName-bootstrap"

function Assert-AzureCommand {
    if ($LASTEXITCODE -ne 0) { throw "Azure CLI failed with exit code $LASTEXITCODE." }
}

New-Item -ItemType Directory -Path $private -Force | Out-Null
if ($IsWindows) {
    $sid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User
    $acl = Get-Acl -LiteralPath $private
    $acl.SetAccessRuleProtection($true, $false)
    foreach ($rule in @($acl.Access)) {
        $acl.RemoveAccessRuleSpecific($rule)
    }
    $acl.SetAccessRule([System.Security.AccessControl.FileSystemAccessRule]::new(
        $sid, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow'))
    [System.IO.FileSystemAclExtensions]::SetAccessControl([System.IO.DirectoryInfo]::new($private), $acl)
} else {
    & chmod 700 $private
    if ($LASTEXITCODE -ne 0) { throw 'Could not protect the deployment directory.' }
}

if (Test-Path -LiteralPath $parametersPath) {
    $document = Get-Content -LiteralPath $parametersPath -Raw | ConvertFrom-Json -AsHashtable
    foreach ($item in @{
        resourceGroupName = $ResourceGroup; appName = $AppName
        storageAccountName = $StorageAccount; location = $Location
    }.GetEnumerator()) {
        if ($document.parameters[$item.Key].value -ne $item.Value) {
            throw "Existing deployment state differs for $($item.Key). Use the original target."
        }
    }
    $document.parameters.containerImageTag.value = $ImageTag
} else {
    $document = @{
        '$schema' = 'https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#'
        contentVersion = '1.0.0.0'
        parameters = @{
            resourceGroupName = @{ value = $ResourceGroup }
            appName = @{ value = $AppName }
            storageAccountName = @{ value = $StorageAccount }
            location = @{ value = $Location }
            containerImageTag = @{ value = $ImageTag }
            loginSecret = @{ value = [Convert]::ToBase64String([Security.Cryptography.RandomNumberGenerator]::GetBytes(48)) }
            sessionSecret = @{ value = [Convert]::ToBase64String([Security.Cryptography.RandomNumberGenerator]::GetBytes(48)) }
        }
    }
}
$document | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $parametersPath -Encoding utf8NoBOM
if (-not $IsWindows) { & chmod 600 $parametersPath }

if ($Action -eq 'Prepare') {
    Write-Output 'Protected deployment parameters prepared. No secrets displayed and no Azure resources changed.'
    return
}

if ($Action -eq 'Validate') {
    az deployment sub validate --subscription $SubscriptionId --location $Location --name $deploymentName `
        --template-file $template --parameters "@$parametersPath" --only-show-errors --output none
    Assert-AzureCommand
    az deployment sub what-if --subscription $SubscriptionId --location $Location --name $deploymentName `
        --template-file $template --parameters "@$parametersPath" --result-format ResourceIdOnly `
        --no-pretty-print --only-show-errors --output json
    Assert-AzureCommand
    return
}

$plan = Get-Content -LiteralPath (Join-Path $root '.azure\deployment-plan.md') -Raw
if ($plan -notmatch '(?m)^Status: Validated\s*$') {
    throw 'Complete azure-validate and record Status: Validated before deploying.'
}
$outputs = az deployment sub create --subscription $SubscriptionId --location $Location --name $deploymentName `
    --template-file $template --parameters "@$parametersPath" --only-show-errors --query properties.outputs --output json
Assert-AzureCommand
$outputs | Set-Content -LiteralPath (Join-Path $private "$AppName.outputs.json") -Encoding utf8NoBOM
$result = $outputs | ConvertFrom-Json

Push-Location $root
try {
    $image = $result.containerImage.value
    docker build --quiet --platform linux/amd64 --tag $image --file 'deployment\Dockerfile' .
    if ($LASTEXITCODE -ne 0) { throw 'Worker container build failed.' }
    az acr login --subscription $SubscriptionId --name $result.registryName.value --only-show-errors
    Assert-AzureCommand
    docker push --quiet $image
    if ($LASTEXITCODE -ne 0) { throw 'Worker image publication failed.' }
} finally {
    Pop-Location
}
az acr repository show --subscription $SubscriptionId --name $result.registryName.value `
    --image "signal-worker:$ImageTag" --only-show-errors --output none
Assert-AzureCommand
az rest --method post --url "https://management.azure.com/subscriptions/$SubscriptionId/resourceGroups/$ResourceGroup/providers/Microsoft.Web/sites/$AppName/config/configreferences/appsettings/refresh?api-version=2023-12-01" `
    --only-show-errors --output none
Assert-AzureCommand
az webapp restart --subscription $SubscriptionId --resource-group $ResourceGroup --name $AppName `
    --only-show-errors --output none
Assert-AzureCommand

$url = $result.applicationUrl.value
$healthy = $false
for ($attempt = 0; $attempt -lt 40; $attempt++) {
    $response = curl.exe --silent --fail --max-time 20 "$url/api/health"
    if ($LASTEXITCODE -eq 0) {
        $health = $response | ConvertFrom-Json
        if ($health.status -eq 'ok' -and $health.storage -eq 'connected' -and $health.worker_image -eq $true) {
            $healthy = $true
            break
        }
    }
    Start-Sleep -Seconds 15
}
if (-not $healthy) { throw 'Container or managed-identity Blob health failed. Collection remains disabled.' }
Write-Output "Container and managed-identity Blob health verified: $url"
Write-Output 'Collection remains disabled until its Key Vault secrets are configured and verified.'
