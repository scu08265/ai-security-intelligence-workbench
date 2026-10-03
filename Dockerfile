FROM python:3.12-slim

ARG APP_VERSION=0.2.3
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=10 \
    INTEL_JSON_LOGS=1 \
    APP_VERSION=${APP_VERSION}

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN python -m pip install --disable-pip-version-check -r requirements.txt

COPY app ./app
COPY docs ./docs
COPY evaluation ./evaluation
COPY research ./research
COPY scripts ./scripts
COPY tools ./tools
COPY README.md ./
COPY VERSION ./

RUN mkdir -p /app/data /app/artifacts /app/reports

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3).read()"

CMD ["python", "-m", "uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000"]
