#!/bin/sh
set -eu
# One virtual display for all headed browsers (Meet refuses headless Chromium).
Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp >/dev/null 2>&1 &
export DISPLAY=:99
# PulseAudio in user mode: every meeting gets its own null sink (see bot/audio.py).
# The default source is a silent sink monitor, so the bot's microphone never sends sound.
pulseaudio --daemonize=yes --exit-idle-time=-1 --disallow-exit --log-target=stderr
pactl load-module module-null-sink sink_name=silence sink_properties=device.description=silence >/dev/null
pactl set-default-source silence.monitor
exec python -m uvicorn bot.app:app --host 0.0.0.0 --port 8100
