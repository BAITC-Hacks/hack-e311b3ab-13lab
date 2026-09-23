FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY scripts ./scripts
COPY seed ./seed
RUN useradd --create-home appuser && mkdir /app/data && chown appuser:appuser /app/data
USER appuser
EXPOSE 8000
# Only the frontend proxy can reach this port; it overwrites X-Forwarded-For with the client address.
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
