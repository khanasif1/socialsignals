#!/usr/bin/env bash
set -euo pipefail
: "${AZURE_SUBSCRIPTION:?Set the explicitly approved target subscription ID}"
: "${RESOURCE_GROUP:?Set the existing SIGNAL resource group}"
: "${APP_NAME:?Set the existing SIGNAL App Service name}"
: "${SIGNAL_CONTAINER_IMAGE:?Set a previously built and pushed Linux amd64 image}"
: "${LINKEDIN_USERNAME_SECRET_URI:?Set a Key Vault secret URI, not a username}"
: "${LINKEDIN_PASSWORD_SECRET_URI:?Set a Key Vault secret URI, not a password}"
for uri in "$LINKEDIN_USERNAME_SECRET_URI" "$LINKEDIN_PASSWORD_SECRET_URI"; do
  [[ "$uri" =~ ^https://[a-zA-Z0-9-]+\.vault\.azure\.net/secrets/[a-zA-Z0-9-]+(/[a-fA-F0-9]{32})?/?$ ]] || {
    echo "Expected an Azure Key Vault secret URI." >&2; exit 1;
  }
done
az account set --subscription "$AZURE_SUBSCRIPTION"
KIND="$(az webapp show --resource-group "$RESOURCE_GROUP" --name "$APP_NAME" --query kind --output tsv)"
[[ "$KIND" == *linux* ]] || { echo "A Linux App Service is required." >&2; exit 1; }
if [[ -n "${CONTAINER_REGISTRY_RESOURCE_ID:-}" ]]; then
  REGISTRY_HOST="$(az acr show --ids "$CONTAINER_REGISTRY_RESOURCE_ID" --query loginServer --output tsv)"
  [[ -n "$REGISTRY_HOST" && "$SIGNAL_CONTAINER_IMAGE" == "${REGISTRY_HOST}/"* ]] || {
    echo "The image must belong to the specified Azure Container Registry." >&2; exit 1;
  }
  PRINCIPAL="$(az webapp identity show --resource-group "$RESOURCE_GROUP" --name "$APP_NAME" --query principalId --output tsv)"
  [[ -n "$PRINCIPAL" ]] || { echo "The App Service needs its existing managed identity." >&2; exit 1; }
  ROLE="$(az role assignment list --assignee "$PRINCIPAL" --scope "$CONTAINER_REGISTRY_RESOURCE_ID" --role AcrPull --query '[0].id' --output tsv)"
  if [[ -z "$ROLE" ]]; then
    az role assignment create --assignee-object-id "$PRINCIPAL" --assignee-principal-type ServicePrincipal \
      --role AcrPull --scope "$CONTAINER_REGISTRY_RESOURCE_ID" --only-show-errors --output none
  fi
fi
az webapp config appsettings set --resource-group "$RESOURCE_GROUP" --name "$APP_NAME" --settings \
  WEBJOBS_DISABLE_SCHEDULE=1 SIGNAL_LINKEDIN_CRAWLER_ENABLED=false \
  WEBSITES_PORT=8000 WEBSITES_ENABLE_APP_SERVICE_STORAGE=true SCM_DO_BUILD_DURING_DEPLOYMENT=false \
  "SIGNAL_LINKEDIN_CRAWLER_USERNAME=@Microsoft.KeyVault(SecretUri=$LINKEDIN_USERNAME_SECRET_URI)" \
  "SIGNAL_LINKEDIN_CRAWLER_PASSWORD=@Microsoft.KeyVault(SecretUri=$LINKEDIN_PASSWORD_SECRET_URI)" \
  --only-show-errors --output none
az webapp config set --resource-group "$RESOURCE_GROUP" --name "$APP_NAME" \
  --startup-file '' --always-on true --generic-configurations '{"acrUseManagedIdentityCreds":true}' \
  --only-show-errors --output none
az webapp config container set --resource-group "$RESOURCE_GROUP" --name "$APP_NAME" \
  --container-image-name "$SIGNAL_CONTAINER_IMAGE" --only-show-errors --output none
URL="https://${APP_NAME}.azurewebsites.net"
healthy=false
for _ in $(seq 1 40); do
  if curl --silent --fail --max-time 20 "$URL/api/health" | python -c \
    'import json,sys; x=json.load(sys.stdin); assert x["status"]=="ok" and x["storage"]=="connected" and x.get("worker_image") is True' 2>/dev/null; then
    healthy=true; break
  fi
  sleep 15
done
[[ "$healthy" == true ]] || { echo "Container/Blob health failed; collection remains disabled." >&2; exit 1; }
az webapp config appsettings set --resource-group "$RESOURCE_GROUP" --name "$APP_NAME" --settings \
  SIGNAL_LINKEDIN_CRAWLER_ENABLED=true WEBJOBS_DISABLE_SCHEDULE=0 \
  --only-show-errors --output none
printf 'Container health verified: %s\nDaily collection enabled. Verify WebJob logs and authenticated /api/linkedin/status after its first run.\n' "$URL"
