targetScope = 'subscription'

param location string = 'australiaeast'
param resourceGroupName string
param appName string
param storageAccountName string
param containerImageTag string
@secure()
param loginSecret string
@secure()
param sessionSecret string
param azureOpenaiModel string = 'gpt-4.1-mini'
param azureOpenaiModelVersion string = '2025-04-14'
param azureOpenaiModelSku string = 'Standard'
@minValue(1)
param azureOpenaiModelCapacity int = 30

resource group 'Microsoft.Resources/resourceGroups@2022-09-01' = {
  name: resourceGroupName
  location: location
  tags: { application: 'SIGNAL' }
}

module application 'main.bicep' = {
  scope: group
  name: '${appName}-infrastructure'
  params: {
    location: location
    appName: appName
    storageAccountName: storageAccountName
    loginSecret: loginSecret
    sessionSecret: sessionSecret
    provisionContainerRegistry: true
    containerImageTag: containerImageTag
    provisionAzureOpenai: true
    provisionPrivateNetworking: true
    azureOpenaiModel: azureOpenaiModel
    azureOpenaiModelVersion: azureOpenaiModelVersion
    azureOpenaiModelSku: azureOpenaiModelSku
    azureOpenaiModelCapacity: azureOpenaiModelCapacity
    linkedinCrawlerEnabled: false
  }
}

output applicationUrl string = application.outputs.applicationUrl
output webAppName string = application.outputs.webAppName
output storageName string = application.outputs.storageName
output keyVaultName string = application.outputs.keyVaultName
output managedIdentity string = application.outputs.managedIdentity
output registryName string = application.outputs.registryName
output containerImage string = application.outputs.workerImage
output openaiEndpoint string = application.outputs.openaiEndpoint
output openaiDeployment string = application.outputs.openaiDeployment
