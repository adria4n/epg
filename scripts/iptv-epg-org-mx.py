#!/usr/bin/env python3

import json
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from zoneinfo import ZoneInfo
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

CANALES_URL = "https://dl.dropbox.com/scl/fi/kwulllm1dc8rotb1249oa/iptv-epg-org-mx.txt?rlkey=fw2pbn7y8hp7bqic9jk17wg3r"
EPG_URL = "https://iptv-epg.org/files/epg-mx.xml"
TZ_TARGET = ZoneInfo("America/Mexico_City")
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

def load_canales():
    with urllib.request.urlopen(CANALES_URL) as resp:
        return json.loads(resp.read().decode("utf-8"))

def fetch_xml() -> str:
    print(f"Descargando {EPG_URL}...", file=sys.stderr)
    req = urllib.request.Request(EPG_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", errors="replace")

def parse_epg(xml_data: str, channel_id: str) -> list[dict]:
    root = ET.fromstring(xml_data)
    programs = []

    for prog in root.findall("programme"):
        if prog.get("channel") != channel_id:
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

def process_canal(xml_data: str, canal: dict):
    channel_id = canal.get("id", "")
    outfile = canal.get("json", f"{channel_id}.json")
    programs = parse_epg(xml_data, channel_id)
    programs.sort(key=lambda x: x["sta"])
    with open(outfile, "w", encoding="utf-8") as f:
        json.dump(programs, f, indent=2, ensure_ascii=False)
    print(f"Listo: {len(programs)} programas en {outfile}", file=sys.stderr)
    return len(programs)

def main():
    canales = load_canales()
    try:
        xml_data = fetch_xml()
        print(f"Procesando {len(canales)} canales en paralelo...", file=sys.stderr)

        with ThreadPoolExecutor() as executor:
            futures = {
                executor.submit(process_canal, xml_data, canal): canal
                for canal in canales
            }
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    canal = futures[future]
                    print(f"Error en canal {canal.get('id')}: {e}", file=sys.stderr)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
