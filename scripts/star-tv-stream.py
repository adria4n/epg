#!/usr/bin/env python3

import json
import sys
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

CANALES_URL = "https://dl.dropboxusercontent.com/scl/fi/g31egmv8b3ik4esbe3vlq/star-tv-stream.json?rlkey=gz8qjwx3qgj6qogtsvmtjqzi1"
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
                print(f"  {day.date()}: {len(items)} programas", file=sys.stderr)
            else:
                break
        except Exception as e:
            print(f"  Error {day.date()}: {e}", file=sys.stderr)
            break
        day_offset += 1
    return all_items

def scrape(cid):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="es-MX"
        )
        page = context.new_page()
        print("Cargando...", file=sys.stderr)
        page.goto("https://edgelb.stargroup.com.mx/web/startv/#spa/login", wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(3000)
        page.get_by_text("EXPLORAR CANALES").click()
        page.wait_for_timeout(5000)
        page.close()
        page = context.new_page()
        page.goto("https://edgelb.stargroup.com.mx/web/startv/#spa/epg", wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(6000)
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
            print("No se obtuvo host, UUID o lineup", file=sys.stderr)
            browser.close()
            return []
        print(f"Host: {host} | UUID: {uuid} | Lineup: {lineup}", file=sys.stderr)
        now = datetime.now(TZ)
        print(f"Usando ID: {cid}", file=sys.stderr)
        all_items = fetch_epg(context, host, uuid, cid, lineup, now)
        browser.close()
        if not all_items:
            print("Sin datos", file=sys.stderr)
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

def main():
    canales = load_canales()
    for canal in canales:
        cid = str(canal.get("id", "")).strip()
        outfile = canal.get("json", f"{cid}.json")
        print(f"\n=== {canal.get('nombre', '?')} (ID {cid}) → {outfile} ===", file=sys.stderr)
        programs = scrape(cid)
        if programs:
            with open(outfile, "w", encoding="utf-8") as f:
                json.dump(programs, f, indent=2, ensure_ascii=False)
            print(f"Listo: {len(programs)} en {outfile}", file=sys.stderr)
        else:
            print("Sin resultados", file=sys.stderr)

if __name__ == "__main__":
    main()
