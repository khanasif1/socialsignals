#!/usr/bin/env bash
set -euo pipefail
: "${RESOURCE_GROUP:?}" "${APP_NAME:?}"
# Bicep owns all application settings and identity-scoped RBAC assignments.
STARTUP='bash startup.sh'
if [[ -n "${SIGNAL_CONTAINER_IMAGE:-}" ]]; then STARTUP=''; fi
az webapp config set --resource-group "$RESOURCE_GROUP" --name "$APP_NAME" \
  --startup-file "$STARTUP" --always-on true --ftps-state Disabled \
  --min-tls-version 1.2 --only-show-errors --output none
