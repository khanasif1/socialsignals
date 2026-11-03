param location string
param appName string
param storageId string
param vaultId string

resource vnet 'Microsoft.Network/virtualNetworks@2023-11-01' = {
  name: '${appName}-vnet'
  location: location
  properties: {
    addressSpace: { addressPrefixes: ['10.58.0.0/24'] }
    subnets: [
      {
        name: 'application'
        properties: {
          addressPrefix: '10.58.0.0/26'
          delegations: [
            {
              name: 'app-service'
              properties: { serviceName: 'Microsoft.Web/serverFarms' }
            }
          ]
        }
      }
      {
        name: 'private-endpoints'
        properties: {
          addressPrefix: '10.58.0.64/26'
          privateEndpointNetworkPolicies: 'Disabled'
        }
      }
    ]
  }
}

var services = [
  { name: 'blob', id: storageId, zone: 'privatelink.blob.core.windows.net', group: 'blob' }
  { name: 'vault', id: vaultId, zone: 'privatelink.vaultcore.azure.net', group: 'vault' }
]

resource zones 'Microsoft.Network/privateDnsZones@2020-06-01' = [for service in services: {
  name: service.zone
  location: 'global'
}]

resource links 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = [for (service, i) in services: {
  parent: zones[i]
  name: '${appName}-link'
  location: 'global'
  properties: {
    virtualNetwork: { id: vnet.id }
    registrationEnabled: false
  }
}]

resource endpoints 'Microsoft.Network/privateEndpoints@2023-11-01' = [for service in services: {
  name: '${appName}-${service.name}-endpoint'
  location: location
  properties: {
    subnet: { id: vnet.properties.subnets[1].id }
    privateLinkServiceConnections: [
      {
        name: '${service.name}-connection'
        properties: {
          privateLinkServiceId: service.id
          groupIds: [service.group]
        }
      }
    ]
  }
}]

resource groups 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2023-11-01' = [for (service, i) in services: {
  parent: endpoints[i]
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: service.name
        properties: { privateDnsZoneId: zones[i].id }
      }
    ]
  }
}]

output applicationSubnetId string = vnet.properties.subnets[0].id
