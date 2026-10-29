#!/usr/bin/env python3

import json
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import sys

BASE_URL = "https://d3ur398j0yj7gx.cloudfront.net/ajax/program_guide/feed/block/{year}/{month:02d}/{day:02d}"
TZ = ZoneInfo("America/Mexico_City")
OUTPUT_FILE = "telemundo-texa.json"

def fetch_day(date: datetime) -> list:
    url = BASE_URL.format(year=date.year, month=date.month, day=date.day)
    print(f"Fetching {url}", file=sys.stderr)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.load(resp)
            return data if isinstance(data, list) else []
    except Exception as e:
        print(f"Error fetching {url}: {e}", file=sys.stderr)
        return []

def unix_to_cdmx(ts_str: str) -> datetime:
    ts = int(ts_str)
    return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(TZ)

def format_dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d/%H:%M:%S")

def process_programs(programs: list) -> list:
    if not programs:
        return []

    programs = sorted(programs, key=lambda p: int(p.get("time_GMT", 0)))
    result = []

    for i, prog in enumerate(programs):
        name = prog.get("name") or "Sin título"
        ts_str = prog.get("time_GMT")
        if not ts_str:
            continue

        start_dt = unix_to_cdmx(ts_str)

        if i + 1 < len(programs) and programs[i + 1].get("time_GMT"):
            end_dt = unix_to_cdmx(programs[i + 1]["time_GMT"])
        else:
            end_dt = start_dt + timedelta(minutes=60)

        result.append({
            "titulo": name,
            "sta": format_dt(start_dt),
            "end": format_dt(end_dt)
        })

    return result

def main():
    now = datetime.now(TZ)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    days = [today + timedelta(days=i) for i in range(3)]

    all_programs = []
    for day in days:
        all_programs.extend(fetch_day(day))

    epg = process_programs(all_programs)

    seen = set()
    unique = []
    for item in epg:
        key = (item["titulo"], item["sta"])
        if key not in seen:
            seen.add(key)
            unique.append(item)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(unique, f, indent=2, ensure_ascii=False)

    print(f"Guardado {len(unique)} programas en {OUTPUT_FILE}", file=sys.stderr)

if __name__ == "__main__":
    main()
