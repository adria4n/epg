#!/usr/bin/env python3

import json
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from zoneinfo import ZoneInfo
import sys

EPG_URL = "https://www.open-epg.com/files/mexico2.xml"
CHANNEL_ID = "STARLINK.mx"
TZ_TARGET = ZoneInfo("America/Mexico_City")
OUTPUT_FILE = "starlink.json"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

def fetch_xml() -> str:
    print(f"Descargando {EPG_URL}...", file=sys.stderr)
    req = urllib.request.Request(EPG_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", errors="replace")

def parse_epg(xml_data: str) -> list[dict]:
    root = ET.fromstring(xml_data)
    programs = []

    for prog in root.findall("programme"):
        if prog.get("channel") != CHANNEL_ID:
            continue

        title_el = prog.find("title")
        title = title_el.text.strip() if title_el is not None and title_el.text else "Sin título"

        start_raw = prog.get("start", "")
        stop_raw = prog.get("stop", "")

        if not start_raw or not stop_raw:
            continue

        try:
            start_utc = datetime.strptime(start_raw, "%Y%m%d%H%M%S %z")
            end_utc = datetime.strptime(stop_raw, "%Y%m%d%H%M%S %z")

            start = start_utc.astimezone(TZ_TARGET)
            end = end_utc.astimezone(TZ_TARGET)

            programs.append({
                "titulo": title,
                "sta": start.strftime("%Y-%m-%d/%H:%M"),
                "end": end.strftime("%Y-%m-%d/%H:%M"),
            })
        except Exception:
            continue

    return programs

def main():
    try:
        xml_data = fetch_xml()
        programs = parse_epg(xml_data)
        programs.sort(key=lambda x: x["sta"])

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(programs, f, indent=2, ensure_ascii=False)

        print(f"Listo: {len(programs)} programas en {OUTPUT_FILE}", file=sys.stderr)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
