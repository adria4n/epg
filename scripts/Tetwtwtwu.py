#!/usr/bin/env python3
"""
EPG Megacable - Azteca Uno (101)
Usa la página del canal de gato.tv (horas exactas)
"""

import json
import urllib.request
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import sys

TZ = ZoneInfo("America/Mexico_City")
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
SLUG = "azteca_uno"          # Canal 101
OUTPUT_FILE = "aztec.json"

def fetch(url: str) -> str:
    print(f"Descargando {url}...", file=sys.stderr)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read().decode("utf-8", errors="replace")

def parse_channel_day(html: str, day: datetime) -> list[dict]:
    programs = []
    rows = re.findall(
        r'<tr class="tbl_EPG_row[^"]*">\s*'
        r'<td[^>]*>.*?datetime="(\d{2}:\d{2})".*?</td>\s*'
        r'<td[^>]*>.*?datetime="(\d{2}:\d{2})".*?</td>\s*'
        r'<td[^>]*>.*?<span>([^<]+)</span>',
        html,
        re.DOTALL | re.IGNORECASE
    )

    current_day = day
    for start_t, end_t, title in rows:
        title = title.strip()
        if not title:
            continue
        try:
            sh, sm = map(int, start_t.split(":"))
            eh, em = map(int, end_t.split(":"))

            start = current_day.replace(hour=sh, minute=sm, second=0, microsecond=0)
            end = current_day.replace(hour=eh, minute=em, second=0, microsecond=0)

            if end <= start:
                end += timedelta(days=1)

            # Ajuste de medianoche
            if programs and start.hour < 6 and programs[-1].get("_start") and programs[-1]["_start"].hour >= 20:
                start += timedelta(days=1)
                if end.date() == start.date() - timedelta(days=1):
                    end += timedelta(days=1)
                current_day = start

            programs.append({
                "titulo": title,
                "sta": start.strftime("%Y-%m-%d/%H:%M"),
                "end": end.strftime("%Y-%m-%d/%H:%M"),
                "_start": start,
            })
        except Exception:
            continue

    for p in programs:
        p.pop("_start", None)
    return programs

def main():
    all_programs = []
    today = datetime.now(TZ).date()

    for i in range(-1, 7):
        d = today + timedelta(days=i)
        date_str = d.strftime("%Y-%m-%d")
        url = f"https://www.gatotv.com/canal/{SLUG}/{date_str}"
        try:
            html = fetch(url)
            day_dt = datetime.combine(d, datetime.min.time(), tzinfo=TZ)
            progs = parse_channel_day(html, day_dt)
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
