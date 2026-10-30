#!/usr/bin/env python3

import json
import urllib.request
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import sys

CHANNEL = "azteca_uno"
BASE_URL = f"https://www.gatotv.com/canal/{CHANNEL}"
TZ_TARGET = ZoneInfo("America/Mexico_City")
OUTPUT_FILE = "azteca-uno.json"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

def fetch_page(date_str: str | None = None) -> str:
    url = BASE_URL if not date_str else f"{BASE_URL}/{date_str}"
    print(f"Descargando {url}...", file=sys.stderr)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read().decode("utf-8", errors="replace")

def parse_items(html: str, page_date: datetime.date) -> list[dict]:
    # Extraer filas de programación
    rows = re.findall(
        r'<tr class="tbl_EPG_row(?:Alternate)?">(.*?)</tr>',
        html,
        re.DOTALL | re.I,
    )

    programs = []
    for row in rows:
        # Extraer tiempos (start y end)
        times = re.findall(r'<time datetime="(\d{2}:\d{2})"', row)
        if len(times) < 2:
            continue

        start_t = times[0]
        end_t = times[1]

        # Extraer título
        title_match = re.search(r'<span[^>]*>([^<]+)</span>', row)
        title = title_match.group(1).strip() if title_match else "Sin título"

        try:
            start_h, start_m = map(int, start_t.split(":"))
            end_h, end_m = map(int, end_t.split(":"))

            start = datetime(
                page_date.year, page_date.month, page_date.day,
                start_h, start_m, tzinfo=TZ_TARGET
            )

            # Si la hora de fin es menor que la de inicio → cruza medianoche
            end_date = page_date
            if (end_h, end_m) < (start_h, start_m):
                end_date = page_date + timedelta(days=1)

            end = datetime(
                end_date.year, end_date.month, end_date.day,
                end_h, end_m, tzinfo=TZ_TARGET
            )

            programs.append({
                "titulo": title,
                "sta": start.strftime("%Y-%m-%d/%H:%M:%S"),
                "end": end.strftime("%Y-%m-%d/%H:%M:%S"),
            })
        except Exception:
            continue

    return programs

def main():
    all_programs = []
    today = datetime.now(TZ_TARGET).date()

    for i in range(-1, 8):
        d = today + timedelta(days=i)
        date_str = d.strftime("%Y-%m-%d")
        try:
            html = fetch_page(date_str)
            progs = parse_items(html, d)
            all_programs.extend(progs)
            print(f"  {date_str}: {len(progs)} programas", file=sys.stderr)
        except Exception as e:
            print(f"  Error en {date_str}: {e}", file=sys.stderr)

    all_programs.sort(key=lambda x: x["sta"])
    seen = set()
    unique = []
    for p in all_programs:
        key = p["sta"]
        if key not in seen:
            seen.add(key)
            unique.append(p)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(unique, f, indent=2, ensure_ascii=False)

    print(f"Listo: {len(unique)} programas en {OUTPUT_FILE}", file=sys.stderr)

if __name__ == "__main__":
    main()
