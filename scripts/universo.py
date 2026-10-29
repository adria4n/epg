#!/usr/bin/env python3

import json
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import sys

URL = "https://www.open-epg.com/files/unitedstates1.xml"
CHANNEL = "UNVSO.us"
TZ = ZoneInfo("America/Mexico_City")
OUTPUT_FILE = "universo.json"

def parse_epg_time(s: str) -> datetime:
    dt_str = s[:14]
    dt = datetime.strptime(dt_str, "%Y%m%d%H%M%S")
    return dt.replace(tzinfo=timezone.utc)

def fetch_xml() -> bytes:
    print(f"Descargando {URL}...", file=sys.stderr)
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()

def main():
    xml_data = fetch_xml()
    root = ET.fromstring(xml_data)

    programmes = []
    for prog in root.findall("programme"):
        if prog.get("channel") != CHANNEL:
            continue

        title = (prog.findtext("title") or "Sin título").strip()
        start_utc = parse_epg_time(prog.get("start"))
        stop_utc = parse_epg_time(prog.get("stop"))

        start_cdmx = start_utc.astimezone(TZ)
        stop_cdmx = stop_utc.astimezone(TZ)

        programmes.append({
            "titulo": title,
            "sta": start_cdmx.strftime("%Y-%m-%d/%H:%M:%S"),
            "end": stop_cdmx.strftime("%Y-%m-%d/%H:%M:%S")
        })

    programmes.sort(key=lambda x: x["sta"])

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(programmes, f, indent=2, ensure_ascii=False)

    print(f"Listo: {len(programmes)} programas guardados en {OUTPUT_FILE}", file=sys.stderr)

if __name__ == "__main__":
    main()
