#!/usr/bin/env python3

import json
import urllib.request
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import sys
from playwright.sync_api import sync_playwright

CHANNEL = "telemundo"
BASE_URL = f"https://mi.tv/mx/async/channel/{CHANNEL}"
STREAM_PAGE = "https://streamxhd.sbs/live1.php?stream=telemundo"
TZ = ZoneInfo("America/Mexico_City")
OUTPUT_FILE = "telemund22o.json"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
UTC_OFFSET = -360

def get_m3u8() -> str:
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
        page.goto(STREAM_PAGE, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(8000)
        browser.close()
    if not m3u8_url:
        raise RuntimeError("No se detectó m3u8 en el tráfico")
    print(f"m3u8 obtenido: {m3u8_url}", file=sys.stderr)
    return m3u8_url

def fetch_page(date_str: str) -> str:
    url = f"{BASE_URL}/{date_str}/{UTC_OFFSET}"
    print(f"Descargando {url}...", file=sys.stderr)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read().decode("utf-8", errors="replace")

def parse_items(html: str, day: datetime, m3u8_url: str) -> list[dict]:
    times = re.findall(r'<span class="time">\s*([^<]+?)\s*</span>', html)
    titles = re.findall(r'<h2>\s*([^<]+?)\s*</h2>', html)
    programs = []
    current_day = day
    for i, (t, title) in enumerate(zip(times, titles)):
        try:
            hour, minute = map(int, t.split(":"))
            start = current_day.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if i > 0 and hour < 6 and programs and programs[-1].get("_start") and programs[-1]["_start"].hour >= 20:
                start += timedelta(days=1)
                current_day = start
            if i + 1 < len(times):
                next_h, next_m = map(int, times[i + 1].split(":"))
                end = current_day.replace(hour=next_h, minute=next_m, second=0, microsecond=0)
                if end <= start:
                    end += timedelta(days=1)
            else:
                end = start + timedelta(minutes=60)
            programs.append({
                "titulo": title.strip(),
                "sta": start.strftime("%Y-%m-%d/%H:%M"),
                "end": end.strftime("%Y-%m-%d/%H:%M"),
                "url": m3u8_url,
                "clearkey": "",
                "_start": start,
            })
        except Exception:
            continue
    for p in programs:
        p.pop("_start", None)
    return programs

def main():
    m3u8_url = get_m3u8()
    all_programs = []
    today = datetime.now(TZ).date()
    for i in range(-1, 7):
        d = today + timedelta(days=i)
        date_str = d.strftime("%Y-%m-%d")
        try:
            html = fetch_page(date_str)
            progs = parse_items(html, datetime.combine(d, datetime.min.time(), tzinfo=TZ), m3u8_url)
            all_programs.extend(progs)
            print(f"  {date_str}: {len(progs)} programas", file=sys.stderr)
        except Exception as e:
            print(f"  Error en {date_str}: {e}", file=sys.stderr)
    all_programs.sort(key=lambda x: x["sta"])
    seen = set()
    unique = [p for p in all_programs if not (p["sta"] in seen or seen.add(p["sta"]))]
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(unique, f, indent=2, ensure_ascii=False)
    print(f"Listo: {len(unique)} programas en {OUTPUT_FILE}", file=sys.stderr)

if __name__ == "__main__":
    main()
