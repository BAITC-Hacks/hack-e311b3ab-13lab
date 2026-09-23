from app.integrations.base import MeetingConnector


class BrowserCaptureConnector(MeetingConnector):
    """Audio captured by the secretary's browser from a meeting tab (and microphone).

    Works with any platform open in the browser. The frontend streams PCM16 over the
    `/api/live/{id}/audio` WebSocket; there is no platform roster, so speaker names come
    from diarization and the meeting's participant list.
    """

    kind = "tab"

    def __init__(self, platform: str = "browser"):
        super().__init__()
        self.platform = platform

    async def join(self, meeting_url: str) -> None:
        return None

    async def leave(self) -> None:
        self.close_streams()
