#!/usr/bin/env python3

import json
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import sys

BASE_URL = "https://api.fispy.com/api/v1/guide/cards"
TZ = ZoneInfo("America/Mexico_City")
OUTPUT_FILE = "azteca-uno.json"
TARGET_CALLSIGN = "AZDELAY"

def fetch_range(from_ms: int, to_ms: int) -> list:
    url = f"{BASE_URL}?from={from_ms}&to={to_ms}"
    print(f"Fetching {url}", file=sys.stderr)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.load(resp)
            return data if isinstance(data, list) else []
    except Exception as e:
        print(f"Error fetching {url}: {e}", file=sys.stderr)
        return []

def ms_to_cdmx(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).astimezone(TZ)

def format_dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d/%H:%M:%S")

def process_station(station: dict) -> list:
    programs = station.get("schedulePrograms") or []
    if not programs:
        return []

    programs = sorted(programs, key=lambda p: p.get("airDateTime", 0))
    result = []

    for prog in programs:
        title = (prog.get("program") or {}).get("title") or "Sin título"
        start_ms = prog.get("airDateTime")
        end_ms = prog.get("endAirDateTime")

        if not start_ms:
            continue

        start_dt = ms_to_cdmx(start_ms)
        if end_ms:
            end_dt = ms_to_cdmx(end_ms)
        else:
            end_dt = start_dt + timedelta(minutes=60)

        result.append({
            "titulo": title,
            "sta": format_dt(start_dt),
            "end": format_dt(end_dt)
        })

    return result

def main():
    now = datetime.now(TZ)
    start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    end = (now + timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)

    from_ms = int(start.timestamp() * 1000)
    to_ms = int(end.timestamp() * 1000)

    stations = fetch_range(from_ms, to_ms)

    target = None
    for st in stations:
        if st.get("callSign") == TARGET_CALLSIGN:
            target = st
            break

    if not target:
        print(f"No se encontró estación con callSign {TARGET_CALLSIGN}", file=sys.stderr)
        return

    print(f"Encontrada: {target.get('name')} ({target.get('callSign')})", file=sys.stderr)

    epg = process_station(target)

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
