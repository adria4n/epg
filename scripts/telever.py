#!/usr/bin/env python3

import json
from datetime import datetime, timedelta

FILE = "telever.json"

def main():
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    if today.weekday() != 0:
        print(f"Hoy no es lunes ({today.strftime('%Y-%m-%d')}). No se actualiza.")
        return

    print(f"Hoy es lunes ({today.strftime('%Y-%m-%d')}). Actualizando fechas...")

    try:
        with open(FILE, "r", encoding="utf-8") as f:
            programs = json.load(f)
    except FileNotFoundError:
        print(f"No se encontró {FILE}")
        return

    if not programs:
        print("El JSON está vacío")
        return

    first_sta = datetime.strptime(programs[0]["sta"], "%Y-%m-%d/%H:%M:%S")
    first_monday = first_sta.replace(hour=0, minute=0, second=0)

    days_to_shift = (today - first_monday).days

    if days_to_shift == 0:
        print("Las fechas ya coinciden con el lunes actual. No se modifica nada.")
        return

    print(f"Desplazando {days_to_shift} días")

    result = []
    for p in programs:
        sta = datetime.strptime(p["sta"], "%Y-%m-%d/%H:%M:%S")
        end = datetime.strptime(p["end"], "%Y-%m-%d/%H:%M:%S")

        new_sta = sta + timedelta(days=days_to_shift)
        new_end = end + timedelta(days=days_to_shift)

        result.append({
            "titulo": p["titulo"],
            "sta": new_sta.strftime("%Y-%m-%d/%H:%M:%S"),
            "end": new_end.strftime("%Y-%m-%d/%H:%M:%S"),
        })

    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write("\n")

    first_new = datetime.strptime(result[0]["sta"], "%Y-%m-%d/%H:%M:%S")
    last_new = datetime.strptime(result[-1]["end"], "%Y-%m-%d/%H:%M:%S")
    print(f"Actualizado {FILE}")
    print(f"Nuevo rango: {first_new.strftime('%Y-%m-%d')} → {last_new.strftime('%Y-%m-%d')}")
    print(f"Programas: {len(result)}")

if __name__ == "__main__":
    main()
