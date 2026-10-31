#!/usr/bin/env python3
"""
Scraper de programación Azteca Uno desde GatoTV.com
Lee las horas en formato 12h (AM/PM) y las convierte a 24h
"""

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

def to_24h(time_str: str) -> tuple[int, int]:
    """Convierte '9:00 PM' o '12:30 AM' a (hora, minuto) en 24h"""
    time_str = time_str.strip().upper()
    m = re.match(r'(\d{1,2}):(\d{2})\s*(AM|PM)', time_str)
    if not m:
        raise ValueError(f"Formato no reconocido: {time_str}")
    h, mi, ampm = int(m.group(1)), int(m.group(2)), m.group(3)
    if ampm == "AM":
        if h == 12:
            h = 0
    else:  # PM
        if h != 12:
            h += 12
    return h, mi

def fetch_page(date_str: str) -> str:
    url = f"{BASE_URL}/{date_str}"
    print(f"Descargando {url}...", file=sys.stderr)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read().decode("utf-8", errors="replace")

def parse_items(html: str, day: datetime) -> list[dict]:
    """
    Extrae programas leyendo el texto visible de las horas (AM/PM)
    """
    # Captura: hora inicio (texto), hora fin (texto), título
    pattern = re.compile(
        r'<time[^>]*>\s*([^<]+?)\s*</time>.*?'
        r'<time[^>]*>\s*([^<]+?)\s*</time>.*?'
        r'<span[^>]*>([^<]+)</span>',
        re.DOTALL | re.IGNORECASE
    )
    
    programs = []
    current_day = day
    
    for match in pattern.finditer(html):
        start_txt, end_txt, title = match.groups()
        title = title.strip()
        if not title or title.lower() in ("programa", "hora"):
            continue
        
        try:
            sh, sm = to_24h(start_txt)
            eh, em = to_24h(end_txt)
            
            start = current_day.replace(hour=sh, minute=sm, second=0, microsecond=0)
            
            # Cruce de medianoche
            if programs and programs[-1].get("_start"):
                prev = programs[-1]["_start"]
                if sh < 6 and prev.hour >= 20:
                    start += timedelta(days=1)
                    current_day = start
            
            end = current_day.replace(hour=eh, minute=em, second=0, microsecond=0)
            if end <= start:
                end += timedelta(days=1)
            
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
        try:
            html = fetch_page(date_str)
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
