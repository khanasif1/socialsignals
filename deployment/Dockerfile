FROM mcr.microsoft.com/playwright/python:v1.64.1-noble

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    SIGNAL_LOCAL_PATH=/home/signal/.signal-data \
    PORT=8000

WORKDIR /opt/signal
COPY backend/requirements.txt backend/requirements-crawler.txt ./
RUN --mount=type=bind,source=deployment/wheels,target=/wheels \
    if find /wheels -name '*.whl' -print -quit | grep -q .; then \
      python -m pip install --no-cache-dir --no-index --find-links=/wheels -r requirements-crawler.txt; \
    else \
      python -m pip install --no-cache-dir -r requirements-crawler.txt; \
    fi \
    && useradd --create-home --uid 10001 signal \
    && chmod -R a+rX /ms-playwright

COPY backend/app ./app
COPY backend/startup.sh deployment/container-start.sh ./
COPY deployment/webjob /opt/signal-webjob
RUN sed -i 's/\r$//' startup.sh container-start.sh /opt/signal-webjob/run.sh \
    && chmod +x startup.sh container-start.sh /opt/signal-webjob/run.sh \
    && runuser -u signal -- python -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); b = p.chromium.launch(); b.close(); p.stop()"

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=5)"
ENTRYPOINT ["bash", "/opt/signal/container-start.sh"]
