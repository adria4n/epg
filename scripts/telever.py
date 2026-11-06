#!/usr/bin/env python3
"""
Parser corregido para Televisa Regional (XHAI-TDT / Las Lajas).
Extrae todos los programas, incluyendo bloques largos y celdas combinadas.
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
OUTPUT_FILE = "telever.json"

COL_BOUNDS = [
    (55, 125, 0),   # Lunes
    (130, 200, 1),  # Martes
    (205, 280, 2),  # Miércoles
    (285, 355, 3),  # Jueves
    (360, 430, 4),  # Viernes
    (435, 505, 5),  # Sábado
    (510, 580, 6),  # Domingo
]


def download_pdf(url, dest="temp_programacion.pdf"):
    print(f"Descargando PDF: {url}", file=sys.stderr)
    with urllib.request.urlopen(url) as resp:
        with open(dest, "wb") as f:
            f.write(resp.read())
    return dest


def clean_title(raw: str) -> str:
    if not raw:
        return ""
    title = str(raw).replace("\n", " ").strip()
    title = re.sub(r'\s+', ' ', title)

    noise = [
        r'\bGRABADO\b', r'\bREPETICI[ÓO]N\b', r'\bLOCAL\b', r'\bVIVO\b',
        r'\bB-15\b', r'\bB\b', r'\bA\b', r'\bREPETICION\b',
        r'\bREP\s*E\s*T\s*IC\s*I[ÓO]N\b', r'\b-?\s*1\s*5\b',
        r'\bESPECIAL\b', r'\bPROGRAMA\b'
    ]
    for pattern in noise:
        title = re.sub(pattern, '', title, flags=re.IGNORECASE)

    title = re.sub(r'\s+', ' ', title).strip(" -.,")
    title = re.sub(r'\s{2,}', ' ', title)

    if len(title) < 4:
        return ""

    replacements = {
        "de admisión noches": "Derecho De Admisión",
        "noche y ya llegué": "Es De Noche Y Ya Llegué",
        "susana adicción": "Susana Adicción",
        "parrilla de fuego": "La Parrilla De Fuego",
        "dudas veracruz": "Sanando Dudas Veracruz",
        "bombazos de cherry": "Los Bombazos De Cherry",
        "que pokar! juego de la fama": "Que Pokar! El Juego De La Fama",
        "código 4": "Código 4",
        "noches de humor": "Noches De Humor",
        "noches de humor jarocho": "Noches De Humor Jarocho",
        "veredicto final": "Veredicto Final",
        "vuelve a la vida": "Vuelve A La Vida",
        "las noticias": "Las Noticias",
        "caminos de la vida": "Caminos De La Vida",
        "en la cocina con geronimo": "En La Cocina Con Gerónimo",
        "milagros de la fe": "Milagros De La Fe",
        "indio yandú": "Indio Yandú",
        "pura pasión": "Pura Pasión",
        "corazón salvaje": "Corazón Salvaje",
        "maestro sebastián": "Maestro Sebastián",
        "curandero damian": "Curandero Damian",
        "sanador francisco": "Sanador Francisco",
        "codigo n+": "Código N+",
        "vamos al bailongo": "Vamos Al Bailongo",
        "con sazón a chef": "Con Sazón A Chef",
        "problemas y soluciones": "Problemas Y Soluciones",
        "el show de figuritas": "El Show De Figuritas",
    }
    low = title.lower()
    for old, new in replacements.items():
        if old in low:
            return new

    if "cine mexicano" in low or "cine" in low:
        m = re.search(r'(alias el rata|que hombre tan simpático|cuando me vaya|ellas también son rebeldes|aventura al centro de la tierra|la madrina del diablo|pero sigo siendo el rey|el fugitivo|enamorada|el mil máscaras|el tunco maclovio)', low)
        if m:
            return "Cine Mexicano " + m.group(1).title()

    return title.title()


def extract_programs_from_pdf(pdf_path: str):
    programs = []
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[0]
        words = page.extract_words(x_tolerance=2, y_tolerance=2)

        col_data = {i: [] for i in range(7)}
        for w in words:
            if w["top"] < 105:
                continue
            for xmin, xmax, day_idx in COL_BOUNDS:
                if xmin <= w["x0"] < xmax:
                    col_data[day_idx].append((w["top"], w["text"]))
                    break

        base_date = datetime(2026, 11, 2, tzinfo=TZ)

        for day_idx in range(7):
            entries = sorted(col_data[day_idx], key=lambda x: x[0])
            if not entries:
                continue

            blocks = []
            current = []
            last_y = None
            for y, text in entries:
                if last_y is None or abs(y - last_y) < 14:
                    current.append(text)
                    last_y = y
                else:
                    if current:
                        blocks.append((last_y or y, " ".join(current)))
                    current = [text]
                    last_y = y
            if current:
                blocks.append((last_y, " ".join(current)))

            for y_pos, raw_title in blocks:
                title = clean_title(raw_title)
                if not title:
                    continue

                relative_y = max(0, y_pos - 108)
                total_min = int(round(relative_y / 6.7)) * 15
                hour = (total_min // 60) % 24
                minute = total_min % 60

                start = base_date.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=day_idx)

                duration = 60
                tl = title.lower()
                if "noticias" in tl or "vuelve a la vida" in tl:
                    duration = 120
                elif "cine mexicano" in tl and any(x in tl for x in ["aventura", "madrina", "fugitivo", "tunco"]):
                    duration = 90

                end = start + timedelta(minutes=duration)

                programs.append({
                    "titulo": title,
                    "sta": start.strftime("%Y-%m-%d/%H:%M"),
                    "end": end.strftime("%Y-%m-%d/%H:%M"),
                })

    seen = set()
    unique = []
    for p in sorted(programs, key=lambda x: x["sta"]):
        key = (p["sta"][:13], p["titulo"])
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


def main():
    try:
        pdf_path = download_pdf(PDF_URL)
        print("Parseando programación (versión corregida)...", file=sys.stderr)
        programs = extract_programs_from_pdf(pdf_path)

        if not programs:
            print("No se extrajeron programas", file=sys.stderr)
            sys.exit(1)

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(programs, f, indent=2, ensure_ascii=False)

        print(f"Listo: {len(programs)} programas en {OUTPUT_FILE}", file=sys.stderr)
        print("\nMuestra:", file=sys.stderr)
        for p in programs[:12]:
            print(f"  {p['sta']} - {p['titulo']}", file=sys.stderr)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
