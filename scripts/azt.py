#!/usr/bin/env python3
"""
EPG Azteca Uno desde FormulaTV
Incluye programas que cruzan medianoche (empezaron el día anterior).
"""

import json
import urllib.request
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import sys

TZ = ZoneInfo("America/Mexico_City")
OUTPUT_FILE = "azteca-test.json"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
BASE = "https://www.formulatv.com/mx/programacion/canal-azteca-uno"

DAYS = {
    -1: "ayer",
    0: "",          # hoy
    1: "manana",
    2: "pasadomanana",
}

def fetch(url: str) -> str:
    print(f"Descargando {url}...", file=sys.stderr)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read().decode("utf-8", errors="replace")

def extract_programs(html: str) -> list[dict]:
    m = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return []

    programs = []
    for item in data.get("@graph", []):
        if item.get("@type") != "ItemList":
            continue
        for el in item.get("itemListElement", []):
            ev = el.get("item", {})
            if ev.get("@type") != "BroadcastEvent":
                continue
            title = ev.get("name", "").strip()
            start = ev.get("startDate")
            end = ev.get("endDate")
            if not (title and start and end):
                continue
            try:
                st = datetime.fromisoformat(start)
                en = datetime.fromisoformat(end)
            except Exception:
                continue
            programs.append({
                "titulo": title,
                "sta": st.strftime("%Y-%m-%d/%H:%M"),
                "end": en.strftime("%Y-%m-%d/%H:%M"),
                "_start": st,
                "_end": en,
            })
    return programs

def main():
    all_programs = []
    today = datetime.now(TZ).date()

    # Descargar todos los días disponibles
    day_data = {}
    for offset, slug in DAYS.items():
        d = today + timedelta(days=offset)
        url = f"{BASE}/{slug}/" if slug else f"{BASE}/"
        try:
            html = fetch(url)
            progs = extract_programs(html)
            day_data[d] = progs
            print(f"  {d}: {len(progs)} programas", file=sys.stderr)
        except Exception as e:
            print(f"  Error en {d}: {e}", file=sys.stderr)
            day_data[d] = []

    # Incluir programas que cruzan medianoche
    for d, progs in day_data.items():
        all_programs.extend(progs)
        # Traer del día anterior los que terminan hoy
        prev_day = d - timedelta(days=1)
        if prev_day in day_data:
            for p in day_data[prev_day]:
                if p["_end"].date() > prev_day:  # cruza a hoy
                    all_programs.append(p)

    # Ordenar y quitar duplicados
    all_programs.sort(key=lambda x: x["_start"])
    seen = set()
    unique = []
    for p in all_programs:
        key = p["sta"]
        if key not in seen:
            seen.add(key)
            p.pop("_start", None)
            p.pop("_end", None)
            unique.append(p)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(unique, f, indent=2, ensure_ascii=False)

    print(f"Listo: {len(unique)} programas en {OUTPUT_FILE}", file=sys.stderr)

if __name__ == "__main__":
    main()
