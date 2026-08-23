"""Screenshot card hover preview on local game."""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(r"D:\Kingmaker\crown-and-court\web\e2e-screenshots")
OUT.mkdir(parents=True, exist_ok=True)
ROOT = Path(r"D:\Kingmaker\crown-and-court")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto("http://127.0.0.1:8000/", wait_until="networkidle", timeout=30000)
        page.fill('input[placeholder="Enter display name"]', "Rafay")
        page.get_by_role("button", name="Create Lobby").click()
        page.wait_for_timeout(300)
        page.get_by_role("button", name="Create & Enter Lobby").click()
        page.wait_for_timeout(1200)

        code = page.locator("h1 >> xpath=following-sibling::p[1]").inner_text().strip()
        print("CODE", code)
        bot = subprocess.Popen(
            [sys.executable, str(ROOT / "scripts" / "e2e_bots.py"), code],
            cwd=str(ROOT),
        )
        page.wait_for_timeout(3500)
        page.get_by_role("button", name="Ready Up").click()
        page.wait_for_timeout(1500)
        start = page.get_by_role("button", name="Start Game")
        if not start.is_enabled():
            print("START DISABLED")
            page.screenshot(path=str(OUT / "13-hover-fail-lobby.png"), full_page=True)
            bot.terminate()
            browser.close()
            return
        start.click()
        page.wait_for_timeout(1500)
        begin = page.get_by_role("button", name="Begin Match")
        if begin.count():
            begin.click()
        page.wait_for_timeout(2000)

        # Negotiate / wait until play panel or hand cards visible
        for i in range(40):
            body = page.locator("body").inner_text()
            if "Select" in body and "card" in body.lower():
                print("PLAY PHASE at iter", i)
                break
            if page.get_by_role("button", name="Pass").count():
                try:
                    page.get_by_role("button", name="Pass").click(timeout=1000)
                except Exception:
                    pass
            page.wait_for_timeout(800)
        else:
            print("NO PLAY PHASE; body:", body[:400].replace("\n", " | "))

        # Prefer play-panel cards; else any face-up card button
        cards = page.locator("button.card-face")
        n = cards.count()
        print("CARD_BUTTONS", n)
        if n == 0:
            page.screenshot(path=str(OUT / "13-hover-no-cards.png"), full_page=True)
            bot.terminate()
            browser.close()
            return

        card = cards.first
        card.hover()
        page.wait_for_timeout(500)
        # Preview portal
        preview = page.locator(".card-preview")
        print("PREVIEW_VISIBLE", preview.count() > 0)
        if preview.count():
            print("PREVIEW_TEXT", preview.first.inner_text()[:280].replace("\n", " | "))
        page.screenshot(path=str(OUT / "13-local-card-hover-preview.png"), full_page=True)
        print("SHOT", OUT / "13-local-card-hover-preview.png")

        bot.terminate()
        browser.close()


if __name__ == "__main__":
    main()
