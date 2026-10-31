#!/usr/bin/env python3

import json
import urllib.request
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import sys

CHANNEL = "azteca-13"
BASE_URL = f"https://mi.tv/mx/async/channel/{CHANNEL}"
TZ = ZoneInfo("America/Mexico_City")
OUTPUT_FILE = "azteca-13.json"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

def get_utc_offset() -> int:
    """Offset en minutos respecto a UTC (ej. -360 para México)."""
    now = datetime.now(TZ)
    return int(now.utcoffset().total_seconds() / 60)

def fetch_page(date_str: str) -> str:
    offset = get_utc_offset()
    url = f"{BASE_URL}/{date_str}/{offset}"
    print(f"Descargando {url}...", file=sys.stderr)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read().decode("utf-8", errors="replace")

def parse_time(t: str) -> tuple[int, int]:
    """Acepta '08:00', '8:00', '20:30', etc."""
    t = t.strip()
    parts = t.split(":")
    hour = int(parts[0])
    minute = int(parts[1]) if len(parts) > 1 else 0
    return hour, minute

def parse_items(html: str, day: datetime) -> list[dict]:
    times = re.findall(r'<span class="time">\s*([^<]+?)\s*</span>', html)
    titles = re.findall(r'<h2>\s*([^<]+?)\s*</h2>', html)
    programs = []
    current_day = day
    prev_hour = -1

    for i, (t, title) in enumerate(zip(times, titles)):
        try:
            hour, minute = parse_time(t)
            start = current_day.replace(hour=hour, minute=minute, second=0, microsecond=0)

            # Cruce de medianoche: la hora baja bruscamente
            if prev_hour >= 0 and hour < prev_hour - 6:
                start += timedelta(days=1)
                current_day = start

            if i + 1 < len(times):
                next_h, next_m = parse_time(times[i + 1])
                end = current_day.replace(hour=next_h, minute=next_m, second=0, microsecond=0)
                if end <= start:
                    end += timedelta(days=1)
            else:
                end = start + timedelta(minutes=60)

            programs.append({
                "titulo": title.strip(),
                "sta": start.strftime("%Y-%m-%d/%H:%M"),
                "end": end.strftime("%Y-%m-%d/%H:%M"),
            })

            prev_hour = hour
        except Exception:
            continue

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
