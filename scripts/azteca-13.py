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

def to_24h(t: str) -> tuple[int, int]:
    t = t.strip().upper()
    m = re.match(r'(\d{1,2}):(\d{2})\s*(AM|PM)', t)
    if not m:
        raise ValueError(t)
    h, mi, ap = int(m.group(1)), int(m.group(2)), m.group(3)
    if ap == "AM":
        h = 0 if h == 12 else h
    else:
        h = h if h == 12 else h + 12
    return h, mi

def fetch_page(date_str: str) -> str:
    url = f"{BASE_URL}/{date_str}"
    print(f"Descargando {url}...", file=sys.stderr)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read().decode("utf-8", errors="replace")

def parse_items(html: str, day: datetime) -> list[dict]:
    pattern = re.compile(
        r'<time[^>]*>\s*([^<]+?)\s*</time>.*?<time[^>]*>\s*([^<]+?)\s*</time>.*?<span[^>]*>([^<]+)</span>',
        re.DOTALL | re.IGNORECASE
    )
    
    programs = []
    
    for match in pattern.finditer(html):
        start_txt, end_txt, title = match.groups()
        title = title.strip()
        if not title:
            continue
        
        try:
            sh, sm = to_24h(start_txt)
            eh, em = to_24h(end_txt)
            
            start = day.replace(hour=sh, minute=sm, second=0, microsecond=0)
            end = day.replace(hour=eh, minute=em, second=0, microsecond=0)
            
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
