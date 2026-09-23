"""Connectors for meeting platforms, backed by the meeting-bot service.

The bot joins the platform's web client as a participant and streams audio and events
to `/internal/bot/{meeting_id}` (see app/routes/bot.py); these classes start and stop
it. Swapping a guest bot for an official platform API only changes this layer.
"""

import httpx

from app.integrations.base import MeetingConnector
from app.integrations.events import ConnectorStatus


class BotConnector(MeetingConnector):
    kind = "bot"

    def __init__(self, settings, meeting_id):
        super().__init__()
        self.settings = settings
        self.meeting_id = meeting_id
        self._left = False

    def _headers(self):
        return {"Authorization": f"Bearer {self.settings.bot_token}"}

    async def join(self, meeting_url: str) -> None:
        payload = {
            "session_id": self.meeting_id,
            "platform": self.platform,
            "meeting_url": meeting_url,
            "bot_name": self.settings.bot_name,
            "callback_url": f"{self.settings.bot_callback_base}/internal/bot/{self.meeting_id}",
        }
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
                response = await client.post(f"{self.settings.bot_service_url}/sessions", json=payload, headers=self._headers())
        except httpx.HTTPError as error:
            raise RuntimeError(f"Сервис бота недоступен ({type(error).__name__})") from None
        if response.status_code == 409 and "Google account" in response.text:
            raise RuntimeError("Аккаунт Google для бота не подключён: выполните вход (docs/TEAM_SETUP.md)")
        if response.status_code == 429:
            raise RuntimeError("Бот занят другими встречами, повторите позже")
        if response.is_error:
            raise RuntimeError(f"Сервис бота ответил HTTP {response.status_code}")

    async def leave(self) -> None:
        if self._left:
            return
        self._left = True
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
                await client.delete(f"{self.settings.bot_service_url}/sessions/{self.meeting_id}", headers=self._headers())
        except httpx.HTTPError:
            pass
        self.close_streams()

    def bot_disconnected(self):
        """The bot's socket closed: end the session unless it already ended."""
        self.close_streams(ConnectorStatus("ended", "Бот вышел из совещания"))


class GoogleMeetConnector(BotConnector):
    platform = "google_meet"


class TeamsConnector(BotConnector):
    platform = "teams"


class ZoomConnector(BotConnector):
    platform = "zoom"


CONNECTORS = {connector.platform: connector for connector in (GoogleMeetConnector, TeamsConnector, ZoomConnector)}


def connector_for(platform, settings, meeting_id):
    return CONNECTORS[platform](settings, meeting_id)
