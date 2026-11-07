#!/usr/bin/env python3

import json
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo
import sys

API_URL = "https://epg.tbxapis.com/v0/epg/external/entries"
TZ = ZoneInfo("America/Mexico_City")

CHANNEL_FILES = {
    "1610": "dsports.json",
    "1612": "dsports-2.json",
    "1613": "dsports-plus.json",
}

def fetch_epg() -> dict:
    print(f"Fetching {API_URL}", file=sys.stderr)
    req = urllib.request.Request(API_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.load(resp)
    if not data.get("ok") or "data" not in data:
        raise RuntimeError(f"API error: {data.get('error')}")
    return data["data"]

def parse_iso(dt_str: str) -> datetime:
    # "2026-11-08T11:00:00+00:00" → aware datetime in Mexico City
    dt = datetime.fromisoformat(dt_str)
    return dt.astimezone(TZ)

def format_dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d/%H:%M")

def process_channel(programs: list) -> list:
    if not programs:
        return []
    # Ordenar por hora de inicio
    programs = sorted(programs, key=lambda p: p["StartDate"])
    result = []
    seen = set()
    for prog in programs:
        title = prog.get("Title") or "Sin título"
        try:
            start_dt = parse_iso(prog["StartDate"])
            end_dt = parse_iso(prog["EndDate"])
        except Exception:
            continue
        sta = format_dt(start_dt)
        end = format_dt(end_dt)
        key = (title, sta)
        if key not in seen:
            seen.add(key)
            result.append({"titulo": title, "sta": sta, "end": end})
    return result

def main():
    data = fetch_epg()
    all_programs = data.get("programs") or []

    # Agrupar por canal
    by_channel = {ch: [] for ch in CHANNEL_FILES}
    for prog in all_programs:
        ch = str(prog.get("ChannelNum", "")).strip()
        if ch in by_channel:
            by_channel[ch].append(prog)

    for ch, filename in CHANNEL_FILES.items():
        epg = process_channel(by_channel[ch])
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(epg, f, indent=2, ensure_ascii=False)
        print(f"{filename}: {len(epg)} programas", file=sys.stderr)

if __name__ == "__main__":
    main()
