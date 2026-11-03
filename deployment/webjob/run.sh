#!/usr/bin/env bash
set -euo pipefail
cd /opt/signal
PYTHON="$(command -v python)"
if [[ "$(id -u)" == 0 ]]; then
  exec runuser -u signal -- "$PYTHON" -m app.worker "$@"
fi
exec "$PYTHON" -m app.worker "$@"
