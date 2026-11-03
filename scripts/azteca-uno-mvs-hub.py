#!/usr/bin/env python3

import json
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

CHANNEL = "101"
ID = ""
TZ = ZoneInfo("America/Mexico_City")
OUTPUT_FILE = "azteca-uno-mvs-hub.json"

def fetch_epg(context, host, uuid, cid, lineup, now):
    all_items = []
    for day_offset in range(-1, 6):
        day = now + timedelta(days=day_offset)
        from_ms = int(day.replace(hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000)
        url = f"{host}/xtv-ws-client/api/epgcache/list/{uuid}/{cid}/{lineup}?page=0&size=100&dateFrom={from_ms}"
        try:
            resp = context.request.get(url)
            if resp.status == 200:
                j = resp.json()
                items = j.get("contents", {}).get("content", [])
                all_items.extend(items)
                print(f"  {day.date()}: {len(items)} programas", file=sys.stderr)
        except Exception as e:
            print(f"  Error {day.date()}: {e}", file=sys.stderr)
    return all_items

def scrape():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        print("Cargando...", file=sys.stderr)
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
                const mapping = {};
                document.querySelectorAll(".epg-channel").forEach(ch => {
                    const num = ch.querySelector(".number")?.innerText?.trim();
                    const img = ch.querySelector("img")?.src || "";
                    const idm = img.match(/\\/images\\/(\\d+)\\/CH_LOGO\\//);
                    if (num && idm) mapping[num] = idm[1];
                });
                return {host, uuid, lineup, mapping};
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
        all_items = []
        cid = None
        if ID.strip():
            cid = ID.strip()
            print(f"Intentando con ID: {cid}", file=sys.stderr)
            all_items = fetch_epg(context, host, uuid, cid, lineup, now)
        if not all_items and CHANNEL.strip():
            cid = info.get("mapping", {}).get(CHANNEL)
            if cid:
                print(f"ID falló o vacío, intentando con CHANNEL {CHANNEL} → {cid}", file=sys.stderr)
                all_items = fetch_epg(context, host, uuid, cid, lineup, now)
        browser.close()
        if not all_items:
            print("Sin datos", file=sys.stderr)
            return []
        seen = set()
        programs = []
        for item in all_items:
            title = item.get("title", "")
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
    programs = scrape()
    if programs:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(programs, f, indent=2, ensure_ascii=False)
        print(f"Listo: {len(programs)} en {OUTPUT_FILE}", file=sys.stderr)
    else:
        print("Sin resultados", file=sys.stderr)

if __name__ == "__main__":
    main()
