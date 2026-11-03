#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
: "${RESOURCE_GROUP:?}" "${APP_NAME:?}"
RUNTIME="$(az webapp config show --resource-group "$RESOURCE_GROUP" --name "$APP_NAME" --query linuxFxVersion --output tsv)"
[[ "$RUNTIME" != DOCKER\|* ]] || {
  echo "This app uses a container. Rebuild/push its image and use deploy-crawler.sh, not ZIP deployment." >&2; exit 1;
}
mkdir -p "$ROOT/output"
python "$ROOT/scripts/package-backend.py" "$ROOT/backend" "$ROOT/output/backend.zip"
az webapp deploy --resource-group "$RESOURCE_GROUP" --name "$APP_NAME" \
  --src-path "$ROOT/output/backend.zip" --type zip --clean true --restart true \
  --timeout 1200000 --only-show-errors --output none
