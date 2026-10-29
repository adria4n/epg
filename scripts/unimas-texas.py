#!/usr/bin/env python3

import json
import urllib.request
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import sys

SITE_ID = "unimas-ktfv-mcallen-tx/13230"
BASE_URL = f"https://www.tvpassport.com/tv-listings/stations/{SITE_ID}"
TZ_TARGET = ZoneInfo("America/Mexico_City")
OUTPUT_FILE = "unimas-texas.json"
DAYS_AHEAD = 2
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

def fetch_page(date_str: str | None = None) -> str:
    url = BASE_URL if not date_str else f"{BASE_URL}/{date_str}"
    print(f"Descargando {url}...", file=sys.stderr)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read().decode("utf-8", errors="replace")

def get_page_timezone(html: str) -> ZoneInfo:
    m = re.search(r'<option[^>]*value="([^"]*)"[^>]*selected', html, re.I)
    tz_name = m.group(1) if m else "America/New_York"
    print(f"  Zona de la página: {tz_name}", file=sys.stderr)
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return ZoneInfo("America/New_York")

def parse_items(html: str, page_tz: ZoneInfo) -> list[dict]:
    blocks = re.findall(
        r'<div[^>]*class="[^"]*list-group-item[^"]*"[^>]*>.*?</div>',
        html,
        re.DOTALL,
    )
    programs = []
    for block in blocks:
        def attr(name: str) -> str:
            m = re.search(rf'data-{name}="([^"]*)"', block, re.I)
            return m.group(1).strip() if m else ""

        show = attr("showName")
        episode = attr("episodeTitle")
        start_raw = attr("st")
        duration = attr("duration")

        if not start_raw or not show:
            continue

        title = show
        if episode:
            title = f"{show} / {episode}"

        try:
            start_naive = datetime.strptime(start_raw, "%Y-%m-%d %H:%M:%S")
            start_page = start_naive.replace(tzinfo=page_tz)
            start = start_page.astimezone(TZ_TARGET)
            mins = int(duration) if duration.isdigit() else 30
            end = start + timedelta(minutes=mins)
        except Exception:
            continue

        programs.append({
            "titulo": title,
            "sta": start.strftime("%Y-%m-%d/%H:%M:%S"),
            "end": end.strftime("%Y-%m-%d/%H:%M:%S"),
        })

    return programs

def main():
    all_programs = []
    today = datetime.now(TZ_TARGET).date()

    for i in range(-1, DAYS_AHEAD):
        d = today + timedelta(days=i)
        date_str = d.strftime("%Y-%m-%d")
        try:
            html = fetch_page(date_str)
            page_tz = get_page_timezone(html)
            progs = parse_items(html, page_tz)
            all_programs.extend(progs)
            print(f"  {date_str}: {len(progs)} programas", file=sys.stderr)
        except Exception as e:
            print(f"  Error en {date_str}: {e}", file=sys.stderr)

    all_programs.sort(key=lambda x: x["sta"])
    seen = set()
    unique = []
    for p in all_programs:
        key = p["sta"]
        if key not in seen:
            seen.add(key)
            unique.append(p)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(unique, f, indent=2, ensure_ascii=False)

    print(f"Listo: {len(unique)} programas en {OUTPUT_FILE}", file=sys.stderr)

if __name__ == "__main__":
    main()
