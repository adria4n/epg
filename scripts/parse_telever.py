#!/usr/bin/env python3
"""
Parser de programación Telever.
Detecta columnas y horas automáticamente del PDF.
"""

import json
import sys
import re
import requests
from datetime import datetime, timedelta
from collections import defaultdict
import pdfplumber

PDF_URL = "https://televisaregional.tv/pdf/telever-c12.pdf"
OUTPUT_FILE = "telever.json"

SKIP_PURE = {"GRABADO", "REPETICIÓN", "REPETICION", "SAP", "REP", "*SAP"}
KEEP_AS_IS = {"B-15", "B15", "RTC", "N+"}

MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}

DAY_NAMES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

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

def parse_base_date(words) -> datetime:
    header = [w for w in words if w["top"] < 80]
    text = " ".join(w["text"] for w in header)
    day_m = re.search(r"\b(\d{1,2})\b", text)
    month_m = re.search(r"\b(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\b", text, re.I)
    year_m = re.search(r"\b(20\d{2})\b", text)
    if not (day_m and month_m and year_m):
        raise ValueError(f"No se pudo leer la fecha: {text}")
    day = int(day_m.group(1))
    month = MESES.get(month_m.group(1).lower())
    year = int(year_m.group(1))
    if not month:
        raise ValueError(f"Mes no reconocido: {month_m.group(1)}")
    print(f"Fecha base: {year}-{month:02d}-{day:02d}")
    return datetime(year, month, day)

def detect_columns(words):
    headers = []
    for w in words:
        if w["text"] in DAY_NAMES and 90 < w["top"] < 105:
            headers.append(w)
    headers.sort(key=lambda x: x["x0"])
    if len(headers) != 7:
        raise ValueError(f"Se esperaban 7 días, se encontraron {len(headers)}")

    columns = []
    for i, h in enumerate(headers):
        x0 = h["x0"] - 15
        if i + 1 < len(headers):
            x1 = (h["x1"] + headers[i+1]["x0"]) / 2
        else:
            x1 = h["x1"] + 40
        columns.append({
            "name": h["text"],
            "offset": i,
            "x0": x0,
            "x1": x1,
        })
    return columns

def detect_time_slots(words):
    markers = []
    for w in words:
        if w["x0"] < 40:
            t = w["text"].strip()
            if re.match(r"^\d{1,2}:\d{2}\( ", t) or re.match(r"^:\d{2} \)", t):
                markers.append((w["top"], t))
    markers.sort()
    if not markers:
        raise ValueError("No se encontraron marcadores de hora")
    return [{"y": y, "index": i, "label": label} for i, (y, label) in enumerate(markers)]

def y_to_slot(y: float, slots) -> int:
    best = 0
    for s in slots:
        if s["y"] <= y + 2:
            best = s["index"]
        else:
            break
    return best

def slot_to_dt(base: datetime, slot: int) -> datetime:
    return base + timedelta(minutes=slot * 15)

def is_noise(text: str) -> bool:
    t = text.strip().upper()
    if t in SKIP_PURE:
        return True
    if re.match(r"^\d{1,2}:\d{2}\( ", t) or re.match(r"^:\d{2} \)", t):
        return True
    if len(t) <= 1 and t not in {"A", "B"}:
        return True
    return False

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
        if not t or is_noise(t):
            continue
        parts.append(t)
    if not parts:
        return ""
    cleaned = []
    for p in parts:
        if not cleaned or cleaned[-1].upper() != p.upper():
            cleaned.append(p)
    title = to_title(" ".join(cleaned))
    if len(title) < 4:
        return ""
    return title

def parse_schedule(words, base_date: datetime):
    columns = detect_columns(words)
    slots = detect_time_slots(words)
    print(f"Columnas: {len(columns)}, slots: {len(slots)}")

    programs = []

    for col in columns:
        col_words = [
            w for w in words
            if col["x0"] <= w["x0"] < col["x1"]
            and w["top"] > 100
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
            if gap < 8.0:
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
            if not title:
                continue

            y_min = min(w["top"] for w in block)
            y_max = max(w["top"] for w in block)

            start_slot = y_to_slot(y_min, slots)
            end_slot = y_to_slot(y_max, slots) + 1
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
        print(f"Palabras: {len(words)}")

        base_date = parse_base_date(words)
        clean = parse_schedule(words, base_date)
        print(f"Programas: {len(clean)}")

        json_str = json.dumps(clean, ensure_ascii=False, indent=2)
        json.loads(json_str)

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(json_str + "\n")

        print(f"JSON escrito en {OUTPUT_FILE}")
        for item in clean[:6]:
            print(f"  {item['sta']} → {item['end']} | {item['titulo'][:50]}")

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
