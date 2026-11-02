#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
: "${GOOGLE_DRIVE_FOLDER_ID:?Set the destination private Google Drive folder ID}"
: "${GOOGLE_DRIVE_ACCESS_TOKEN:?Supply a short-lived OAuth access token securely}"
python "$ROOT/scripts/upload-google-drive.py" "${1:-$ROOT/output/SIGNAL.ipa}"
