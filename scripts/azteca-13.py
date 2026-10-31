#!/usr/bin/env python3

import json
import urllib.request
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import sys

BASE_URL = "https://www.gatotv.com/canal/azteca_uno"
TZ = ZoneInfo("America/Mexico_City")
OUTPUT_FILE = "azteca-13.json"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

def fetch_page(date_str: str) -> str:
    url = f"{BASE_URL}/{date_str}"
    print(f"Descargando {url}...", file=sys.stderr)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read().decode("utf-8", errors="replace")

def parse_items(html: str, day: datetime) -> list[dict]:
    pattern = re.compile(
        r'<time datetime="(\d{2}:\d{2})"[^>]*>.*?</time>\s*</div>\s*</td>\s*<td[^>]*>\s*<div[^>]*>\s*<time datetime="(\d{2}:\d{2})"[^>]*>.*?</time>.*?<span[^>]*>([^<]+)</span>',
        re.DOTALL | re.IGNORECASE
    )
    
    programs = []
    switched = False
    
    for match in pattern.finditer(html):
        start_hms, end_hms, title = match.groups()
        title = title.strip()
        if not title:
            continue
        
        try:
            sh, sm = map(int, start_hms.split(":"))
            eh, em = map(int, end_hms.split(":"))
            
            if not switched and sh < 12:
                switched = True
            
            program_day = day if switched else day - timedelta(days=1)
            
            start = program_day.replace(hour=sh, minute=sm, second=0, microsecond=0, tzinfo=TZ) - timedelta(hours=2)
            end = program_day.replace(hour=eh, minute=em, second=0, microsecond=0, tzinfo=TZ) - timedelta(hours=2)
            
            if end <= start:
                end += timedelta(days=1)
            
            programs.append({
                "titulo": title,
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
            html = fetch_page(date_str)
            base = datetime.combine(d, datetime.min.time(), tzinfo=TZ)
            progs = parse_items(html, base)
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
