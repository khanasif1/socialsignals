#!/usr/bin/env bash
set -euo pipefail
exec gunicorn 'app.main:create_app()' --worker-class uvicorn.workers.UvicornWorker \
  --workers 1 --bind "0.0.0.0:${PORT:-8000}" --timeout 180 --access-logfile /dev/null
