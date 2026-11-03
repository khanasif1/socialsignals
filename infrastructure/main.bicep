targetScope = 'resourceGroup'

param location string = 'australiaeast'
@minLength(3)
@maxLength(35)
param appName string
@minLength(3)
@maxLength(24)
param storageAccountName string
param sku string = 'B1'
@secure()
param loginSecret string
@secure()
param sessionSecret string
@secure()
param aiApiKey string = ''
@secure()
param linkedinClientSecret string = ''
param aiProvider string = 'none'
param openaiModel string = 'gpt-4o-mini'
param azureOpenaiEndpoint string = ''
param azureOpenaiDeployment string = ''
param azureOpenaiApiVersion string = '2024-10-21'
param linkedinClientId string = ''
param corsOrigins array = []
param containerImage string = ''
param linkedinCrawlerEnabled bool = false
param linkedinCrawlerUsernameSecretUri string = ''
param linkedinCrawlerPasswordSecretUri string = ''

var vaultName = 'sig-${uniqueString(resourceGroup().id, appName)}'

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageAccountName
  location: location
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
  }
}
resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
}
resource container 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'signal-data'
  properties: { publicAccess: 'None' }
}
resource plan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: '${appName}-plan'
  location: location
  kind: 'linux'
  sku: { name: sku }
  properties: { reserved: true }
}
resource vault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: vaultName
  location: location
  properties: {
    tenantId: tenant().tenantId
    sku: { family: 'A', name: 'standard' }
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    enablePurgeProtection: true
    accessPolicies: []
  }
}
resource login 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: vault
  name: 'signal-login'
  properties: { value: loginSecret }
}
resource session 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: vault
  name: 'signal-session'
  properties: { value: sessionSecret }
}
resource aiKey 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = if (!empty(aiApiKey)) {
  parent: vault
  name: 'signal-ai'
  properties: { value: aiApiKey }
}
resource linkedinKey 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = if (!empty(linkedinClientSecret)) {
  parent: vault
  name: 'signal-linkedin'
  properties: { value: linkedinClientSecret }
}
resource web 'Microsoft.Web/sites@2023-12-01' = {
  name: appName
  location: location
  kind: empty(containerImage) ? 'app,linux' : 'app,linux,container'
  identity: { type: 'SystemAssigned' }
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: empty(containerImage) ? 'PYTHON|3.12' : 'DOCKER|${containerImage}'
      appCommandLine: empty(containerImage) ? 'bash startup.sh' : ''
      acrUseManagedIdentityCreds: !empty(containerImage)
      alwaysOn: true
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      scmMinTlsVersion: '1.2'
      http20Enabled: true
      appSettings: [
        { name: 'SCM_DO_BUILD_DURING_DEPLOYMENT', value: empty(containerImage) ? 'true' : 'false' }
        { name: 'WEBSITES_PORT', value: '8000' }
        { name: 'WEBSITES_ENABLE_APP_SERVICE_STORAGE', value: 'true' }
        { name: 'SIGNAL_LINKEDIN_CRAWLER_ENABLED', value: linkedinCrawlerEnabled ? 'true' : 'false' }
        { name: 'SIGNAL_LINKEDIN_CRAWLER_USERNAME', value: empty(linkedinCrawlerUsernameSecretUri) ? '' : '@Microsoft.KeyVault(SecretUri=${linkedinCrawlerUsernameSecretUri})' }
        { name: 'SIGNAL_LINKEDIN_CRAWLER_PASSWORD', value: empty(linkedinCrawlerPasswordSecretUri) ? '' : '@Microsoft.KeyVault(SecretUri=${linkedinCrawlerPasswordSecretUri})' }
        { name: 'WEBJOBS_DISABLE_SCHEDULE', value: linkedinCrawlerEnabled ? '0' : '1' }
        { name: 'SIGNAL_ENV', value: 'production' }
        { name: 'SIGNAL_STORAGE', value: 'azure' }
        { name: 'SIGNAL_STORAGE_ACCOUNT', value: storage.name }
        { name: 'SIGNAL_STORAGE_CONTAINER', value: container.name }
        { name: 'SIGNAL_LOGIN_SECRET', value: '@Microsoft.KeyVault(SecretUri=${vault.properties.vaultUri}secrets/${login.name}/)' }
        { name: 'SIGNAL_SESSION_SECRET', value: '@Microsoft.KeyVault(SecretUri=${vault.properties.vaultUri}secrets/${session.name}/)' }
        { name: 'SIGNAL_AI_PROVIDER', value: aiProvider }
        { name: 'SIGNAL_OPENAI_MODEL', value: openaiModel }
        { name: 'SIGNAL_OPENAI_API_KEY', value: !empty(aiApiKey) && aiProvider == 'openai' ? '@Microsoft.KeyVault(SecretUri=${vault.properties.vaultUri}secrets/signal-ai/)' : '' }
        { name: 'SIGNAL_AZURE_OPENAI_API_KEY', value: !empty(aiApiKey) && aiProvider == 'azure' ? '@Microsoft.KeyVault(SecretUri=${vault.properties.vaultUri}secrets/signal-ai/)' : '' }
        { name: 'SIGNAL_AZURE_OPENAI_ENDPOINT', value: azureOpenaiEndpoint }
        { name: 'SIGNAL_AZURE_OPENAI_DEPLOYMENT', value: azureOpenaiDeployment }
        { name: 'SIGNAL_AZURE_OPENAI_API_VERSION', value: azureOpenaiApiVersion }
        { name: 'SIGNAL_LINKEDIN_CLIENT_ID', value: linkedinClientId }
        { name: 'SIGNAL_LINKEDIN_CLIENT_SECRET', value: !empty(linkedinClientSecret) ? '@Microsoft.KeyVault(SecretUri=${vault.properties.vaultUri}secrets/signal-linkedin/)' : '' }
        { name: 'SIGNAL_LINKEDIN_REDIRECT_URI', value: 'https://${appName}.azurewebsites.net/api/linkedin/callback' }
        { name: 'SIGNAL_CORS_ORIGINS', value: string(corsOrigins) }
        { name: 'SIGNAL_SCHEDULER_ENABLED', value: 'true' }
      ]
    }
  }
}
resource blobRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(container.id, web.id, 'blob-contributor')
  scope: container
  properties: {
    principalId: web.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
  }
}
resource vaultRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(vault.id, web.id, 'secrets-user')
  scope: vault
  properties: {
    principalId: web.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
  }
}
output applicationUrl string = 'https://${web.properties.defaultHostName}'
output webAppName string = web.name
output storageName string = storage.name
output keyVaultName string = vault.name
output managedIdentity string = web.identity.principalId
