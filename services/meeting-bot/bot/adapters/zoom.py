import asyncio
import re
from urllib.parse import parse_qs, urlsplit

from bot.adapters.base import Adapter, click_button, fill_first, list_names


class ZoomAdapter(Adapter):
    """Zoom web client (app.zoom.us/wc). The host account must allow joining from a browser."""

    platform = "zoom"
    lobby_text = (r"Please wait, the meeting host will let you in soon", r"Waiting for the host to start", r"Host has joined\. We've let them know you're here")
    denied_text = (r"You have been removed", r"The host has removed you", r"This meeting link is invalid", r"Invalid meeting ID")
    ended_text = (r"This meeting has been ended by host", r"The meeting has ended", r"meeting has been ended")
    leave_button = (r"^Leave$", r"^Leave meeting")

    def web_url(self, url):
        parts = urlsplit(url)
        match = re.search(r"/(?:j|wc(?:/join)?)/(\d+)", parts.path)
        if not match:
            return url
        password = parse_qs(parts.query).get("pwd", [""])[0]
        return f"https://app.zoom.us/wc/join/{match.group(1)}" + (f"?pwd={password}" if password else "")

    async def join(self, page, url, name):
        await page.goto(self.web_url(url), wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5)
        await click_button(page, (r"^Accept Cookies", r"^Accept All Cookies", r"^I Agree", r"^Agree"))
        await click_button(page, (r"Continue without microphone and camera", r"Join from Your Browser", r"join from your browser"))
        await asyncio.sleep(3)
        await fill_first(page, ("#input-for-name", 'input[placeholder="Your Name"]', 'input[aria-label*="name" i]'), name)
        for _attempt in range(10):
            if await click_button(page, (r"^Join$", r"^Join Meeting")):
                return
            await asyncio.sleep(2)
        raise RuntimeError("Не найдена кнопка входа в Zoom: проверьте ссылку и разрешён ли вход из браузера")

    async def after_join(self, page):
        # Without joining computer audio the web client plays nothing.
        for _attempt in range(5):
            if await click_button(page, (r"Join Audio by Computer", r"^Join Audio")):
                break
            await asyncio.sleep(2)
        await click_button(page, (r"^Mute",))
        await click_button(page, (r"^Participants", r"open the participants list"))

    async def participants(self, page):
        return await list_names(page, ".participants-item__display-name")

    async def speaking(self, page):
        names = await list_names(page, ".speaker-active-container__video-frame .video-avatar__avatar-footer, .speaker-bar-container__video-frame--active .video-avatar__avatar-footer")
        return [item["name"] for item in names]

    async def announce(self, page, message):
        if not await click_button(page, (r"^Chat", r"open the chat panel")):
            return False
        await asyncio.sleep(2)
        box = page.locator('[contenteditable="true"], textarea.chat-box__chat-textarea').first
        if not await box.count():
            return False
        await box.fill(message, timeout=3000)
        await box.press("Enter")
        return True
