FROM python:3.11-slim

WORKDIR /app

# Only minimal system deps — no Firefox/geckodriver, since the scraper
# now talks to EDGAR's JSON API directly. lxml needs libxml2/libxslt
# at build time, but the wheel ships them, so nothing to install here.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY edgar8k.py ./
COPY app.py ./
COPY templates/ ./templates/
COPY static/ ./static/

ENV PYTHONUNBUFFERED=1 \
    EDGAR_OUTPUT_DIR=/data

VOLUME ["/data"]
EXPOSE 5000

CMD ["python", "app.py"]
