#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PARAMS="$(mktemp)"
trap 'rm -f "$PARAMS"' EXIT
chmod 600 "$PARAMS"
python - "$PARAMS" <<'PY'
import json, os, sys
env = os.environ
values = {
    "appName": env["APP_NAME"], "storageAccountName": env["STORAGE_ACCOUNT"],
    "location": env.get("AZURE_LOCATION", "australiaeast"), "sku": env.get("APP_SERVICE_SKU", "B1"),
    "loginSecret": env["SIGNAL_LOGIN_SECRET"], "sessionSecret": env["SIGNAL_SESSION_SECRET"],
    "aiProvider": env.get("SIGNAL_AI_PROVIDER", "none"),
    "aiApiKey": env.get("SIGNAL_AZURE_OPENAI_API_KEY") or env.get("SIGNAL_OPENAI_API_KEY", ""),
    "openaiModel": env.get("SIGNAL_OPENAI_MODEL", "gpt-4o-mini"),
    "azureOpenaiEndpoint": env.get("SIGNAL_AZURE_OPENAI_ENDPOINT", ""),
    "azureOpenaiDeployment": env.get("SIGNAL_AZURE_OPENAI_DEPLOYMENT", ""),
    "azureOpenaiApiVersion": env.get("SIGNAL_AZURE_OPENAI_API_VERSION", "2024-10-21"),
    "linkedinClientId": env.get("SIGNAL_LINKEDIN_CLIENT_ID", ""),
    "linkedinClientSecret": env.get("SIGNAL_LINKEDIN_CLIENT_SECRET", ""),
    "corsOrigins": json.loads(env.get("SIGNAL_CORS_ORIGINS", "[]")),
    "containerImage": env.get("SIGNAL_CONTAINER_IMAGE", ""),
    "linkedinCrawlerEnabled": env.get("SIGNAL_LINKEDIN_CRAWLER_ENABLED", "false").lower() == "true",
    "linkedinCrawlerUsernameSecretUri": env.get("LINKEDIN_USERNAME_SECRET_URI", ""),
    "linkedinCrawlerPasswordSecretUri": env.get("LINKEDIN_PASSWORD_SECRET_URI", ""),
}
with open(sys.argv[1], "w") as file:
    json.dump({"parameters": {k: {"value": v} for k, v in values.items()}}, file)
PY
az deployment group create --resource-group "$RESOURCE_GROUP" --name signal \
  --template-file "$ROOT/infrastructure/main.bicep" --parameters "@$PARAMS" \
  --only-show-errors --query properties.outputs --output json
