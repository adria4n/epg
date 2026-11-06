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
    title = re.sub(r'\b(GRABADO|REPETICIÓN|REPETICION|EN VIVO|VIVO|LOCAL)\b', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\s+(A|B|AA|B-15|B15|C|D)\s*$', '', title)
    title = re.sub(r'\s+(A|B)\b', ' ', title)
    title = re.sub(r'\s+', ' ', title).strip(" -.,")
    if not title:
        return ""
    return title.title()

def parse_pdf_schedule(pdf_path):
    programs_por_dia = {i: [] for i in range(7)}
    base_date = datetime(2026, 11, 2, tzinfo=TZ)
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[0]
        words = page.extract_words(x_tolerance=2, y_tolerance=3, keep_blank_chars=False)
        if not words:
            return []
        words = sorted(words, key=lambda w: (round(w["top"] / 5) * 5, w["x0"]))
        rows = []
        for w in words:
            placed = False
            for r in rows:
                if abs(w["top"] - r[0]["top"]) < 8:
                    r.append(w)
                    placed = True
                    break
            if not placed:
                rows.append([w])
        rows = sorted(rows, key=lambda r: min(w["top"] for w in r))
        header_idx = -1
        header_xs = []
        for idx, r in enumerate(rows):
            texts = [w["text"].upper() for w in r]
            joined = " ".join(texts)
            if "LUNES" in joined and "MARTES" in joined:
                header_idx = idx
                header_xs = sorted([w["x0"] for w in r if w["text"].upper() in ["LUNES", "MARTES", "MIERCOLES", "MIÉRCOLES", "JUEVES", "VIERNES", "SABADO", "SÁBADO", "DOMINGO"]])
                break
        if header_idx == -1:
            return []
        col_bounds = []
        for i, x in enumerate(header_xs):
            x_start = x - 10
            x_end = header_xs[i + 1] - 10 if i + 1 < len(header_xs) else page.width
            col_bounds.append((x_start, x_end))
        time_x_limit = header_xs[0] - 10
        last_hour = 0
        last_titles = [""] * 7
        for r in rows[header_idx + 1:]:
            r_sorted = sorted(r, key=lambda w: w["x0"])
            time_words = [w for w in r_sorted if w["x0"] < time_x_limit]
            time_text = "".join([w["text"] for w in time_words]).strip()
            m_full = re.match(r'^(\d{1,2}):(\d{2})$', time_text)
            m_min = re.match(r'^:(\d{2})$', time_text)
            if m_full:
                hour = int(m_full.group(1))
                minute = int(m_full.group(2))
                last_hour = hour
            elif m_min:
                hour = last_hour
                minute = int(m_min.group(1))
            else:
                continue
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                continue
            for day_offset in range(7):
                xs, xe = col_bounds[day_offset]
                cell_words = [w for w in r_sorted if xs <= w["x0"] < xe]
                cell_text = " ".join([w["text"] for w in sorted(cell_words, key=lambda w: w["x0"])])
                cell_text = cell_text.strip()
                if not cell_text:
                    continue
                title = clean_title(cell_text)
                if len(title) < 3:
                    continue
                if title == last_titles[day_offset]:
                    continue
                last_titles[day_offset] = title
                start = base_date.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=day_offset)
                programs_por_dia[day_offset].append((start, title))
    programs = []
    for day_offset in range(7):
        dia = sorted(programs_por_dia[day_offset], key=lambda x: x[0])
        dedup = []
        seen = set()
        for start, title in dia:
            key = (start, title)
            if key not in seen:
                seen.add(key)
                dedup.append((start, title))
        dia = dedup
        for i, (start, title) in enumerate(dia):
            if i + 1 < len(dia):
                end = dia[i + 1][0]
                if end <= start:
                    continue
            else:
                end = (start + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            programs.append({
                "titulo": title,
                "sta": start.strftime("%Y-%m-%d/%H:%M"),
                "end": end.strftime("%Y-%m-%d/%H:%M"),
            })
    programs.sort(key=lambda x: x["sta"])
    return programs

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
        for p in programs[:20]:
            print(f"  {p['sta']} - {p['end']} - {p['titulo']}", file=sys.stderr)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
