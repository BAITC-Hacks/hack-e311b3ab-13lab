#!/bin/sh
set -eu
cd "$(dirname "$0")"
set -a
. ./service.env
set +a
exec .venv/bin/python -m uvicorn server:app --host 127.0.0.1 --port 18765
