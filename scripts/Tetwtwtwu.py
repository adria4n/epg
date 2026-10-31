#!/usr/bin/env python3
"""
EPG Megacable desde gato.tv
Uso: python3 epg_megacable.py [numero_canal]
Ej:  python3 epg_megacable.py 101
"""

import json
import urllib.request
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import sys

TZ = ZoneInfo("America/Mexico_City")
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
OUTPUT_FILE = "azte22ca-une32222o.json"

def fetch(url: str) -> str:
    print(f"Descargando {url}...", file=sys.stderr)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read().decode("utf-8", errors="replace")

def get_channel_slug(channel_num: str) -> str:
    """Obtiene el slug del canal desde la guía principal de Megacable."""
    html = fetch("https://www.gatotv.com/guia_tv/megacable")
    # Busca bloques de canal: número + enlace /canal/slug
    pattern = re.compile(
        r'<div class="div_channel_number">\s*' + re.escape(channel_num) + r'\s*</div>.*?'
        r'href="https://www.gatotv.com/canal/([^"/]+)"',
        re.DOTALL | re.IGNORECASE
    )
    m = pattern.search(html)
    if not m:
        raise ValueError(f"No se encontró el canal {channel_num} en la guía de Megacable")
    slug = m.group(1)
    print(f"Canal {channel_num} → slug: {slug}", file=sys.stderr)
    return slug

def parse_channel_day(html: str, day: datetime) -> list[dict]:
    """Parsea la tabla de horarios de un día del canal."""
    programs = []
    # Extrae filas con hora inicio, hora fin y título
    rows = re.findall(
        r'<tr class="tbl_EPG_row[^"]*">\s*'
        r'<td[^>]*>.*?datetime="(\d{2}:\d{2})".*?</td>\s*'
        r'<td[^>]*>.*?datetime="(\d{2}:\d{2})".*?</td>\s*'
        r'<td[^>]*>.*?<span>([^<]+)</span>',
        html,
        re.DOTALL | re.IGNORECASE
    )

    current_day = day
    for start_t, end_t, title in rows:
        title = title.strip()
        if not title:
            continue
        try:
            sh, sm = map(int, start_t.split(":"))
            eh, em = map(int, end_t.split(":"))

            start = current_day.replace(hour=sh, minute=sm, second=0, microsecond=0)
            end = current_day.replace(hour=eh, minute=em, second=0, microsecond=0)

            # Si el fin es menor o igual que el inicio → cruza medianoche
            if end <= start:
                end += timedelta(days=1)

            # Si el inicio es muy temprano y el anterior era de noche, ajusta día
            if programs and start.hour < 6 and programs[-1].get("_start") and programs[-1]["_start"].hour >= 20:
                start += timedelta(days=1)
                end += timedelta(days=1)
                current_day = start

            programs.append({
                "titulo": title,
                "sta": start.strftime("%Y-%m-%d/%H:%M"),
                "end": end.strftime("%Y-%m-%d/%H:%M"),
                "_start": start,
            })
        except Exception:
            continue

    for p in programs:
        p.pop("_start", None)
    return programs

def main():
    channel_num = sys.argv[1] if len(sys.argv) > 1 else "101"
    slug = get_channel_slug(channel_num)

    all_programs = []
    today = datetime.now(TZ).date()

    for i in range(-1, 7):  # ayer hasta +6 días
        d = today + timedelta(days=i)
        date_str = d.strftime("%Y-%m-%d")
        url = f"https://www.gatotv.com/canal/{slug}/{date_str}"
        try:
            html = fetch(url)
            day_dt = datetime.combine(d, datetime.min.time(), tzinfo=TZ)
            progs = parse_channel_day(html, day_dt)
            all_programs.extend(progs)
            print(f"  {date_str}: {len(progs)} programas", file=sys.stderr)
        except Exception as e:
            print(f"  Error en {date_str}: {e}", file=sys.stderr)

    # Ordenar y quitar duplicados por hora de inicio
    all_programs.sort(key=lambda x: x["sta"])
    seen = set()
    unique = [p for p in all_programs if not (p["sta"] in seen or seen.add(p["sta"]))]

    out_file = f"{slug}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(unique, f, indent=2, ensure_ascii=False)

    print(f"Listo: {len(unique)} programas en {out_file}", file=sys.stderr)

if __name__ == "__main__":
    main()
