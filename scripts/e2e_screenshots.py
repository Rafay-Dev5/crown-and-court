"""Capture e2e screenshots with Playwright (local + production)."""
from __future__ import annotations

import json
import subprocess
import sys
import time
import uuid
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(r"D:\Kingmaker\crown-and-court\web\e2e-screenshots")
OUT.mkdir(parents=True, exist_ok=True)
ROOT = Path(r"D:\Kingmaker\crown-and-court")


def shot(page, name: str):
    path = OUT / f"{name}.png"
    page.screenshot(path=str(path), full_page=True)
    print("SHOT", path)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 900})

        # --- PRODUCTION ---
        page = context.new_page()
        page.goto("https://kingmaker.up.railway.app/", wait_until="networkidle", timeout=90000)
        page.wait_for_timeout(2000)
        shot(page, "01-prod-home")
        print("PROD home connected?:", "Connecting" in page.content())

        page.fill('input[placeholder="Enter display name"]', "Rafay")
        page.get_by_role("button", name="Create Lobby").click()
        page.wait_for_timeout(500)
        if page.get_by_role("button", name="Create & Enter Lobby").count():
            page.get_by_role("button", name="Create & Enter Lobby").click()
        page.wait_for_timeout(2500)
        shot(page, "02-prod-lobby-or-error")
        print("PROD after create URL:", page.url)
        print("PROD text:", page.locator("body").inner_text()[:450].replace("\n", " | "))

        page.goto("https://kingmaker.up.railway.app/health", wait_until="domcontentloaded")
        page.wait_for_timeout(500)
        shot(page, "03-prod-health")
        print("PROD health:", page.locator("body").inner_text()[:200])

        # --- LOCAL ---
        page2 = context.new_page()
        page2.goto("http://127.0.0.1:8000/", wait_until="networkidle", timeout=30000)
        page2.wait_for_timeout(1500)
        shot(page2, "04-local-home")

        page2.fill('input[placeholder="Enter display name"]', "Rafay")
        page2.get_by_role("button", name="Create Lobby").click()
        page2.wait_for_timeout(400)
        page2.get_by_role("button", name="Create & Enter Lobby").click()
        page2.wait_for_timeout(1500)
        shot(page2, "05-local-lobby-solo")

        # Room code is large tracking text under Lobby heading
        code = page2.locator("h1 >> xpath=following-sibling::p[1]").inner_text().strip()
        if len(code) < 3:
            # fallback: any uppercase code-like text
            text = page2.locator("body").inner_text()
            for line in text.splitlines():
                if line.strip().isalnum() and 3 <= len(line.strip()) <= 8 and line.strip().isupper():
                    code = line.strip()
                    break
        print("LOCAL code", code)

        bot = subprocess.Popen(
            [sys.executable, str(ROOT / "scripts" / "e2e_bots.py"), code],
            cwd=str(ROOT),
        )
        page2.wait_for_timeout(4000)
        shot(page2, "06-local-lobby-4players")
        print("LOCAL lobby:", page2.locator("body").inner_text()[:500].replace("\n", " | "))

        page2.get_by_role("button", name="Ready Up").click()
        page2.wait_for_timeout(2000)
        shot(page2, "07-local-all-ready")

        start = page2.get_by_role("button", name="Start Game")
        print("Start enabled?", start.is_enabled())
        if start.is_enabled():
            start.click()
            page2.wait_for_timeout(2000)
            shot(page2, "08-local-match-intro")
            begin = page2.get_by_role("button", name="Begin Match")
            if begin.count():
                begin.click()
                page2.wait_for_timeout(2500)
                shot(page2, "09-local-game-board")
                # try pass if negotiation panel visible
                if page2.get_by_role("button", name="Pass").count():
                    page2.get_by_role("button", name="Pass").click()
                    page2.wait_for_timeout(1500)
                    shot(page2, "10-local-after-pass")
                print("LOCAL game:", page2.locator("body").inner_text()[:500].replace("\n", " | "))
        else:
            shot(page2, "08-local-start-disabled")

        bot.terminate()
        browser.close()
        print("DONE screenshots in", OUT)


if __name__ == "__main__":
    # Patch e2e_bots to use absolute ready
    main()
