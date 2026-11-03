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

DAYS_RANGE = range(-1, 7)  # ayer hasta +6 días

def fetch(url: str) -> str:
    print(f"Descargando {url}...", file=sys.stderr)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read().decode("utf-8", errors="replace")

def parse_time_12h(time_str: str, base_date: datetime) -> datetime | None:
    """Convierte '11:40 PM' o '1:34 AM' a datetime con la fecha base."""
    time_str = time_str.strip().upper()
    m = re.match(r'(\d{1,2}):(\d{2})\s*(AM|PM)', time_str)
    if not m:
        return None
    hour, minute, ampm = int(m.group(1)), int(m.group(2)), m.group(3)
    if ampm == "PM" and hour != 12:
        hour += 12
    if ampm == "AM" and hour == 12:
        hour = 0
    return base_date.replace(hour=hour, minute=minute, second=0, microsecond=0)

def extract_programs(html: str, day: datetime) -> list[dict]:
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
        title = cells[2].get_text(" ", strip=True)

        # Limpiar título (quitar espacios extra y saltos)
        title = re.sub(r'\s+', ' ', title).strip()

        if not start_str or not title or "Horarios" in start_str:
            continue

        key = (start_str, end_str, title)
        if key in seen:
            continue
        seen.add(key)

        start = parse_time_12h(start_str, day)
        end = parse_time_12h(end_str, day)

        if not start:
            continue

        # Si el end es menor que start, es del día siguiente
        if end and end <= start:
            end += timedelta(days=1)

        # Si no hay end, asumir 30 min
        if not end:
            end = start + timedelta(minutes=30)

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
