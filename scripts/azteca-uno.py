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

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://fispy.com/",
    "Origin": "https://fispy.com"
}

def fetch_range(from_ms: int, to_ms: int) -> list:
    url = f"{BASE_URL}?from={from_ms}&to={to_ms}"
    print(f"Fetching {url}", file=sys.stderr)
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.load(resp)
            return data if isinstance(data, list) else []
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return []

def ms_to_cdmx(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).astimezone(TZ)

def format_dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d/%H:%M:%S")

def process_station(station: dict) -> list:
    programs = sorted(station.get("schedulePrograms") or [], key=lambda p: p.get("airDateTime", 0))
    result = []
    for prog in programs:
        title = (prog.get("program") or {}).get("title") or "Sin título"
        start_ms = prog.get("airDateTime")
        end_ms = prog.get("endAirDateTime")
        if not start_ms:
            continue
        start_dt = ms_to_cdmx(start_ms)
        end_dt = ms_to_cdmx(end_ms) if end_ms else start_dt + timedelta(minutes=60)
        result.append({
            "titulo": title,
            "sta": format_dt(start_dt),
            "end": format_dt(end_dt)
        })
    return result

def main():
    now = datetime.now(TZ)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Varios días (ayer + hoy + próximos), como el otro script
    days = [today + timedelta(days=i) for i in range(-1, 7)]

    all_stations = []
    for day in days:
        from_ms = int(day.timestamp() * 1000)
        to_ms = int((day + timedelta(days=1)).timestamp() * 1000)
        stations = fetch_range(from_ms, to_ms)
        all_stations.extend(stations)

    # Buscar la estación objetivo (puede venir repetida por día)
    targets = [st for st in all_stations if st.get("callSign") == TARGET_CALLSIGN]
    if not targets:
        print(f"No se encontró {TARGET_CALLSIGN}", file=sys.stderr)
        return

    print(f"Encontradas {len(targets)} entradas de {targets[0].get('name')} ({TARGET_CALLSIGN})", file=sys.stderr)

    # Juntar todos los programas
    epg = []
    for target in targets:
        epg.extend(process_station(target))

    # Deduplicar
    seen = set()
    unique = []
    for item in epg:
        key = (item["titulo"], item["sta"])
        if key not in seen:
            seen.add(key)
            unique.append(item)

    # Ordenar por hora
    unique.sort(key=lambda x: x["sta"])

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(unique, f, indent=2, ensure_ascii=False)

    print(f"Guardado {len(unique)} programas en {OUTPUT_FILE}", file=sys.stderr)

if __name__ == "__main__":
    main()
