#!/usr/bin/env python3

import json
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import sys
from playwright.sync_api import sync_playwright

AGENDA_URL = "https://la18hd.su/eventos/json/agenda123.json"
OUTPUT_FILE = "agenda.json"
TZ = ZoneInfo("America/Mexico_City")
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

def get_m3u8(page_url: str) -> str:
    m3u8_url = None
    def handle_request(request):
        nonlocal m3u8_url
        url = request.url
        if ".m3u8" in url and m3u8_url is None:
            m3u8_url = url
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=USER_AGENT)
        page = context.new_page()
        page.on("request", handle_request)
        try:
            page.goto(page_url, wait_until="networkidle", timeout=45000)
            page.wait_for_timeout(6000)
        except Exception as e:
            print(f"  Error cargando {page_url}: {e}", file=sys.stderr)
        browser.close()
    return m3u8_url or ""

def main():
    print("Descargando agenda...", file=sys.stderr)
    req = urllib.request.Request(AGENDA_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        events = json.loads(resp.read().decode("utf-8"))

    seen_titles = set()
    unique = []
    for ev in events:
        title = ev.get("title", "").strip()
        if not title or title in seen_titles:
            continue
        seen_titles.add(title)
        unique.append(ev)

    print(f"Eventos únicos: {len(unique)}", file=sys.stderr)
    output = []

    for ev in unique:
        title = ev.get("title", "").strip()
        date_str = ev.get("date", "")
        time_str = ev.get("time", "00:00")
        link = ev.get("link", "")

        try:
            hour, minute = map(int, time_str.split(":"))
            start = datetime.strptime(date_str, "%Y-%m-%d").replace(
                hour=hour, minute=minute, tzinfo=TZ
            )
            end = start + timedelta(hours=2)
        except Exception:
            continue

        print(f"Obteniendo m3u8 de: {title}", file=sys.stderr)
        m3u8 = get_m3u8(link) if link else ""

        output.append({
            "titulo": title,
            "sta": start.strftime("%Y-%m-%d/%H:%M"),
            "end": end.strftime("%Y-%m-%d/%H:%M"),
            "url": m3u8,
            "clearkey": ""
        })

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"Listo: {len(output)} eventos en {OUTPUT_FILE}", file=sys.stderr)

if __name__ == "__main__":
    main()
