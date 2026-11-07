#!/usr/bin/env python3

import json
import sys
import os
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright
from concurrent.futures import ThreadPoolExecutor, as_completed

CANALES_URL = "https://dl.dropboxusercontent.com/scl/fi/984awaw2wrq64549g1fmi/mvs-hub.txt?rlkey=6x99irvj1y58u5ekd094rk1fz"
TZ = ZoneInfo("America/Mexico_City")
REPLAY_DIR = "replay"
DAYS_BACK = 3
BASE_CATCHUP = "https://dish.akamaized.net/Content/DASH/CatchUp/channel(name={name},startTime={start},endTime={end})/manifest.mpd"
ORIGIN = "https://mvshub.com.mx/"

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

def get_logo(item):
    try:
        images = item.get("images", {}).get("image", [])
        if not images:
            return ""
        for img in images:
            if img.get("usage") == "S_DESC" and img.get("url"):
                return img["url"]
        return images[0].get("url", "")
    except Exception:
        return ""

def get_session_info():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="es-MX"
        )
        page = context.new_page()
        print("Obteniendo sesión MVS Hub...", file=sys.stderr)
        page.goto("https://mvshub.com.mx/#spa/epg", wait_until="networkidle", timeout=60000)
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
        browser.close()
        return info.get("host"), info.get("uuid"), info.get("lineup")

def fetch_epg(host, uuid, cid, lineup, now):
    all_items = []
    for days_ago in range(DAYS_BACK, -1, -1):
        day = (now - timedelta(days=days_ago)).replace(hour=0, minute=0, second=0, microsecond=0)
        from_ms = int(day.timestamp() * 1000)
        url = f"{host}/xtv-ws-client/api/epgcache/list/{uuid}/{cid}/{lineup}?page=0&size=100&dateFrom={from_ms}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                j = json.loads(resp.read().decode("utf-8"))
                items = j.get("contents", {}).get("content", [])
                if items:
                    all_items.extend(items)
                    print(f"  {cid} {day.date()}: {len(items)} programas", file=sys.stderr)
        except Exception as e:
            print(f"  Error {cid} {day.date()}: {e}", file=sys.stderr)
    return all_items

def process_canal(host, uuid, lineup, canal):
    cid = str(canal.get("id", "")).strip()
    outfile = canal.get("json", f"{cid}.json")
    channel_name = canal.get("url", "").strip()
    clearkey = canal.get("clearkey", "")
    if not channel_name:
        print(f"Sin 'url' para canal {cid}, saltando", file=sys.stderr)
        return 0

    now = datetime.now(TZ)
    cutoff = (now - timedelta(days=DAYS_BACK)).replace(hour=0, minute=0, second=0, microsecond=0)
    cutoff_ms = int(cutoff.timestamp() * 1000)

    all_items = fetch_epg(host, uuid, cid, lineup, now)
    if not all_items:
        print(f"Sin datos para {cid}", file=sys.stderr)
        return 0

    seen = set()
    programs = []
    for item in all_items:
        if not item.get("catchupTv"):
            continue
        start = item.get("startDateTime")
        end = item.get("endDateTime")
        if not start or start < cutoff_ms:
            continue
        title = build_title(item)
        if not title:
            continue
        key = str(start)
        if key in seen:
            continue
        seen.add(key)

        start_100ns = int(start) * 10000
        end_100ns = int(end) * 10000 if end else start_100ns + 36000000000
        catchup_url = BASE_CATCHUP.format(
            name=channel_name,
            start=start_100ns,
            end=end_100ns
        )

        sta = datetime.fromtimestamp(start / 1000, TZ)
        end_dt = datetime.fromtimestamp(end / 1000, TZ) if end else sta

        programs.append({
            "titulo": title,
            "logo": get_logo(item),
            "url": catchup_url,
            "clearkey": clearkey,
            "sta": sta.strftime("%Y-%m-%d/%H:%M"),
            "end": end_dt.strftime("%Y-%m-%d/%H:%M"),
            "origin": ORIGIN,
            "referer": ORIGIN,
            "useragent": ""
        })

    programs.sort(key=lambda x: x["sta"])
    outpath = os.path.join(REPLAY_DIR, outfile)
    os.makedirs(REPLAY_DIR, exist_ok=True)
    with open(outpath, "w", encoding="utf-8") as f:
        json.dump(programs, f, indent=2, ensure_ascii=False)
    print(f"Listo: {len(programs)} catchup en {outpath}", file=sys.stderr)
    return len(programs)

def main():
    host, uuid, lineup = get_session_info()
    if not host or not uuid or not lineup:
        print("No se pudo obtener la sesión de MVS Hub", file=sys.stderr)
        sys.exit(1)
    print(f"Sesión obtenida → Host: {host} | UUID: {uuid} | Lineup: {lineup}", file=sys.stderr)

    canales = load_canales()
    print(f"Procesando {len(canales)} canales (últimos {DAYS_BACK} días, solo catchupTv=true)...", file=sys.stderr)

    with ThreadPoolExecutor() as executor:
        futures = {
            executor.submit(process_canal, host, uuid, lineup, canal): canal
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
