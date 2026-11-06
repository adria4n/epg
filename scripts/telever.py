#!/usr/bin/env python3
import json
import sys
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import pdfplumber
import re

PDF_URL = "https://televisaregional.tv/pdf/veracruz-c8.pdf"
TZ = ZoneInfo("America/Mexico_City")
OUTPUT_FILE = "telever.json"

def download_pdf(url, dest="temp_programacion.pdf"):
    print(f"Descargando PDF: {url}", file=sys.stderr)
    with urllib.request.urlopen(url) as resp:
        with open(dest, "wb") as f:
            f.write(resp.read())
    return dest

def clean_title(raw):
    title = str(raw).replace("\n", " ").strip()
    title = re.sub(r'\s+', ' ', title)
    title = re.sub(r'\b(GRABADO|REPETICIÓN|REPETICION|EN VIVO|VIVO|LOCAL|REPETICI[OÓ]N)\b', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\s+(A|B|AA|B-15|B15|C)\s*$', '', title)
    title = re.sub(r'\s+', ' ', title).strip(" -.,")
    if not title:
        return ""
    return title.title()

def parse_pdf_schedule(pdf_path):
    base_date = datetime(2026, 11, 2, tzinfo=TZ)
    programs = []
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[0]
        words = page.extract_words(x_tolerance=2, y_tolerance=3)
        time_marks = []
        for w in words:
            if re.match(r'^\d{1,2}:\d{2}$', w["text"]):
                if w["x0"] < 90 or w["x0"] > page.width - 90:
                    h, m = map(int, w["text"].split(":"))
                    time_marks.append((w["top"], h * 60 + m))
        time_marks = sorted(set(time_marks))
        def top_to_minutes(top):
            best = time_marks[0][1]
            best_d = abs(top - time_marks[0][0])
            for t, mins in time_marks:
                d = abs(top - t)
                if d < best_d:
                    best_d = d
                    best = mins
            return best
        def minutes_to_dt(day_offset, mins):
            return (base_date + timedelta(days=day_offset)).replace(hour=mins // 60, minute=mins % 60, second=0, microsecond=0)
        header_words = [w for w in words if w["text"].upper() in ["LUNES", "MARTES", "MIÉRCOLES", "MIERCOLES", "JUEVES", "VIERNES", "SÁBADO", "SABADO", "DOMINGO"]]
        header_words = sorted(header_words, key=lambda w: w["x0"])
        day_centers = [w["x0"] + (w["x1"] - w["x0"]) / 2 for w in header_words]
        tables = page.find_tables(table_settings={"vertical_strategy": "lines", "horizontal_strategy": "lines", "snap_tolerance": 4, "join_tolerance": 4, "edge_min_length": 20})
        if not tables:
            return []
        table = tables[0]
        seen = set()
        for cell in table.cells:
            x0, top, x1, bottom = cell
            text = page.crop((x0, top, x1, bottom)).extract_text() or ""
            text = text.strip()
            if not text:
                continue
            if re.match(r'^\d{1,2}:\d{2}$', text):
                continue
            if "LUNES" in text.upper() and "MARTES" in text.upper():
                continue
            if text.upper() in ["LUNES", "MARTES", "MIÉRCOLES", "MIERCOLES", "JUEVES", "VIERNES", "SÁBADO", "SABADO", "DOMINGO"]:
                continue
            title = clean_title(text)
            if len(title) < 3:
                continue
            cx = (x0 + x1) / 2
            days = []
            for i, dc in enumerate(day_centers):
                if i == 0:
                    left = 80
                else:
                    left = (day_centers[i - 1] + dc) / 2
                if i == len(day_centers) - 1:
                    right = page.width - 40
                else:
                    right = (dc + day_centers[i + 1]) / 2
                if left <= x0 < right or left < x1 <= right or (x0 <= left and x1 >= right):
                    days.append(i)
                elif x0 <= dc <= x1:
                    if i not in days:
                        days.append(i)
            if not days:
                dists = [(abs(cx - dc), i) for i, dc in enumerate(day_centers)]
                days = [min(dists)[1]]
            start_mins = top_to_minutes(top)
            end_mins = top_to_minutes(bottom)
            if end_mins <= start_mins:
                end_mins = start_mins + 60
            for d in days:
                start = minutes_to_dt(d, start_mins)
                end = minutes_to_dt(d, end_mins)
                if end <= start:
                    continue
                key = (start, end, title, d)
                if key in seen:
                    continue
                seen.add(key)
                programs.append({"titulo": title, "sta": start.strftime("%Y-%m-%d/%H:%M"), "end": end.strftime("%Y-%m-%d/%H:%M"), "_d": d})
    programs = sorted(programs, key=lambda x: (x["sta"], x["_d"]))
    out = []
    for p in programs:
        out.append({"titulo": p["titulo"], "sta": p["sta"], "end": p["end"]})
    return out

def main():
    try:
        pdf_path = download_pdf(PDF_URL)
        print("Parseando programación...", file=sys.stderr)
        programs = parse_pdf_schedule(pdf_path)
        if not programs:
            print("No se extrajeron programas", file=sys.stderr)
            sys.exit(1)
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(programs, f, indent=2, ensure_ascii=False)
        print(f"Listo: {len(programs)} programas en {OUTPUT_FILE}", file=sys.stderr)
        for p in programs:
            if p["sta"].startswith("2026-11-06"):
                print(f"  {p['sta']} - {p['end']} - {p['titulo']}", file=sys.stderr)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
