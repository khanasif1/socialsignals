#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for tool in az python curl; do
  command -v "$tool" >/dev/null || { echo "Required tool missing: $tool" >&2; exit 1; }
done
az account show --only-show-errors >/dev/null || { echo "Run az login first." >&2; exit 1; }
if [[ -n "${AZURE_SUBSCRIPTION:-}" ]]; then az account set --subscription "$AZURE_SUBSCRIPTION"; fi
: "${RESOURCE_GROUP:=signal-personal}" "${AZURE_LOCATION:=australiaeast}" "${APP_SERVICE_SKU:=B1}"
: "${APP_NAME:?Set a globally unique APP_NAME}"
: "${STORAGE_ACCOUNT:?Set a globally unique lowercase alphanumeric STORAGE_ACCOUNT}"
: "${SIGNAL_LOGIN_SECRET:?Export SIGNAL_LOGIN_SECRET (32+ characters)}"
: "${SIGNAL_SESSION_SECRET:?Export SIGNAL_SESSION_SECRET (independent 32+ characters)}"
export RESOURCE_GROUP AZURE_LOCATION APP_SERVICE_SKU APP_NAME STORAGE_ACCOUNT
python -c 'import os,re; assert len(os.environ["SIGNAL_LOGIN_SECRET"]) >= 32 and len(os.environ["SIGNAL_SESSION_SECRET"]) >= 32; assert os.environ["SIGNAL_LOGIN_SECRET"] != os.environ["SIGNAL_SESSION_SECRET"]; assert re.fullmatch(r"[a-z0-9]{3,24}",os.environ["STORAGE_ACCOUNT"]), "Storage name must be 3-24 lowercase letters/digits"; assert re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{1,33}[A-Za-z0-9]",os.environ["APP_NAME"]), "App name must be 3-35 letters/digits/hyphens"'
az group create --name "$RESOURCE_GROUP" --location "$AZURE_LOCATION" --only-show-errors --output none
bash "$ROOT/deployment/deploy-azure.sh"
bash "$ROOT/deployment/configure-app.sh"
bash "$ROOT/deployment/deploy-backend.sh"
URL="https://${APP_NAME}.azurewebsites.net"
APP_ID="$(az webapp show --resource-group "$RESOURCE_GROUP" --name "$APP_NAME" --query id --output tsv)"
echo "Waiting for backend and Managed Identity propagation..."
healthy=false
for _ in $(seq 1 40); do
  if curl --silent --fail --max-time 20 "$URL/api/health" | python -c 'import json,sys; x=json.load(sys.stdin); assert x["status"]=="ok" and x["storage"]=="connected"' 2>/dev/null; then
    healthy=true; break
  fi
  # Failed initial Key Vault lookups can be cached even after RBAC propagates.
  if ! az rest --method post --url "https://management.azure.com${APP_ID}/config/configreferences/appsettings/refresh?api-version=2022-03-01" --output none --only-show-errors; then
    echo "Key Vault reference refresh not ready; health verification will retry." >&2
  fi
  sleep 15
done
if [[ "$healthy" != true ]]; then echo "Health check failed. Inspect App Service startup logs and Key Vault/RBAC propagation." >&2; exit 1; fi
printf '\nSIGNAL deployed\nURL: %s\nResource group: %s\nStorage: %s (private)\n' "$URL" "$RESOURCE_GROUP" "$STORAGE_ACCOUNT"
echo "Set EXPO_PUBLIC_API_URL=$URL and EXPO_PUBLIC_DEMO=false for your mobile build."
