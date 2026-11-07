#!/usr/bin/env python3
"""
Saca programación de DSports 1610, 1612 y 1613
y guarda en dsports.json, dsports-2.json y dsports-plus.json
"""

import json
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

TZ = ZoneInfo("America/Mexico_City")
URL = "https://www.directvsports.com/programacion/"

CHANNELS = {
    "1610": "dsports.json",
    "1612": "dsports-2.json",
    "1613": "dsports-plus.json",
}

def main():
    programs = {ch: [] for ch in CHANNELS}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # headless=False para que veas qué pasa
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="es-MX",
            viewport={"width": 1400, "height": 900}
        )
        page = context.new_page()

        captured = []

        def on_response(response):
            url = response.url
            if any(x in url.lower() for x in ["epg", "schedule", "program", "guia", "guide", "canal", "channel", "json"]):
                try:
                    if "json" in response.headers.get("content-type", ""):
                        data = response.json()
                        captured.append({"url": url, "data": data})
                        print(f"[API] {url[:100]}", file=sys.stderr)
                except Exception:
                    pass

        page.on("response", on_response)

        print("Abriendo programación...", file=sys.stderr)
        page.goto(URL, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(6000)

        # Intentar interactuar con el selector de días
        try:
            page.click("text=HOY", timeout=5000)
            page.wait_for_timeout(1500)
        except Exception:
            pass

        # Scroll para forzar carga
        for _ in range(4):
            page.keyboard.press("ArrowRight")
            page.wait_for_timeout(1000)

        page.wait_for_timeout(3000)
        browser.close()

    # Guarda todo lo que capturó para que lo analices
    with open("dsports_raw.json", "w", encoding="utf-8") as f:
        json.dump(captured, f, indent=2, ensure_ascii=False, default=str)

    print(f"\nCapturadas {len(captured)} respuestas → dsports_raw.json", file=sys.stderr)
    print("Revisa ese archivo, busca el endpoint que trae los programas y avísame para terminar el parseo.", file=sys.stderr)

if __name__ == "__main__":
    main()
