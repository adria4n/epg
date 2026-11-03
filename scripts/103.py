#!/usr/bin/env python3

import json
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

CHANNEL = "103"
CHANNEL_MAP = {"101": "969", "103": "724", "106": "783", "120": "1444", "134": "1447", "145": "1442", "200": "604", "204": "612", "206": "613"}
TZ = ZoneInfo("America/Mexico_City")
OUTPUT_FILE = "mvshub-epg.json"

def scrape():
    cid = CHANNEL_MAP.get(CHANNEL)
    if not cid:
        print(f"Canal {CHANNEL} no mapeado", file=sys.stderr)
        return []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        print("Cargando...", file=sys.stderr)
        page.goto("https://mvshub.com.mx/#spa/epg", wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(4000)
        now_ms = int(datetime.now(TZ).timestamp() * 1000)
        from_ms = now_ms - 6 * 3600 * 1000
        data = page.evaluate("""
            async ([cid, fromMs]) => {
                const url = `https://edge.prod.ovp.ses.com:9443/xtv-ws-client/api/epgcache/list/f3ba0f40-5b31-40f4-9ec2-28fd441e3427/\( {cid}/220?page=0&size=200&dateFrom= \){fromMs}`;
                const r = await fetch(url);
                const j = await r.json();
                const items = j.contents?.content || j.content || [];
                return items.map(i => ({
                    titulo: i.title || "",
                    start: i.startDateTime,
                    end: i.endDateTime
                }));
            }
        """, [cid, from_ms])
        browser.close()
        programs = []
        for item in data:
            if not item.get("titulo"):
                continue
            sta = datetime.fromtimestamp(item["start"] / 1000, TZ)
            end = datetime.fromtimestamp(item["end"] / 1000, TZ)
            programs.append({
                "titulo": item["titulo"],
                "sta": sta.strftime("%Y-%m-%d/%H:%M"),
                "end": end.strftime("%Y-%m-%d/%H:%M"),
            })
        programs.sort(key=lambda x: x["sta"])
        print(f"Canal {CHANNEL}: {len(programs)} programas", file=sys.stderr)
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
