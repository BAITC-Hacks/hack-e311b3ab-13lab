"""Shared helpers for platform adapters.

Web clients change their markup often, so adapters look for visible text and accessible
names (button labels) rather than generated CSS classes, and check every frame. The
browser runs with an en-US locale, which keeps the labels predictable.
"""

import contextlib
import re

from playwright.async_api import Error as PlaywrightError, Page


class Adapter:
    platform = "unknown"
    # Regular expressions (case-insensitive) that identify each state from page text.
    lobby_text: tuple[str, ...] = ()
    denied_text: tuple[str, ...] = ()
    ended_text: tuple[str, ...] = ()
    leave_button: tuple[str, ...] = ()

    def web_url(self, url: str) -> str:
        return url

    async def join(self, page: Page, url: str, name: str) -> None:
        raise NotImplementedError

    async def state(self, page: Page) -> str:
        """prejoin, lobby, joined, denied or ended."""
        text = await page_text(page)
        if matches(text, self.denied_text):
            return "denied"
        if matches(text, self.ended_text):
            return "ended"
        if await find_button(page, self.leave_button):
            return "joined"
        if matches(text, self.lobby_text):
            return "lobby"
        return "prejoin"

    async def after_join(self, page: Page) -> None:
        """Called once after admission (open panels, join computer audio)."""

    async def participants(self, page: Page) -> list[dict]:
        return []

    async def speaking(self, page: Page) -> list[str]:
        return []

    async def announce(self, page: Page, message: str) -> bool:
        return False

    async def leave(self, page: Page) -> None:
        with contextlib.suppress(PlaywrightError):
            button = await find_button(page, self.leave_button)
            if button:
                await button.click(timeout=3000)


def matches(text: str, patterns) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


async def page_text(page: Page) -> str:
    parts = []
    for frame in page.frames:
        with contextlib.suppress(PlaywrightError):
            parts.append(await frame.evaluate("() => document.body ? document.body.innerText : ''"))
    return "\n".join(parts)


async def find_button(page: Page, names):
    """First visible button (in any frame) whose accessible name matches one of `names`."""
    for frame in page.frames:
        for name in names:
            with contextlib.suppress(PlaywrightError):
                locator = frame.get_by_role("button", name=re.compile(name, re.IGNORECASE))
                count = await locator.count()
                for index in range(count):
                    candidate = locator.nth(index)
                    if await candidate.is_visible():
                        return candidate
    return None


async def click_button(page: Page, names, timeout=2000) -> bool:
    button = await find_button(page, names)
    if not button:
        return False
    with contextlib.suppress(PlaywrightError):
        await button.click(timeout=timeout)
        return True
    return False


async def fill_first(page: Page, selectors, value: str) -> bool:
    for frame in page.frames:
        for selector in selectors:
            with contextlib.suppress(PlaywrightError):
                locator = frame.locator(selector).first
                if await locator.count() and await locator.is_visible():
                    await locator.fill(value, timeout=2000)
                    return True
    return False


async def list_names(page: Page, selector: str, attribute: str | None = None) -> list[dict]:
    """Collect participant names from list items; the name doubles as a stable id."""
    names = []
    for frame in page.frames:
        with contextlib.suppress(PlaywrightError):
            values = await frame.eval_on_selector_all(
                selector,
                "(nodes, attribute) => nodes.map((node) => (attribute ? node.getAttribute(attribute) : node.innerText) || '')",
                attribute,
            )
            names.extend(value.split("\n")[0].strip() for value in values)
    seen, result = set(), []
    for name in names:
        if name and name not in seen and len(name) <= 120:
            seen.add(name)
            result.append({"id": name, "name": name})
    return result
