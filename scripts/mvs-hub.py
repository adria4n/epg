#!/usr/bin/env python3

import json
import sys
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright
from concurrent.futures import ThreadPoolExecutor, as_completed

CANALES_URL = "https://dl.dropboxusercontent.com/scl/fi/984awaw2wrq64549g1fmi/mvs-hub.txt?rlkey=6x99irvj1y58u5ekd094rk1fz"
TZ = ZoneInfo("America/Mexico_City")

def load_canales():
    with urllib.request.urlopen(CANALES_URL) as resp:
        return json.loads(resp.read().decode("utf-8"))

def build_title(item):
    title = item.get("title", "")
    season = item.get("seasonNumber")
    episode = item.get("episodeNumber")
    ep_title = item.get("episodeTitle", "")
    parts = []
    if season and season > 0:
        parts.append(f"T{season}")
    if episode and episode > 0:
        parts.append(f"E{episode}")
    extra = " ".join(parts)
    if ep_title:
        extra = f"{extra} {ep_title}".strip() if extra else ep_title
    if extra:
        return f"{title} / {extra}"
    return title

def fetch_epg(context, host, uuid, cid, lineup, now):
    all_items = []
    day_offset = -1
    while True:
        day = now + timedelta(days=day_offset)
        from_ms = int(day.replace(hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000)
        url = f"{host}/xtv-ws-client/api/epgcache/list/{uuid}/{cid}/{lineup}?page=0&size=100&dateFrom={from_ms}"
        try:
            resp = context.request.get(url)
            if resp.status == 200:
                j = resp.json()
                items = j.get("contents", {}).get("content", [])
                if not items:
                    break
                all_items.extend(items)
                print(f"  {cid} {day.date()}: {len(items)} programas", file=sys.stderr)
            else:
                break
        except Exception as e:
            print(f"  Error {cid} {day.date()}: {e}", file=sys.stderr)
            break
        day_offset += 1
    return all_items

def scrape(cid):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        print(f"Cargando {cid}...", file=sys.stderr)
        page.goto("https://mvshub.com.mx/#spa/epg", wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(5000)
        info = page.evaluate("""
            () => {
                let host = null;
                let uuid = null;
                let lineup = null;
                const entries = performance.getEntriesByType("resource");
                for (const e of entries) {
                    const m = e.name.match(/(https?:\\/\\/[^/]+)\\/xtv-ws-client\\/api\\/epgcache\\/list\\/([a-f0-9-]{36})\\/\\d+\\/(\\d+)/);
                    if (m) { host = m[1]; uuid = m[2]; lineup = m[3]; break; }
                }
                return {host, uuid, lineup};
            }
        """)
        host = info.get("host")
        uuid = info.get("uuid")
        lineup = info.get("lineup")
        if not host or not uuid or not lineup:
            print(f"No se obtuvo host, UUID o lineup para {cid}", file=sys.stderr)
            browser.close()
            return []
        print(f"Host: {host} | UUID: {uuid} | Lineup: {lineup} | CID: {cid}", file=sys.stderr)
        now = datetime.now(TZ)
        all_items = fetch_epg(context, host, uuid, cid, lineup, now)
        browser.close()
        if not all_items:
            print(f"Sin datos para {cid}", file=sys.stderr)
            return []
        seen = set()
        programs = []
        for item in all_items:
            title = build_title(item)
            start = item.get("startDateTime")
            end = item.get("endDateTime")
            if not title or not start:
                continue
            key = str(start)
            if key in seen:
                continue
            seen.add(key)
            sta = datetime.fromtimestamp(start / 1000, TZ)
            end_dt = datetime.fromtimestamp(end / 1000, TZ)
            programs.append({
                "titulo": title,
                "sta": sta.strftime("%Y-%m-%d/%H:%M"),
                "end": end_dt.strftime("%Y-%m-%d/%H:%M"),
            })
        programs.sort(key=lambda x: x["sta"])
        print(f"Total: {len(programs)} programas (CID: {cid})", file=sys.stderr)
        return programs

def process_canal(canal):
    cid = str(canal.get("id", "")).strip()
    outfile = canal.get("json", f"{cid}.json")
    programs = scrape(cid)
    if programs:
        with open(outfile, "w", encoding="utf-8") as f:
            json.dump(programs, f, indent=2, ensure_ascii=False)
        print(f"Listo: {len(programs)} en {outfile}", file=sys.stderr)
        return len(programs)
    else:
        print(f"Sin resultados para {cid}", file=sys.stderr)
        return 0

def main():
    canales = load_canales()
    print(f"Procesando {len(canales)} canales en paralelo (sin límite)...", file=sys.stderr)

    with ThreadPoolExecutor() as executor:
        futures = {
            executor.submit(process_canal, canal): canal
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
