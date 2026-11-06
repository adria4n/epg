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
    for word in ["GRABADO", "REPETICIÓN", "REPETICION", "LOCAL", "VIVO", "B-15"]:
        title = re.sub(rf'\b{word}\b', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\s+', ' ', title).strip(" -.,")
    if not title:
        return ""
    return title.title()

def parse_pdf_schedule(pdf_path):
    programs_por_dia = {i: [] for i in range(7)}
    base_date = datetime(2026, 11, 2, tzinfo=TZ)
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[0]
        tables = page.extract_tables()
        if not tables:
            return []
        table = tables[0]
        last_hour = 0
        for row in table[1:]:
            if not row or not row[0]:
                continue
            time_str = str(row[0]).strip()
            m_full = re.match(r'^(\d{1,2}):(\d{2})$', time_str)
            m_min = re.match(r'^:(\d{2})$', time_str)
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
                cell = row[day_offset + 1] if day_offset + 1 < len(row) else None
                if not cell or not str(cell).strip():
                    continue
                title = clean_title(cell)
                if len(title) < 3:
                    continue
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
        for p in programs[:15]:
            print(f"  {p['sta']} - {p['end']} - {p['titulo']}", file=sys.stderr)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
