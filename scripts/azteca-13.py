#!/usr/bin/env python3

import json
import urllib.request
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import sys

CHANNEL_SLUG = "azteca_uno"
BASE_URL = f"https://www.gatotv.com/canal/{CHANNEL_SLUG}"
TZ = ZoneInfo("America/Mexico_City")
OUTPUT_FILE = "azteca-13.json"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

def fetch_page(date_str: str | None = None) -> str:
    url = BASE_URL if not date_str else f"{BASE_URL}/{date_str}"
    print(f"Descargando {url}...", file=sys.stderr)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read().decode("utf-8", errors="replace")

def parse_items(html: str, day: datetime) -> list[dict]:
    # Captura start, end y título de cada fila de programa
    pattern = re.compile(
        r'<tr class="tbl_EPG_row[^"]*">\s*'
        r'<td[^>]*>\s*<div[^>]*>\s*<time datetime="(\d{2}:\d{2})"[^>]*>.*?</time>.*?</div>\s*</td>\s*'
        r'<td[^>]*>\s*<div[^>]*>\s*<time datetime="(\d{2}:\d{2})"[^>]*>.*?</time>.*?</div>\s*</td>\s*'
        r'<td[^>]*>\s*<div[^>]*>\s*<div class="div_program_title_on_channel">\s*<span>([^<]+)</span>',
        re.DOTALL | re.IGNORECASE
    )

    programs = []
    base_date = day.date()

    for match in pattern.finditer(html):
        start_hm, end_hm, title = match.groups()
        try:
            sh, sm = map(int, start_hm.split(":"))
            eh, em = map(int, end_hm.split(":"))

            start = datetime(base_date.year, base_date.month, base_date.day,
                             sh, sm, tzinfo=TZ)
            end = datetime(base_date.year, base_date.month, base_date.day,
                           eh, em, tzinfo=TZ)

            # Si el fin es menor o igual al inicio → cruza medianoche
            if end <= start:
                end += timedelta(days=1)

            # Si el programa empieza después de las 20:00 y el fin es de madrugada,
            # el inicio pertenece al día anterior de la página
            if sh >= 20 and eh < 6:
                start -= timedelta(days=1)

            programs.append({
                "titulo": title.strip(),
                "sta": start.strftime("%Y-%m-%d/%H:%M"),
                "end": end.strftime("%Y-%m-%d/%H:%M"),
            })
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
            html = fetch_page(date_str if i != 0 else None)
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
