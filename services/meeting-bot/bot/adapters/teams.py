import asyncio

from playwright.async_api import Error as PlaywrightError

from bot.adapters.base import Adapter, click_button, list_names


class TeamsAdapter(Adapter):
    """Microsoft Teams web client, joined as a guest (or with a stored account)."""

    platform = "teams"
    lobby_text = (r"Someone in the meeting should let you in soon", r"When the meeting starts, we'll let people know you're waiting", r"waiting for (someone|people) to let you in")
    denied_text = (r"denied access to the meeting", r"You can't join this meeting", r"Your request to join was declined")
    ended_text = (r"You've been removed from this meeting", r"The meeting has ended", r"You left the meeting", r"Thanks for joining")
    leave_button = (r"^Leave", r"^Hang up")
    leave_selectors = ('#hangup-button', '[data-tid="hangup-main-btn"]', '[data-tid="call-hangup"]')

    async def join(self, page, url, name):
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        # The guest pre-join screen takes 10-20 s to render. Keep "Computer audio" (the
        # default): the bot must hear the meeting; its own microphone is a silent source.
        for _attempt in range(45):
            await asyncio.sleep(2)
            await click_button(page, (r"Continue on this browser", r"Join on the web instead", r"Use the web app instead"))
            name_box = page.locator('input[data-tid="prejoin-display-name-input"], input[placeholder="Type your name"]').first
            if await name_box.count() and await name_box.is_visible() and not await name_box.input_value():
                await name_box.fill(name)
                await asyncio.sleep(1)
            join = page.locator('button[data-tid="prejoin-join-button"]').first
            if await join.count() and await join.is_enabled():
                try:
                    await join.click(timeout=3000)
                except PlaywrightError:
                    # Teams keeps an overlay over the pre-join screen; a DOM click still works.
                    await join.evaluate("(button) => button.click()")
                return
            if await click_button(page, (r"^Join now",)):
                return
        raise RuntimeError("Не найдена кнопка «Join now» в Teams: проверьте ссылку и разрешён ли гостевой вход")

    async def after_join(self, page):
        await click_button(page, (r"^People", r"^Show participants", r"^Participants"))

    async def participants(self, page):
        return await list_names(page, '[data-tid^="participantsInCall"] [role="treeitem"], [role="treeitem"][aria-label]', "aria-label")

    async def speaking(self, page):
        names = await list_names(page, '[data-tid="voice-level-stream-outline"][data-is-speaking="true"], [aria-label*="speaking" i]', "aria-label")
        return [item["name"].replace(", speaking", "").strip() for item in names]

    async def announce(self, page, message):
        if not await click_button(page, (r"^Chat", r"^Show conversation")):
            return False
        await asyncio.sleep(2)
        box = page.locator('[role="textbox"][contenteditable="true"]').first
        if not await box.count():
            return False
        await box.fill(message, timeout=3000)
        await box.press("Enter")
        return True
