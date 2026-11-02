#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
: "${RESOURCE_GROUP:?}" "${APP_NAME:?}"
mkdir -p "$ROOT/output"
python "$ROOT/scripts/package-backend.py" "$ROOT/backend" "$ROOT/output/backend.zip"
az webapp deploy --resource-group "$RESOURCE_GROUP" --name "$APP_NAME" \
  --src-path "$ROOT/output/backend.zip" --type zip --clean true --restart true \
  --timeout 1200000 --only-show-errors --output none
