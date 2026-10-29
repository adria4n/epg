#!/usr/bin/env python3
"""
Parser de programación Telever.
"""

import json, re, requests
from datetime import datetime, timedelta
from collections import defaultdict
import pdfplumber

PDF_URL = "https://televisaregional.tv/pdf/telever-c12.pdf"
OUTPUT_FILE = "telever.json"

DAY_COLUMNS = [
    {"name": "Lunes",     "offset": 0, "x0": 40,  "x1": 130},
    {"name": "Martes",    "offset": 1, "x0": 115, "x1": 205},
    {"name": "Miércoles", "offset": 2, "x0": 190, "x1": 280},
    {"name": "Jueves",    "offset": 3, "x0": 265, "x1": 360},
    {"name": "Viernes",   "offset": 4, "x0": 345, "x1": 435},
    {"name": "Sábado",    "offset": 5, "x0": 420, "x1": 510},
    {"name": "Domingo",   "offset": 6, "x0": 495, "x1": 575},
]

Y_START = 104.0
SLOT_H = 6.45

SKIP = {"GRABADO","REPETICIÓN","REPETICION","SAP","REP","*SAP","CAMBIOS","SUJETA","AVISO","PREVIO","ULTIMA","ACTUALIZACIÓN","PROGRAMACIÓN"}
KEEP = {"B-15","B15","RTC","N+"}

MESES = {"enero":1,"febrero":2,"marzo":3,"abril":4,"mayo":5,"junio":6,"julio":7,"agosto":8,"septiembre":9,"octubre":10,"noviembre":11,"diciembre":12}

def y_to_slot(y):
    return max(0, int((y - Y_START) / SLOT_H))

def slot_to_dt(base, slot):
    return base + timedelta(minutes=slot * 15)

def is_noise(t):
    u = t.strip().upper()
    if u in SKIP: return True
    if re.match(r"^\d{1,2}:\d{2}\( ", u) or re.match(r"^:\d{2} \)", u): return True
    if re.match(r"^\d{1,2}/\d{1,2}/\d{4}", u): return True
    if len(u) <= 1 and u not in {"A","B"}: return True
    return False

def to_title(text):
    out = []
    for w in text.split():
        if w.upper() in KEEP:
            out.append(w.upper())
        else:
            out.append(w.capitalize())
    return " ".join(out)

def clean(words):
    parts = []
    for w in words:
        t = w["text"].strip()
        if t and not is_noise(t):
            parts.append(t)
    if not parts: return ""
    cleaned = []
    for p in parts:
        if not cleaned or cleaned[-1].upper() != p.upper():
            cleaned.append(p)
    title = to_title(" ".join(cleaned))
    return title if len(title) >= 4 else ""

def main():
    r = requests.get(PDF_URL, timeout=30)
    open("/tmp/telever.pdf","wb").write(r.content)
    with pdfplumber.open("/tmp/telever.pdf") as pdf:
        words = pdf.pages[0].extract_words(x_tolerance=1.5, y_tolerance=1.5)

    header = " ".join(w["text"] for w in words if w["top"] < 80)
    day = int(re.search(r"\b(\d{1,2})\b", header).group(1))
    month = MESES[re.search(r"\b(octubre|noviembre)\b", header, re.I).group(1).lower()]
    year = int(re.search(r"\b(20\d{2})\b", header).group(1))
    base = datetime(year, month, day)
    print(f"Fecha base: {base.date()}")

    programs = []
    for col in DAY_COLUMNS:
        cw = [w for w in words if col["x0"] <= w["x0"] < col["x1"] and w["top"] > 100]
        if not cw: continue
        lines = defaultdict(list)
        for w in cw:
            lines[round(w["top"]/2)*2].append(w)
        sorted_lines = [{"y": y, "words": sorted(lines[y], key=lambda x: x["x0"])} for y in sorted(lines)]

        blocks, cur, last = [], [], None
        for ln in sorted_lines:
            gap = 0 if last is None else ln["y"] - last
            if gap < 9:
                cur.extend(ln["words"])
            else:
                if cur: blocks.append(cur)
                cur = list(ln["words"])
            last = ln["y"]
        if cur: blocks.append(cur)

        day_dt = base + timedelta(days=col["offset"])
        for b in blocks:
            title = clean(b)
            if not title: continue
            y0 = min(w["top"] for w in b)
            y1 = max(w["top"] for w in b)
            s0 = y_to_slot(y0)
            s1 = y_to_slot(y1) + 1
            if s1 <= s0: s1 = s0 + 1
            programs.append({
                "titulo": title,
                "sta": slot_to_dt(day_dt, s0).strftime("%Y-%m-%d/%H:%M:%S"),
                "end": slot_to_dt(day_dt, s1).strftime("%Y-%m-%d/%H:%M:%S"),
            })

    programs.sort(key=lambda p: p["sta"])
    for i in range(len(programs)-1):
        ce = datetime.strptime(programs[i]["end"], "%Y-%m-%d/%H:%M:%S")
        ns = datetime.strptime(programs[i+1]["sta"], "%Y-%m-%d/%H:%M:%S")
        if ce.date() == ns.date() and ns > ce:
            programs[i]["end"] = programs[i+1]["sta"]

    seen, result = set(), []
    for p in programs:
        k = (p["titulo"], p["sta"])
        if k not in seen:
            seen.add(k)
            result.append(p)

    print(f"Programas: {len(result)}")
    json.dump(result, open(OUTPUT_FILE,"w"), ensure_ascii=False, indent=2)
    print(f"Escrito en {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
