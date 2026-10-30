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
OUTPUT_FILE = "azteca-uno.json"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
UTC_OFFSET = -360  # CST

def fetch_page(date_str: str) -> str:
    url = f"{BASE_URL}/{date_str}/{UTC_OFFSET}"
    print(f"Descargando {url}...", file=sys.stderr)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read().decode("utf-8", errors="replace")

def parse_items(html: str, day: datetime) -> list[dict]:
    times = re.findall(r'<span class="time">\s*([^<]+?)\s*</span>', html)
    titles = re.findall(r'<h2>\s*([^<]+?)\s*</h2>', html)

    programs = []
    current_day = day

    for i, (t, title) in enumerate(zip(times, titles)):
        try:
            hour, minute = map(int, t.split(":"))
            start = current_day.replace(hour=hour, minute=minute, second=0, microsecond=0)

            # Si el horario es de madrugada y ya pasamos de medianoche en la lista
            if i > 0 and hour < 6 and programs and programs[-1]["start"].hour >= 20:
                start += timedelta(days=1)
                current_day = start

            # End = inicio del siguiente, o +60 min si es el último
            if i + 1 < len(times):
                next_h, next_m = map(int, times[i + 1].split(":"))
                end = current_day.replace(hour=next_h, minute=next_m, second=0, microsecond=0)
                if end <= start:
                    end += timedelta(days=1)
            else:
                end = start + timedelta(minutes=60)

            programs.append({
                "titulo": title.strip(),
                "sta": start.strftime("%Y-%m-%d/%H:%M:%S"),
                "end": end.strftime("%Y-%m-%d/%H:%M:%S"),
                "start": start,  # temporal para cálculo
            })
        except Exception:
            continue

    # Limpiar campo temporal
    for p in programs:
        p.pop("start", None)

    return programs

def main():
    all_programs = []
    today = datetime.now(TZ).date()

    for i in range(-1, 7):  # ayer + 6 días
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
