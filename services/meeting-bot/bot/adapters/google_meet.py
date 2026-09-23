import asyncio
import contextlib

from playwright.async_api import Error as PlaywrightError

from bot.adapters.base import Adapter, click_button, fill_first, find_button, list_names


class GoogleMeetAdapter(Adapter):
    """Google Meet in the browser, signed in with the bot's Google account.

    Consumer Meet does not admit anonymous guests, so `secrets/google_meet.json` (a
    Playwright storage state created by `python -m bot.login google_meet`) is required.
    """

    platform = "google_meet"
    lobby_text = (r"Asking to be let in", r"You'll join the call when someone lets you in", r"Please wait until a meeting host brings you into the call")
    denied_text = (r"You can't join this (video )?call", r"Someone in the call denied your request", r"You've been denied")
    ended_text = (r"You left the meeting", r"You've been removed from the meeting", r"The call has ended", r"Return to home screen")
    leave_button = (r"^Leave call",)

    async def join(self, page, url, name):
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(4)
        await click_button(page, (r"Continue without microphone and camera", r"Dismiss", r"Got it"))
        await fill_first(page, ('input[aria-label="Your name"]', 'input[placeholder="Your name"]'), name)
        for label in (r"Turn off microphone", r"Turn off camera"):
            await click_button(page, (label,))
        for _attempt in range(10):
            if await click_button(page, (r"^Ask to join", r"^Join now", r"^Join here too", r"^Switch here")):
                return
            await asyncio.sleep(2)
        raise RuntimeError("Не найдена кнопка входа в Google Meet: проверьте ссылку и вход в аккаунт бота")

    async def after_join(self, page):
        await click_button(page, (r"^Got it", r"^Dismiss", r"^Close"))
        # The People panel is the only reliable place with every participant name.
        await click_button(page, (r"^People", r"^Show everyone"))

    async def participants(self, page):
        return await list_names(page, '[role="listitem"][aria-label]', "aria-label")

    async def speaking(self, page):
        # Tiles of speaking participants carry an audio-level indicator; its markup is not
        # stable, so this relies on the `data-audio-level` hook Meet exposes today and
        # silently returns nothing when it disappears (diarization still labels voices).
        with contextlib.suppress(PlaywrightError):
            return await page.evaluate(
                """() => [...document.querySelectorAll('[data-participant-id]')]
                    .filter((tile) => tile.querySelector('[data-audio-level]:not([data-audio-level="0"])'))
                    .map((tile) => (tile.querySelector('[data-self-name]')?.getAttribute('data-self-name') || tile.innerText.split('\\n')[0]).trim())
                    .filter(Boolean)"""
            )
        return []

    async def announce(self, page, message):
        with contextlib.suppress(PlaywrightError):
            if not await click_button(page, (r"^Chat with everyone", r"^Chat")):
                return False
            await asyncio.sleep(1)
            box = page.locator('textarea[aria-label*="Send a message"], textarea').first
            await box.fill(message, timeout=3000)
            await box.press("Enter")
            await asyncio.sleep(1)
            await click_button(page, (r"^People", r"^Show everyone"))
            return True
        return False

    async def leave(self, page):
        with contextlib.suppress(PlaywrightError):
            button = await find_button(page, self.leave_button)
            if button:
                await button.click(timeout=3000)
