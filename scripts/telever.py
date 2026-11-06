#!/usr/bin/env python3
"""
Script adaptado para descargar y parsear automáticamente
la programación de Televisa Regional (XHAI-TDT Las Lajas)
y generar JSON de EPG compatible con el formato de Star TV.
"""

import json
import sys
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import pdfplumber
import re

PDF_URL = "https://televisaregional.tv/pdf/veracruz-c8.pdf"
TZ = ZoneInfo("America/Mexico_City")
OUTPUT_FILE = "xhai_tdt_las_lajas.json"

def download_pdf(url, dest="temp_programacion.pdf"):
    print(f"Descargando PDF: {url}", file=sys.stderr)
    with urllib.request.urlopen(url) as resp:
        with open(dest, "wb") as f:
            f.write(resp.read())
    return dest

def parse_pdf_schedule(pdf_path):
    """Extrae la programación del PDF y la convierte en lista de eventos."""
    programs = []
    
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[0]
        tables = page.extract_tables()
        if not tables:
            print("No se encontraron tablas en el PDF", file=sys.stderr)
            return programs
        
        table = tables[0]
        current_date = datetime(2026, 11, 2, tzinfo=TZ)  # Lunes 02
        
        for row_idx, row in enumerate(table[1:], start=1):
            if not row or not row[0]:
                continue
                
            time_str = str(row[0]).strip()
            if not re.match(r'\d{2}:\d{2}|:\d{2}', time_str):
                continue
            
            if time_str.startswith(":"):
                hour_part = table[row_idx-1][0] if row_idx > 0 else "00:00"
                if hour_part and ":" in str(hour_part):
                    base_hour = str(hour_part).split(":")[0]
                    time_str = f"{base_hour}{time_str}"
                else:
                    continue
            
            try:
                hour, minute = map(int, time_str.split(":"))
            except:
                continue
            
            for day_offset in range(7):
                cell = row[day_offset + 1] if day_offset + 1 < len(row) else None
                if not cell or not str(cell).strip():
                    continue
                
                title_raw = str(cell).replace("\n", " ").strip()
                if not title_raw or title_raw in ["", "None"]:
                    continue
                
                title = re.sub(r'\s+', ' ', title_raw)
                title = title.replace("GRABADO", "").replace("REPETICIÓN", "").replace("LOCAL", "").replace("VIVO", "").strip()
                title = re.sub(r'\s+', ' ', title).strip(" -")
                
                if len(title) < 3:
                    continue
                
                tipo = ""
                cell_upper = str(cell).upper()
                if "LOCAL" in cell_upper:
                    tipo = "LOCAL"
                elif "VIVO" in cell_upper:
                    tipo = "VIVO"
                elif "REPETICIÓN" in cell_upper or "REPETICION" in cell_upper:
                    tipo = "REPETICIÓN"
                elif "GRABADO" in cell_upper:
                    tipo = "GRABADO"
                
                if tipo and tipo not in title:
                    title = f"{title} ({tipo})"
                
                start = current_date.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=day_offset)
                end = start + timedelta(minutes=60)
                
                programs.append({
                    "titulo": title,
                    "sta": start.strftime("%Y-%m-%d/%H:%M"),
                    "end": end.strftime("%Y-%m-%d/%H:%M"),
                })
    
    seen = set()
    unique = []
    for p in programs:
        key = (p["sta"], p["titulo"])
        if key not in seen:
            seen.add(key)
            unique.append(p)
    
    unique.sort(key=lambda x: x["sta"])
    return unique

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
        
        print("\nMuestra:", file=sys.stderr)
        for p in programs[:5]:
            print(f"  {p['sta']} - {p['titulo']}", file=sys.stderr)
            
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
