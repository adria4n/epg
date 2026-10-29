#!/usr/bin/env python3

import json
import sys
import re
import requests
from datetime import datetime, timedelta
from collections import defaultdict
import pdfplumber

PDF_URL = "https://televisaregional.tv/pdf/telever-c12.pdf"
OUTPUT_FILE = "telever.json"

DAY_COLUMNS = [
    {"name": "Lunes",     "offset": 0, "x0": 50,  "x1": 125},
    {"name": "Martes",    "offset": 1, "x0": 125, "x1": 200},
    {"name": "Miércoles", "offset": 2, "x0": 200, "x1": 275},
    {"name": "Jueves",    "offset": 3, "x0": 275, "x1": 355},
    {"name": "Viernes",   "offset": 4, "x0": 355, "x1": 430},
    {"name": "Sábado",    "offset": 5, "x0": 430, "x1": 505},
    {"name": "Domingo",   "offset": 6, "x0": 505, "x1": 575},
]

Y_START = 104.6
SLOT_HEIGHT = 6.45

SKIP_PURE = {"GRABADO", "REPETICIÓN", "REPETICION", "SAP", "REP"}
KEEP_AS_IS = {"B-15", "B15", "RTC", "N+"}

MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}

def download_pdf(url: str, dest: str = "/tmp/telever.pdf") -> str:
    print(f"Descargando {url}...")
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    with open(dest, "wb") as f:
        f.write(r.content)
    print(f"PDF guardado ({len(r.content)} bytes)")
    return dest

def extract_words(pdf_path: str):
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[0]
        return page.extract_words(x_tolerance=2.5, y_tolerance=2.0)

def parse_base_date(words) -> datetime:
    header = [w for w in words if w["top"] < 80]
    text = " ".join(w["text"] for w in header)
    day_m = re.search(r"\b(\d{1,2})\b", text)
    month_m = re.search(r"\b(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\b", text, re.I)
    year_m = re.search(r"\b(20\d{2})\b", text)
    if not (day_m and month_m and year_m):
        raise ValueError(f"No se pudo leer la fecha del encabezado: {text}")
    day = int(day_m.group(1))
    month = MESES.get(month_m.group(1).lower())
    year = int(year_m.group(1))
    if not month:
        raise ValueError(f"Mes no reconocido: {month_m.group(1)}")
    print(f"Fecha base detectada: {year}-{month:02d}-{day:02d}")
    return datetime(year, month, day)

def y_to_slot(y: float) -> int:
    rel = y - Y_START
    if rel < 0:
        return 0
    return int(round(rel / SLOT_HEIGHT))

def slot_to_dt(base: datetime, slot: int) -> datetime:
    return base + timedelta(minutes=slot * 15)

def to_title(text: str) -> str:
    words = text.split()
    out = []
    for w in words:
        up = w.upper()
        if up in KEEP_AS_IS:
            out.append(up)
        else:
            out.append(w.capitalize())
    return " ".join(out)

def clean_block(words) -> str:
    parts = []
    for w in words:
        t = w["text"].strip()
        if not t:
            continue
        up = t.upper()
        if up in SKIP_PURE:
            continue
        if len(t) == 1 and up not in {"A", "B"}:
            continue
        parts.append(t)
    if not parts:
        return ""
    cleaned = []
    for p in parts:
        if not cleaned or cleaned[-1].upper() != p.upper():
            cleaned.append(p)
    return to_title(" ".join(cleaned))

def parse_schedule(words, base_date: datetime):
    programs = []

    for col in DAY_COLUMNS:
        col_words = [
            w for w in words
            if col["x0"] <= w["x0"] < col["x1"]
            and Y_START - 6 <= w["top"] < Y_START + 24 * 4 * SLOT_HEIGHT + 20
        ]
        if not col_words:
            continue

        lines_dict = defaultdict(list)
        for w in col_words:
            y_key = round(w["top"] / 1.2) * 1.2
            lines_dict[y_key].append(w)

        sorted_ys = sorted(lines_dict.keys())
        lines = [{"y": y, "words": sorted(lines_dict[y], key=lambda x: x["x0"])} for y in sorted_ys]

        blocks = []
        current = []
        last_y = None

        for line in lines:
            gap = 0 if last_y is None else (line["y"] - last_y)
            # Más tolerante para bloques de 15, 30 y 45 min
            if gap < SLOT_HEIGHT * 2.8:
                current.extend(line["words"])
            else:
                if current:
                    blocks.append(current)
                current = list(line["words"])
            last_y = line["y"]
        if current:
            blocks.append(current)

        day_date = base_date + timedelta(days=col["offset"])

        for block in blocks:
            title = clean_block(block)
            if len(title) < 3:
                continue

            y_min = min(w["top"] for w in block)
            y_max = max(w["top"] for w in block)

            start_slot = y_to_slot(y_min)
            end_slot = y_to_slot(y_max) + 1
            if end_slot <= start_slot:
                end_slot = start_slot + 1

            # Forzar duración mínima razonable según el alto del bloque
            block_height = y_max - y_min
            min_slots = max(1, int(round(block_height / SLOT_HEIGHT)))
            if end_slot - start_slot < min_slots:
                end_slot = start_slot + min_slots

            start_dt = slot_to_dt(day_date, start_slot)
            end_dt = slot_to_dt(day_date, end_slot)

            programs.append({
                "titulo": title,
                "sta": start_dt.strftime("%Y-%m-%d/%H:%M:%S"),
                "end": end_dt.strftime("%Y-%m-%d/%H:%M:%S"),
            })

    programs.sort(key=lambda p: p["sta"])
    for i in range(len(programs) - 1):
        curr_end = datetime.strptime(programs[i]["end"], "%Y-%m-%d/%H:%M:%S")
        next_sta = datetime.strptime(programs[i+1]["sta"], "%Y-%m-%d/%H:%M:%S")
        if curr_end.date() == next_sta.date() and next_sta > curr_end:
            programs[i]["end"] = programs[i+1]["sta"]

    seen = set()
    result = []
    for p in programs:
        key = (p["titulo"], p["sta"])
        if key not in seen:
            seen.add(key)
            result.append(p)

    return result

def main():
    try:
        pdf_path = download_pdf(PDF_URL)
        words = extract_words(pdf_path)
        print(f"Palabras extraídas: {len(words)}")

        base_date = parse_base_date(words)
        clean = parse_schedule(words, base_date)
        print(f"Programas detectados: {len(clean)}")

        json_str = json.dumps(clean, ensure_ascii=False, indent=2)
        json.loads(json_str)

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(json_str + "\n")

        print(f"JSON escrito en {OUTPUT_FILE}")
        for item in clean[:10]:
            print(f"  {item['sta']} → {item['end']} | {item['titulo'][:55]}")

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
