#!/usr/bin/env bash
set -euo pipefail
JOB=/home/site/wwwroot/App_Data/jobs/triggered/linkedin-crawler
mkdir -p "$JOB"
cp /opt/signal-webjob/run.sh /opt/signal-webjob/settings.job "$JOB/"
chmod +x "$JOB/run.sh"
cd /opt/signal
exec runuser -u signal -- bash startup.sh
