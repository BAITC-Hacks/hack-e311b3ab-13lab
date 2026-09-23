FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Silero VAD for live sessions (about 2 MB, CPU only), pinned by hash.
RUN mkdir -p /app/models && python -c "import hashlib, urllib.request; path = '/app/models/silero_vad.onnx'; urllib.request.urlretrieve('https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/silero_vad.onnx', path); digest = hashlib.sha256(open(path, 'rb').read()).hexdigest(); assert digest == '9e2449e1087496d8d4caba907f23e0bd3f78d91fa552479bb9c23ac09cbb1fd6', digest"
ENV VAD_MODEL_PATH=/app/models/silero_vad.onnx
COPY app ./app
COPY scripts ./scripts
COPY seed ./seed
RUN useradd --create-home appuser && mkdir /app/data && chown appuser:appuser /app/data
USER appuser
EXPOSE 8000
# Only the frontend proxy can reach this port; it overwrites X-Forwarded-For with the client address.
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
