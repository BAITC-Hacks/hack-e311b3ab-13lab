from fastapi import HTTPException

from app.integrations.browser_capture import BrowserCaptureConnector
from app.integrations.registry import detect_platform


def build_connector(source, meeting_url, platform, settings, meeting_id):
    """Pick the connector for a new live session; returns (connector, platform)."""
    if source == "tab":
        detected = detect_platform(meeting_url) if meeting_url else None
        return BrowserCaptureConnector(platform or detected or "browser"), platform or detected or "browser"
    detected = detect_platform(meeting_url or "")
    if not detected:
        raise HTTPException(422, "Нужна ссылка на Google Meet, Microsoft Teams или Zoom (https)")
    if not (settings.bot_service_url and settings.bot_token):
        raise HTTPException(503, "Бот для подключения к совещаниям не настроен (BOT_SERVICE_URL, BOT_TOKEN)")
    from app.integrations.bot import connector_for

    return connector_for(detected, settings, meeting_id), detected
