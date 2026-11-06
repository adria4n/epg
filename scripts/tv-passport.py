#!/usr/bin/env python3

import json
import urllib.request
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

CANALES_URL = "https://dl.dropboxusercontent.com/scl/fi/a2blnq1tk33ebl4vdo2pb/tv-passport.txt?rlkey=cgacvhhoouph3w66y4wkkmr5x"
TZ_TARGET = ZoneInfo("America/Mexico_City")
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

def load_canales():
    with urllib.request.urlopen(CANALES_URL) as resp:
        return json.loads(resp.read().decode("utf-8"))

def fetch_page(base_url: str, date_str: str | None = None) -> str:
    url = base_url if not date_str else f"{base_url}/{date_str}"
    print(f"Descargando {url}...", file=sys.stderr)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read().decode("utf-8", errors="replace")

def get_page_timezone(html: str) -> ZoneInfo:
    m = re.search(r'<option[^>]*value="([^"]*)"[^>]*selected', html, re.I)
    tz_name = m.group(1) if m else "America/New_York"
    print(f"  Zona de la página: {tz_name}", file=sys.stderr)
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return ZoneInfo("America/New_York")

def parse_items(html: str, page_tz: ZoneInfo) -> list[dict]:
    blocks = re.findall(r'<div[^>]*class="[^"]*list-group-item[^"]*"[^>]*>.*?</div>', html, re.DOTALL)
    programs = []
    for block in blocks:
        def attr(name: str) -> str:
            m = re.search(rf'data-{name}="([^"]*)"', block, re.I)
            return m.group(1).strip() if m else ""
        show = attr("showName")
        episode = attr("episodeTitle")
        start_raw = attr("st")
        duration = attr("duration")
        if not start_raw or not show:
            continue
        if show.lower() == "movie" and episode:
            title = episode
        elif episode:
            title = f"{show} / {episode}"
        else:
            title = show
        try:
            start_naive = datetime.strptime(start_raw, "%Y-%m-%d %H:%M:%S")
            start_page = start_naive.replace(tzinfo=page_tz)
            start = start_page.astimezone(TZ_TARGET)
            mins = int(duration) if duration.isdigit() else 30
            end = start + timedelta(minutes=mins)
        except Exception:
            continue
        programs.append({"titulo": title, "sta": start.strftime("%Y-%m-%d/%H:%M"), "end": end.strftime("%Y-%m-%d/%H:%M")})
    return programs

def scrape(site_id, outfile):
    base_url = f"https://www.tvpassport.com/tv-listings/stations/{site_id}"
    all_programs = []
    today = datetime.now(TZ_TARGET).date()
    for i in range(-1, 8):
        d = today + timedelta(days=i)
        date_str = d.strftime("%Y-%m-%d")
        try:
            html = fetch_page(base_url, date_str)
            page_tz = get_page_timezone(html)
            progs = parse_items(html, page_tz)
            all_programs.extend(progs)
            print(f"  {site_id} {date_str}: {len(progs)} programas", file=sys.stderr)
        except Exception as e:
            print(f"  Error en {site_id} {date_str}: {e}", file=sys.stderr)
    all_programs.sort(key=lambda x: x["sta"])
    seen = set()
    unique = [p for p in all_programs if not (p["sta"] in seen or seen.add(p["sta"]))]
    with open(outfile, "w", encoding="utf-8") as f:
        json.dump(unique, f, indent=2, ensure_ascii=False)
    print(f"Listo: {len(unique)} programas en {outfile}", file=sys.stderr)
    return len(unique)

def main():
    canales = load_canales()
    print(f"Procesando {len(canales)} canales en paralelo (sin límite)...", file=sys.stderr)

    with ThreadPoolExecutor() as executor:
        futures = {
            executor.submit(
                scrape,
                canal.get("id", ""),
                canal.get("json", f"{canal.get('id', '').split('/')[-1]}.json")
            ): canal
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
