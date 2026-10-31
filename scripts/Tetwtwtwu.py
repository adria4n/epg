#!/usr/bin/env python3
"""
EPG Megacable desde grilla cada 30 min
Horas 100% de la URL. Filtra por número de canal (default 101)
"""

import json
import urllib.request
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import sys

TZ = ZoneInfo("America/Mexico_City")
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

def fetch(url: str) -> str:
    print(f"Descargando {url}...", file=sys.stderr)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read().decode("utf-8", errors="replace")

def extract_starting(html: str, channel_num: str, window_start: datetime):
    pattern = re.compile(
        r'<div class="div_channel_number">\s*' + re.escape(channel_num) + r'\s*</div>.*?</tr>',
        re.DOTALL | re.IGNORECASE
    )
    m = pattern.search(html)
    if not m:
        return None

    block = m.group(0)
    tds = re.findall(r'<td colspan="(\d+)"[^>]*>(.*?)</td>', block, re.DOTALL)

    for colspan, content in tds:
        if "PG_ArrowLeft" in content:
            continue
        text = re.sub(r"<span[^>]*>.*?</span>", "", content)
        text = re.sub(r"<[^>]+>", " ", text)
        title = " ".join(text.split()).strip()
        if not title:
            continue

        minutes = int(colspan)
        start = window_start
        end = start + timedelta(minutes=minutes)
        return {
            "titulo": title,
            "sta": start.strftime("%Y-%m-%d/%H:%M"),
            "end": end.strftime("%Y-%m-%d/%H:%M"),
        }
    return None

def main():
    channel_num = sys.argv[1] if len(sys.argv) > 1 else "101"
    out_file = sys.argv[2] if len(sys.argv) > 2 else f"canal-{channel_num}.json"

    all_programs = []
    today = datetime.now(TZ).date()

    slots = [f"{h:02d}-{m:02d}" for h in range(24) for m in (0, 30)]

    for i in range(-1, 7):
        d = today + timedelta(days=i)
        date_str = d.strftime("%Y-%m-%d")
        day_dt = datetime.combine(d, datetime.min.time(), tzinfo=TZ)

        for slot in slots:
            hh, mm = map(int, slot.split("-"))
            window_start = day_dt.replace(hour=hh, minute=mm)
            url = f"https://www.gatotv.com/guia_tv/megacable/{date_str}/{slot}"
            try:
                html = fetch(url)
                prog = extract_starting(html, channel_num, window_start)
                if prog:
                    all_programs.append(prog)
                    print(f"  {date_str} {slot}: {prog['titulo']}", file=sys.stderr)
            except Exception as e:
                print(f"  Error {date_str} {slot}: {e}", file=sys.stderr)

    all_programs.sort(key=lambda x: x["sta"])
    seen = set()
    unique = [p for p in all_programs if not (p["sta"] in seen or seen.add(p["sta"]))]

    # Limpiar solapes del mismo título
    cleaned = []
    for p in unique:
        if not cleaned or not (p["titulo"] == cleaned[-1]["titulo"] and p["sta"] < cleaned[-1]["end"]):
            cleaned.append(p)

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, indent=2, ensure_ascii=False)

    print(f"Listo: {len(cleaned)} programas en {out_file}", file=sys.stderr)

if __name__ == "__main__":
    main()
