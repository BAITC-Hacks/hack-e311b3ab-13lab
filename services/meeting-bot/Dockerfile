# Chromium with a virtual display and a virtual sound card per meeting.
FROM mcr.microsoft.com/playwright/python:v1.63.0-noble
RUN apt-get update && apt-get install -y --no-install-recommends pulseaudio pulseaudio-utils xvfb fonts-noto-color-emoji && rm -rf /var/lib/apt/lists/*
WORKDIR /bot
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && python -m playwright install chromium
COPY bot ./bot
COPY start.sh .
RUN useradd --create-home botuser && mkdir -p /secrets /debug && chown botuser:botuser /debug
USER botuser
ENV HOME=/home/botuser
EXPOSE 8100
CMD ["sh", "start.sh"]
