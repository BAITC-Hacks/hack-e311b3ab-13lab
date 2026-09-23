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
    leave_selectors: tuple[str, ...] = ()
    last_match = ""

    def web_url(self, url: str) -> str:
        return url

    async def join(self, page: Page, url: str, name: str) -> None:
        raise NotImplementedError

    async def state(self, page: Page) -> str:
        """prejoin, lobby, joined, denied or ended. Being in the call wins over any text."""
        if await find_button(page, self.leave_button) or await self._visible(page, self.leave_selectors):
            return "joined"
        text = await page_text(page)
        for state, patterns in (("denied", self.denied_text), ("ended", self.ended_text)):
            for pattern in patterns:
                if found := re.search(pattern, text, re.IGNORECASE):
                    self.last_match = text[max(0, found.start() - 80):found.end() + 80].replace("\n", " | ")
                    return state
        if matches(text, self.lobby_text):
            return "lobby"
        return "prejoin"

    async def _visible(self, page: Page, selectors) -> bool:
        for frame in page.frames:
            for selector in selectors:
                with contextlib.suppress(PlaywrightError):
                    locator = frame.locator(selector).first
                    if await locator.count() and await locator.is_visible():
                        return True
        return False

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


_MARK = """(patterns) => {
  const regexes = patterns.map((pattern) => new RegExp(pattern, 'i'))
  document.querySelectorAll('[data-hattama-target]').forEach((node) => node.removeAttribute('data-hattama-target'))
  const nodes = [...document.querySelectorAll('button, [role="button"], a[role="button"]')]
  for (const regex of regexes) {
    for (const node of nodes) {
      const label = (node.getAttribute('aria-label') || '').trim()
      const text = (node.innerText || '').trim()
      const box = node.getBoundingClientRect()
      const enabled = !node.disabled && node.getAttribute('aria-disabled') !== 'true'
      if (enabled && box.width > 0 && box.height > 0 && (regex.test(label) || regex.test(text))) {
        node.setAttribute('data-hattama-target', '1')
        return true
      }
    }
  }
  return false
}"""


async def find_button(page: Page, names):
    """First visible, enabled button in any frame whose aria-label or text matches `names`.

    Matches on the DOM directly: some clients (Teams) keep controls inside aria-hidden
    containers, where accessibility-tree lookups find nothing.
    """
    for frame in page.frames:
        with contextlib.suppress(PlaywrightError):
            if await frame.evaluate(_MARK, list(names)):
                return frame.locator('[data-hattama-target="1"]').first
    return None


async def click_button(page: Page, names, timeout=2000) -> bool:
    button = await find_button(page, names)
    if not button:
        return False
    try:
        await button.click(timeout=timeout)
        return True
    except PlaywrightError:
        with contextlib.suppress(PlaywrightError):
            await button.evaluate("(node) => node.click()")
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
