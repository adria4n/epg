#!/usr/bin/env python3

import json
import urllib.request
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import sys
from bs4 import BeautifulSoup

TZ = ZoneInfo("America/Mexico_City")
OUTPUT_FILE = "sony-mexico.json"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
BASE = "https://www.gatotv.com/canal/sony_mexico"

DAYS_RANGE = range(-1, 7)

def fetch(url: str) -> str:
    print(f"Descargando {url}...", file=sys.stderr)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read().decode("utf-8", errors="replace")

def parse_time_12h(time_str: str) -> tuple[int, int] | None:
    time_str = time_str.strip().upper()
    m = re.match(r'(\d{1,2}):(\d{2})\s*(AM|PM)', time_str)
    if not m:
        return None
    hour, minute, ampm = int(m.group(1)), int(m.group(2)), m.group(3)
    if ampm == "PM" and hour != 12:
        hour += 12
    if ampm == "AM" and hour == 12:
        hour = 0
    return hour, minute

def get_title(row) -> str:
    # Formato normal
    title_el = row.select_one(".div_program_title_on_channel")
    episode_el = row.select_one(".div_episode_programa_on_channel strong")
    if title_el:
        title = title_el.get_text(strip=True)
        if episode_el:
            ep = episode_el.get_text(strip=True)
            if ep:
                title = f"{title} {ep}"
        return title
    # Formato alterno (películas con link/imagen)
    a = row.select_one("td a[title]")
    if a and a.get("title"):
        return a["title"].strip()
    # Fallback
    cells = row.find_all("td")
    if len(cells) >= 3:
        return re.sub(r'\s+', ' ', cells[2].get_text(" ", strip=True)).strip()
    return ""

def extract_programs(html: str, page_date: datetime) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    programs = []
    seen = set()

    rows = soup.select("tr.tbl_EPG_row, tr.tbl_EPG_rowAlternate")
    for row in rows:
        times = row.find_all("time")
        if len(times) < 2:
            continue

        start_str = times[0].get_text(strip=True)
        end_str = times[1].get_text(strip=True)
        title = get_title(row)

        if not start_str or not title:
            continue

        key = (start_str, end_str, title)
        if key in seen:
            continue
        seen.add(key)

        start_hm = parse_time_12h(start_str)
        end_hm = parse_time_12h(end_str)
        if not start_hm:
            continue

        sh, sm = start_hm
        eh, em = end_hm if end_hm else (sh, sm)

        crosses_midnight = (sh >= 12 and eh < 12) or (eh < sh)
        if crosses_midnight and sh >= 18:
            start_date = page_date - timedelta(days=1)
        else:
            start_date = page_date

        start = start_date.replace(hour=sh, minute=sm, second=0, microsecond=0)
        end_date = start_date + timedelta(days=1) if (eh < sh or (eh == sh and em <= sm)) else start_date
        end = end_date.replace(hour=eh, minute=em, second=0, microsecond=0)

        programs.append({
            "titulo": title,
            "sta": start.strftime("%Y-%m-%d/%H:%M"),
            "end": end.strftime("%Y-%m-%d/%H:%M"),
            "_start": start,
        })

    return programs

def main():
    all_programs = []
    today = datetime.now(TZ).date()

    for offset in DAYS_RANGE:
        d = today + timedelta(days=offset)
        date_str = d.strftime("%Y-%m-%d")
        url = f"{BASE}/{date_str}" if offset != 0 else BASE

        try:
            html = fetch(url)
            day_dt = datetime.combine(d, datetime.min.time(), tzinfo=TZ)
            progs = extract_programs(html, day_dt)
            all_programs.extend(progs)
            print(f"  {date_str}: {len(progs)} programas", file=sys.stderr)
        except Exception as e:
            print(f"  Error en {date_str}: {e}", file=sys.stderr)

    all_programs.sort(key=lambda x: x["_start"])
    seen = set()
    unique = []
    for p in all_programs:
        key = p["sta"]
        if key not in seen:
            seen.add(key)
            p.pop("_start", None)
            unique.append(p)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(unique, f, indent=2, ensure_ascii=False)

    print(f"Listo: {len(unique)} programas en {OUTPUT_FILE}", file=sys.stderr)

if __name__ == "__main__":
    main()
