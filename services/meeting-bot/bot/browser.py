"""Chromium launch settings shared by meeting sessions and the login helper."""

import os
import subprocess
import time
from pathlib import Path

SECRETS = Path(os.getenv("BOT_SECRETS_DIR", "/secrets"))
CHROMIUM_ARGS = [
    "--autoplay-policy=no-user-gesture-required",
    "--disable-blink-features=AutomationControlled",
    "--use-fake-ui-for-media-stream",  # auto-answer permission prompts; audio comes from PulseAudio
    "--lang=en-US",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-dev-shm-usage",
]


def storage_state(platform: str) -> str | None:
    path = SECRETS / f"{platform}.json"
    return str(path) if path.is_file() else None


def ensure_display() -> str:
    """Start Xvfb :99 when no display is running (e.g. under `docker compose run`)."""
    display = os.getenv("DISPLAY", ":99")
    socket = Path("/tmp/.X11-unix") / f"X{display.lstrip(':').split('.')[0]}"
    if not socket.exists():
        subprocess.Popen(["Xvfb", display, "-screen", "0", "1920x1080x24", "-nolisten", "tcp"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _wait in range(50):
            if socket.exists():
                break
            time.sleep(0.1)
    return display


async def launch(playwright, sink_name: str | None = None):
    env = {**os.environ, "DISPLAY": ensure_display()}
    if sink_name:
        env["PULSE_SINK"] = sink_name
    return await playwright.chromium.launch(headless=False, args=CHROMIUM_ARGS, env=env)


async def new_context(browser, platform: str):
    return await browser.new_context(
        locale="en-US",
        timezone_id="Asia/Almaty",
        viewport={"width": 1280, "height": 800},
        storage_state=storage_state(platform),
        permissions=["microphone", "camera"],
    )
