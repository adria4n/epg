#!/usr/bin/env python3

import json
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from playwright.sync_api import sync_playwright

AGENDA_URL = "https://streamxhd.sbs/eventos.json"
OUTPUT_FILE = "agenda.json"
TZ = ZoneInfo("America/Mexico_City")
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
MAX_WORKERS = 50

def get_m3u8(page_url: str) -> str:
    if not page_url:
        return ""
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
            page.wait_for_timeout(5000)
        except Exception as e:
            print(f"  Error en {page_url}: {e}", file=sys.stderr)
        finally:
            browser.close()
    return m3u8_url or ""

def select_server_url(servers: list) -> str:
    if not servers:
        return ""
    n = len(servers)
    if n >= 3:
        return servers[2].get("url", "")
    elif n >= 2:
        return servers[1].get("url", "")
    else:
        return servers[0].get("url", "")

def parse_event_time(time_str: str, tz_name: str = "America/Lima") -> datetime | None:
    if not time_str:
        return None
    try:
        if "T" in time_str:
            return datetime.fromisoformat(time_str)
        dt = datetime.strptime(time_str.strip(), "%Y-%m-%d %H:%M")
        return dt.replace(tzinfo=ZoneInfo(tz_name))
    except Exception:
        return None

def process_event(ev: dict) -> dict | None:
    title = ev.get("title", "").strip()
    time_str = ev.get("time", "")
    tz_name = ev.get("timezone", "America/Lima")
    servers = ev.get("servers", [])

    start = parse_event_time(time_str, tz_name)
    if not start:
        print(f"  Saltando (tiempo inválido): {title}", file=sys.stderr)
        return None

    start = start.astimezone(TZ)
    end = start + timedelta(hours=2)
    server_url = select_server_url(servers)

    print(f"Procesando: {title}", file=sys.stderr)
    m3u8 = get_m3u8(server_url)

    return {
        "titulo": title,
        "sta": start.strftime("%Y-%m-%d/%H:%M"),
        "end": end.strftime("%Y-%m-%d/%H:%M"),
        "url": m3u8,
        "clearkey": ""
    }

def main():
    print("Descargando agenda...", file=sys.stderr)
    req = urllib.request.Request(AGENDA_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    events = []
    for sport in data.get("sports", []):
        for league in sport.get("leagues", []):
            for ev in league.get("events", []):
                events.append(ev)

    seen_titles = set()
    unique = []
    for ev in events:
        title = ev.get("title", "").strip()
        if not title or title in seen_titles:
            continue
        seen_titles.add(title)
        unique.append(ev)

    print(f"Eventos únicos: {len(unique)} → extrayendo m3u8 en paralelo (hasta 50 a la vez)...", file=sys.stderr)

    output = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_event, ev): ev for ev in unique}
        for future in as_completed(futures):
            result = future.result()
            if result:
                output.append(result)

    output.sort(key=lambda x: x["sta"])

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"Listo: {len(output)} eventos en {OUTPUT_FILE}", file=sys.stderr)

if __name__ == "__main__":
    main()
