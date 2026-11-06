#!/usr/bin/env python3

import json
import urllib.request
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import sys
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

CANALES_URL = "https://dl.dropboxusercontent.com/scl/fi/x4wyqmstcso2k4qu0uonm/formula-tv.txt?rlkey=s2kh6yhjoxzn6oo9ijidjy488"
TZ = ZoneInfo("America/Mexico_City")
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
BASE = "https://www.formulatv.com/mx/programacion/"

DAYS = {
    -1: "ayer",
    0: "",
    1: "manana",
    2: "pasadomanana",
}

def load_canales():
    with urllib.request.urlopen(CANALES_URL) as resp:
        return json.loads(resp.read().decode("utf-8"))

def fetch(url: str) -> str:
    print(f"Descargando {url}...", file=sys.stderr)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read().decode("utf-8", errors="replace")

def parse_duration(dur_text: str) -> timedelta:
    if not dur_text:
        return timedelta(0)
    dur_text = dur_text.lower().strip()
    hours = minutes = 0
    h_match = re.search(r'(\d+)\s*h', dur_text)
    m_match = re.search(r'(\d+)\s*min', dur_text)
    if h_match:
        hours = int(h_match.group(1))
    if m_match:
        minutes = int(m_match.group(1))
    return timedelta(hours=hours, minutes=minutes)

def extract_programs(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    items = soup.select("ol.pmx-tl > li.pmx-it")
    programs = []

    for li in items:
        time_el = li.select_one("time")
        h3 = li.select_one("h3")
        small = li.select_one("small")

        if not (time_el and h3):
            continue

        title = h3.get_text(strip=True)
        start_iso = time_el.get("datetime")
        if not (title and start_iso):
            continue

        try:
            start = datetime.fromisoformat(start_iso)
        except Exception:
            continue

        duration = parse_duration(small.get_text(strip=True) if small else "")
        end = start + duration

        programs.append({
            "titulo": title,
            "sta": start.strftime("%Y-%m-%d/%H:%M"),
            "end": end.strftime("%Y-%m-%d/%H:%M"),
            "_start": start,
        })

    return programs

def scrape(channel, outfile):
    all_programs = []
    today = datetime.now(TZ).date()
    channel_base = f"{BASE}{channel}/"

    for offset, slug in DAYS.items():
        d = today + timedelta(days=offset)
        url = f"{channel_base}{slug}/" if slug else channel_base
        try:
            html = fetch(url)
            progs = extract_programs(html)
            all_programs.extend(progs)
            print(f"  {channel} {d}: {len(progs)} programas", file=sys.stderr)
        except Exception as e:
            print(f"  Error en {channel} {d}: {e}", file=sys.stderr)

    all_programs.sort(key=lambda x: x["_start"])
    seen = set()
    unique = []
    for p in all_programs:
        key = p["sta"]
        if key not in seen:
            seen.add(key)
            p.pop("_start", None)
            unique.append(p)

    with open(outfile, "w", encoding="utf-8") as f:
        json.dump(unique, f, indent=2, ensure_ascii=False)

    print(f"Listo: {len(unique)} programas en {outfile}", file=sys.stderr)
    return len(unique)

def main():
    canales = load_canales()
    print(f"Procesando {len(canales)} canales en paralelo...", file=sys.stderr)

    with ThreadPoolExecutor(max_workers=min(8, len(canales))) as executor:
        futures = {
            executor.submit(scrape, canal.get("id", ""), canal.get("json", f"{canal.get('id', '')}.json")): canal
            for canal in canales
        }
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                canal = futures[future]
                print(f"Error en canal {canal.get('id')}: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
