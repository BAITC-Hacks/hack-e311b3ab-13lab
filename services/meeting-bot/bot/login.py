"""Sign the bot into a platform once and save the Playwright storage state to /secrets.

    printf '%s\\n' "$PASSWORD" | docker compose run --rm -T meeting-bot python -m bot.login google_meet --email bot@example.com

The password is read from standard input and never written anywhere. Screenshots of each
step go to /debug/login so a person can see verification prompts. If Google asks for a
code, run again with --code-stdin and pass the code on the second line of stdin.
"""

import argparse
import asyncio
import contextlib
import sys
import time
from pathlib import Path

from playwright.async_api import async_playwright

from bot.browser import SECRETS, launch, new_context

SHOTS = Path("/debug/login")


async def shot(page, label):
    SHOTS.mkdir(parents=True, exist_ok=True)
    with contextlib.suppress(Exception):
        await page.screenshot(path=str(SHOTS / f"{int(time.time())}-{label}.png"))


async def google(email, password, code):
    async with async_playwright() as playwright:
        browser = await launch(playwright)
        context = await new_context(browser, "none")
        page = await context.new_page()
        await page.goto("https://accounts.google.com/signin/v2/identifier?hl=en&continue=https%3A%2F%2Fmeet.google.com%2F", wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        await shot(page, "start")
        await page.locator('input[name="identifier"], input[type="email"]').first.fill(email)
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(5000)
        await shot(page, "after-email")
        password_box = page.locator('input[name="Passwd"], input[type="password"]:not([name="hiddenPassword"])').first
        try:
            await password_box.wait_for(state="visible", timeout=20000)
        except Exception:
            await shot(page, "no-password-box")
            print("Google did not show the password step. See /debug/login screenshots.", file=sys.stderr)
            return 2
        await password_box.fill(password)
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(8000)
        await shot(page, "after-password")
        if code and "challenge" in page.url:
            box = page.locator('input[type="tel"], input[name="totpPin"], input[type="text"]').first
            await box.fill(code)
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(8000)
            await shot(page, "after-code")
        for _wait in range(30):
            if page.url.startswith("https://meet.google.com") or "myaccount.google.com" in page.url:
                break
            await page.wait_for_timeout(2000)
        await shot(page, "final")
        if not (page.url.startswith("https://meet.google.com") or "myaccount.google.com" in page.url):
            print(f"Sign-in not finished, Google is at: {page.url.split('?')[0]}. See /debug/login screenshots.", file=sys.stderr)
            return 3
        SECRETS.mkdir(parents=True, exist_ok=True)
        target = SECRETS / "google_meet.json"
        await context.storage_state(path=str(target))
        target.chmod(0o600)
        print(f"Signed in. Session saved to {target}")
        await browser.close()
        return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("platform", choices=["google_meet"])
    parser.add_argument("--email", required=True)
    parser.add_argument("--code-stdin", action="store_true")
    args = parser.parse_args()
    password = sys.stdin.readline().rstrip("\n")
    code = sys.stdin.readline().strip() if args.code_stdin else ""
    sys.exit(asyncio.run(google(args.email, password, code)))


if __name__ == "__main__":
    main()
