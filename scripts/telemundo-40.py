#!/usr/bin/env python3

import json
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "https://d3ur398j0yj7gx.cloudfront.net/ajax/program_guide/feed/block/{year}/{month:02d}/{day:02d}"

# Zonas horarias
ZONAS = {
    "east": ZoneInfo("America/New_York"),
    "central": ZoneInfo("America/Chicago"),
    "montana": ZoneInfo("America/Denver"),
    "pacifico": ZoneInfo("America/Los_Angeles"),
}

def fetch_day(date: datetime) -> list:
    url = BASE_URL.format(year=date.year, month=date.month, day=date.day)
    print(f"Descargando {url}", file=sys.stderr)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.load(resp)
            return data if isinstance(data, list) else []
    except Exception as e:
        print(f"Error descargando {url}: {e}", file=sys.stderr)
        return []

def unix_to_tz(ts_str: str, tz: ZoneInfo) -> datetime:
    ts = int(ts_str)
    return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(tz)

def format_dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d/%H:%M")

def process_programs(programs: list, tz: ZoneInfo) -> list:
    if not programs:
        return []
    programs = sorted(programs, key=lambda p: int(p.get("time_GMT", 0)))
    result = []
    for i, prog in enumerate(programs):
        name = prog.get("name") or "Sin título"
        ts_str = prog.get("time_GMT")
        if not ts_str:
            continue
        start_dt = unix_to_tz(ts_str, tz)
        if i + 1 < len(programs) and programs[i + 1].get("time_GMT"):
            end_dt = unix_to_tz(programs[i + 1]["time_GMT"], tz)
        else:
            end_dt = start_dt + timedelta(minutes=60)
        result.append({
            "titulo": name,
            "sta": format_dt(start_dt),
            "end": format_dt(end_dt)
        })
    return result

def main():
    # Usamos Mexico City solo para calcular "hoy"
    ahora = datetime.now(ZoneInfo("America/Mexico_City"))
    hoy = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
    dias = [hoy + timedelta(days=i) for i in range(-1, 8)]

    todos_los_programas = []
    print(f"Descargando {len(dias)} días en paralelo...", file=sys.stderr)

    with ThreadPoolExecutor() as executor:
        futures = {executor.submit(fetch_day, dia): dia for dia in dias}
        for future in as_completed(futures):
            try:
                todos_los_programas.extend(future.result())
            except Exception as e:
                dia = futures[future]
                print(f"Error procesando día {dia.date()}: {e}", file=sys.stderr)

    # Generar un JSON por zona
    for nombre_zona, tz in ZONAS.items():
        epg = process_programs(todos_los_programas, tz)
        
        # Quitar duplicados
        vistos = set()
        unicos = []
        for item in epg:
            clave = (item["titulo"], item["sta"])
            if clave not in vistos:
                vistos.add(clave)
                unicos.append(item)

        archivo = f"telemundo-{nombre_zona}.json"
        with open(archivo, "w", encoding="utf-8") as f:
            json.dump(unicos, f, indent=2, ensure_ascii=False)
        
        print(f"Guardado {len(unicos)} programas en {archivo}", file=sys.stderr)

if __name__ == "__main__":
    main()
