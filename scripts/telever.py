#!/usr/bin/env python3

import json
from datetime import datetime, timedelta

FILE = "telever.json"

def get_next_monday(from_date: datetime) -> datetime:
    """Devuelve el próximo lunes (o el mismo día si ya es lunes)."""
    days_ahead = 0 - from_date.weekday()  # lunes = 0
    if days_ahead <= 0:
        days_ahead += 7
    return from_date + timedelta(days=days_ahead)

def shift_to_next_week(programs):
    if not programs:
        return []

    # Tomar la fecha del primer programa como referencia
    first_sta = datetime.strptime(programs[0]["sta"], "%Y-%m-%d/%H:%M:%S")
    next_monday = get_next_monday(first_sta)
    days_to_shift = (next_monday - first_sta.replace(hour=0, minute=0, second=0)).days

    print(f"Fecha base actual: {first_sta.strftime('%Y-%m-%d')}")
    print(f"Próximo lunes:     {next_monday.strftime('%Y-%m-%d')}")
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
    return result

def main():
    try:
        with open(FILE, "r", encoding="utf-8") as f:
            programs = json.load(f)
    except FileNotFoundError:
        print(f"No se encontró {FILE}")
        return

    if not programs:
        print("El JSON está vacío")
        return

    new_programs = shift_to_next_week(programs)

    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(new_programs, f, ensure_ascii=False, indent=2)
        f.write("\n")

    first_new = datetime.strptime(new_programs[0]["sta"], "%Y-%m-%d/%H:%M:%S")
    last_new = datetime.strptime(new_programs[-1]["end"], "%Y-%m-%d/%H:%M:%S")
    print(f"Actualizado {FILE}")
    print(f"Nuevo rango: {first_new.strftime('%Y-%m-%d')} → {last_new.strftime('%Y-%m-%d')}")
    print(f"Programas: {len(new_programs)}")

if __name__ == "__main__":
    main()
