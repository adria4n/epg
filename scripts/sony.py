#!/usr/bin/env python3

import json
import urllib.request
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import sys
from bs4 import BeautifulSoup

TZ = ZoneInfo("America/Mexico_City")
OUTPUT_FILE = "sony-mexico.json"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
BASE = "https://www.gatotv.com/canal/sony_mexico"

DAYS_RANGE = range(-1, 7)

def fetch(url: str) -> str:
    print(f"Descargando {url}...", file=sys.stderr)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read().decode("utf-8", errors="replace")

def parse_time_12h(time_str: str) -> tuple[int, int] | None:
    """Regresa (hour_24, minute) desde '11:40 PM' o '1:34 AM'."""
    time_str = time_str.strip().upper()
    m = re.match(r'(\d{1,2}):(\d{2})\s*(AM|PM)', time_str)
    if not m:
        return None
    hour, minute, ampm = int(m.group(1)), int(m.group(2)), m.group(3)
    if ampm == "PM" and hour != 12:
        hour += 12
    if ampm == "AM" and hour == 12:
        hour = 0
    return hour, minute

def extract_programs(html: str, page_date: datetime) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    programs = []
    seen = set()

    for time_el in soup.find_all("time"):
        row = time_el.find_parent("tr")
        if not row:
            continue
        cells = row.find_all("td")
        if len(cells) < 3:
            continue

        start_str = cells[0].get_text(strip=True)
        end_str = cells[1].get_text(strip=True)
        title = re.sub(r'\s+', ' ', cells[2].get_text(" ", strip=True)).strip()

        if not start_str or not title or "Horario" in start_str:
            continue

        key = (start_str, end_str, title)
        if key in seen:
            continue
        seen.add(key)

        start_hm = parse_time_12h(start_str)
        end_hm = parse_time_12h(end_str)
        if not start_hm:
            continue

        sh, sm = start_hm
        eh, em = end_hm if end_hm else (sh, sm)

        # Si empieza en PM tarde y termina en AM, el start es del día anterior
        crosses_midnight = (sh >= 12 and eh < 12) or (eh < sh)
        
        if crosses_midnight and sh >= 18:
            # Empezó la noche anterior
            start_date = page_date - timedelta(days=1)
        else:
            start_date = page_date

        start = start_date.replace(hour=sh, minute=sm, second=0, microsecond=0)
        
        end_date = start_date
        if eh < sh or (eh == sh and em <= sm):
            end_date = start_date + timedelta(days=1)
        end = end_date.replace(hour=eh, minute=em, second=0, microsecond=0)

        programs.append({
            "titulo": title,
            "sta": start.strftime("%Y-%m-%d/%H:%M"),
            "end": end.strftime("%Y-%m-%d/%H:%M"),
            "_start": start,
        })

    return programs

def main():
    all_programs = []
    today = datetime.now(TZ).date()

    for offset in DAYS_RANGE:
        d = today + timedelta(days=offset)
        date_str = d.strftime("%Y-%m-%d")
        url = f"{BASE}/{date_str}" if offset != 0 else BASE

        try:
            html = fetch(url)
            day_dt = datetime.combine(d, datetime.min.time(), tzinfo=TZ)
            progs = extract_programs(html, day_dt)
            all_programs.extend(progs)
            print(f"  {date_str}: {len(progs)} programas", file=sys.stderr)
        except Exception as e:
            print(f"  Error en {date_str}: {e}", file=sys.stderr)

    all_programs.sort(key=lambda x: x["_start"])
    seen = set()
    unique = []
    for p in all_programs:
        key = p["sta"]
        if key not in seen:
            seen.add(key)
            p.pop("_start", None)
            unique.append(p)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(unique, f, indent=2, ensure_ascii=False)

    print(f"Listo: {len(unique)} programas en {OUTPUT_FILE}", file=sys.stderr)

if __name__ == "__main__":
    main()
