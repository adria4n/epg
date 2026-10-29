#!/usr/bin/env python3

import json
import sys
from datetime import datetime, timedelta

FILE = "telever.json"

def shift_week(programs, days_to_shift: int):
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
    if len(sys.argv) >= 2:
        try:
            days = int(sys.argv[1])
        except ValueError:
            print("El número de días debe ser un entero")
            sys.exit(1)
    else:
        days = 7
        print("No se pasó argumento. Usando +7 días por defecto.")

    try:
        with open(FILE, "r", encoding="utf-8") as f:
            programs = json.load(f)
    except FileNotFoundError:
        print(f"No se encontró {FILE}")
        sys.exit(1)

    if not programs:
        print("El JSON está vacío")
        sys.exit(1)

    first = datetime.strptime(programs[0]["sta"], "%Y-%m-%d/%H:%M:%S")
    print(f"Rango original: {first.strftime('%Y-%m-%d')}")

    new_programs = shift_week(programs, days)

    first_new = datetime.strptime(new_programs[0]["sta"], "%Y-%m-%d/%H:%M:%S")
    print(f"Nuevo rango:    {first_new.strftime('%Y-%m-%d')}")

    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(new_programs, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"Actualizado {FILE} ({len(new_programs)} programas)")

if __name__ == "__main__":
    main()
