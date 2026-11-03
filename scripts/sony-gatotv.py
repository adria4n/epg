#!/usr/bin/env python3

import json
import urllib.request
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import sys

CHANNEL_SLUG = "sony_mexico"
BASE_URL = f"https://www.gatotv.com/canal/{CHANNEL_SLUG}"
TZ = ZoneInfo("America/Mexico_City")
OUTPUT_FILE = "sony.json"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

def fetch_page(date_str: str) -> str:
    url = f"{BASE_URL}/{date_str}"
    print(f"Descargando {url}...", file=sys.stderr)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read().decode("utf-8", errors="replace")

def parse_items(html: str, day: datetime) -> list[dict]:
    rows = re.findall(r'<tr class="tbl_EPG_row[^"]*">(.*?)</tr>', html, re.DOTALL)
    programs = []
    for row in rows:
        times = re.findall(r'<time datetime="([^"]+)">', row)
        title_match = re.search(r'<span>([^<]+)</span>', row)
        if len(times) < 2 or not title_match:
            continue
        title = title_match.group(1).strip()
        start_h, start_m = map(int, times[0].split(":"))
        end_h, end_m = map(int, times[1].split(":"))
        start = day.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
        end = day.replace(hour=end_h, minute=end_m, second=0, microsecond=0)
        if end <= start:
            end += timedelta(days=1)
        programs.append({
            "titulo": title,
            "sta": start.strftime("%Y-%m-%d/%H:%M"),
            "end": end.strftime("%Y-%m-%d/%H:%M"),
        })
    return programs

def main():
    all_programs = []
    today = datetime.now(TZ).date()
    for i in range(-1, 7):
        d = today + timedelta(days=i)
        date_str = d.strftime("%Y-%m-%d")
        try:
            html = fetch_page(date_str)
            progs = parse_items(html, datetime.combine(d, datetime.min.time(), tzinfo=TZ))
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
