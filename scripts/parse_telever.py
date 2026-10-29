#!/usr/bin/env python3
"""
Parser de programación Telever (Televisa Regional Veracruz)
"""

import json
import sys
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

Y_START = 104.0
SLOT_HEIGHT = 6.35

SKIP_PURE = {"GRABADO", "REPETICIÓN", "REPETICION", "SAP", "REP"}
KEEP_AS_IS = {"B-15", "B15", "RTC", "N+"}

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
        return page.extract_words(x_tolerance=1.5, y_tolerance=1.5)

def y_to_slot(y: float) -> int:
    return max(0, int(round((y - Y_START) / SLOT_HEIGHT)))

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
            and Y_START - 5 <= w["top"] < Y_START + 24 * 4 * SLOT_HEIGHT + 12
        ]
        if not col_words:
            continue

        lines_dict = defaultdict(list)
        for w in col_words:
            y_key = round(w["top"] / 2.0) * 2.0
            lines_dict[y_key].append(w)

        sorted_ys = sorted(lines_dict.keys())
        lines = [{"y": y, "words": sorted(lines_dict[y], key=lambda x: x["x0"])} for y in sorted_ys]

        blocks = []
        current = []
        last_y = None

        for line in lines:
            gap = 0 if last_y is None else (line["y"] - last_y)
            if gap < SLOT_HEIGHT * 1.4:
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

            start_dt = slot_to_dt(day_date, start_slot)
            end_dt = slot_to_dt(day_date, end_slot)

            programs.append({
                "titulo": title,
                "sta": start_dt.strftime("%Y-%m-%d/%H:%M:%S"),
                "end": end_dt.strftime("%Y-%m-%d/%H:%M:%S"),
            })

    programs.sort(key=lambda p: p["sta"])
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

        base_date = datetime(2026, 10, 26)
        clean = parse_schedule(words, base_date)
        print(f"Programas detectados: {len(clean)}")

        json_str = json.dumps(clean, ensure_ascii=False, indent=2)
        json.loads(json_str)

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(json_str + "\n")

        print(f"JSON escrito en {OUTPUT_FILE}")
        for item in clean[:8]:
            print(f"  {item['sta']} → {item['end']} | {item['titulo'][:55]}")

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
