#!/usr/bin/env python3

import json
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

CHANNEL = "103"
TZ = ZoneInfo("America/Mexico_City")
OUTPUT_FILE = "mvshub-epg.json"

def scrape():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        print("Cargando...", file=sys.stderr)
        page.goto("https://mvshub.com.mx/#spa/epg", wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(5000)

        info = page.evaluate("""
            () => {
                let uuid = null;
                const entries = performance.getEntriesByType("resource");
                for (const e of entries) {
                    const m = e.name.match(/epgcache\\/list\\/([a-f0-9-]{36})/);
                    if (m) { uuid = m[1]; break; }
                }
                const mapping = {};
                document.querySelectorAll(".epg-channel").forEach(ch => {
                    const num = ch.querySelector(".number")?.innerText?.trim();
                    const img = ch.querySelector("img")?.src || "";
                    const idm = img.match(/\\/images\\/(\\d+)\\/CH_LOGO\\//);
                    if (num && idm) mapping[num] = idm[1];
                });
                return {uuid, mapping};
            }
        """)

        uuid = info.get("uuid")
        cid = info.get("mapping", {}).get(CHANNEL)
        if not uuid or not cid:
            print(f"No se obtuvo uuid o canal {CHANNEL}", file=sys.stderr)
            browser.close()
            return []

        print(f"UUID: {uuid} | CID: {cid}", file=sys.stderr)
        now_ms = int(datetime.now(TZ).timestamp() * 1000)
        from_ms = now_ms - 8 * 3600 * 1000

        data = page.evaluate("""
            async ([uuid, cid, fromMs]) => {
                const url = `https://edge.prod.ovp.ses.com:9443/xtv-ws-client/api/epgcache/list/\( {uuid}/ \){cid}/220?page=0&size=200&dateFrom=${fromMs}`;
                const r = await fetch(url);
                const j = await r.json();
                const items = j.contents?.content || [];
                return items.map(i => ({
                    titulo: i.title || "",
                    start: i.startDateTime,
                    end: i.endDateTime
                }));
            }
        """, [uuid, cid, from_ms])

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
