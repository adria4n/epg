#!/usr/bin/env python3

import json
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import sys
from playwright.sync_api import sync_playwright

AGENDA_URL = "https://streamxhd.sbs/eventos.json"
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
        # Formato ISO con offset: 2026-10-31T18:00:00-05:00
        if "T" in time_str:
            return datetime.fromisoformat(time_str)
        # Formato simple: 2026-10-31 17:00
        dt = datetime.strptime(time_str.strip(), "%Y-%m-%d %H:%M")
        return dt.replace(tzinfo=ZoneInfo(tz_name))
    except Exception:
        return None

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

    print(f"Eventos únicos: {len(unique)}", file=sys.stderr)
    output = []

    for ev in unique:
        title = ev.get("title", "").strip()
        time_str = ev.get("time", "")
        tz_name = ev.get("timezone", "America/Lima")
        servers = ev.get("servers", [])

        start = parse_event_time(time_str, tz_name)
        if not start:
            print(f"  Saltando (tiempo inválido): {title}", file=sys.stderr)
            continue

        # Convertir a Mexico City para consistencia con el script anterior
        start = start.astimezone(TZ)
        end = start + timedelta(hours=2)

        server_url = select_server_url(servers)
        print(f"Obteniendo m3u8 de: {title} → {server_url}", file=sys.stderr)
        m3u8 = get_m3u8(server_url) if server_url else ""

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
