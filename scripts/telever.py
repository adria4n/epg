#!/usr/bin/env python3
import json
import sys
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import re
import fitz

PDF_URL = "https://televisaregional.tv/pdf/veracruz-c8.pdf"
TZ = ZoneInfo("America/Mexico_City")
OUTPUT_FILE = "telever.json"

def download_pdf(url, dest="temp_programacion.pdf"):
    print(f"Descargando: {url}", file=sys.stderr)
    with urllib.request.urlopen(url) as r:
        data = r.read()
    with open(dest, "wb") as f:
        f.write(data)
    return dest

def clean_title(raw):
    t = str(raw).replace("\n", " ").strip()
    t = re.sub(r'\s+', ' ', t)
    t = re.sub(r'\b(GRABADO|REPETICION|REPETICIÓN|EN VIVO|VIVO|LOCAL)\b', '', t, flags=re.IGNORECASE)
    t = re.sub(r'\s+(A|B|AA|B-15|B15|C)\s*$', '', t)
    t = re.sub(r'\s+', ' ', t).strip(" -.,")
    return t.title() if t else ""

def main():
    pdf_path = download_pdf(PDF_URL)
    doc = fitz.open(pdf_path)
    page = doc[0]
    W = page.rect.width
    base = datetime(2026, 11, 2, tzinfo=TZ)

    words = page.get_text("words")
    times = []
    for x0, y0, x1, y1, txt, *_ in words:
        if re.match(r'^\d{1,2}:\d{2}$', txt) and (x0 < 90 or x0 > W - 90):
            h, m = map(int, txt.split(":"))
            times.append((y0, h * 60 + m))
    times = sorted(set(times))

    def y_to_mins(y):
        best = times[0][1]
        bd = abs(y - times[0][0])
        for yy, mm in times:
            d = abs(y - yy)
            if d < bd:
                bd = d
                best = mm
        return best

    headers = []
    for x0, y0, x1, y1, txt, *_ in words:
        if txt.upper() in ["LUNES", "MARTES", "MIÉRCOLES", "MIERCOLES", "JUEVES", "VIERNES", "SÁBADO", "SABADO", "DOMINGO"]:
            headers.append(((x0 + x1) / 2, txt.upper()))
    headers = sorted(headers)
    centers = [c for c, _ in headers]

    blocks = page.get_text("blocks")
    programs = []
    seen = set()

    for x0, y0, x1, y1, txt, *_ in blocks:
        txt = txt.strip()
        if not txt:
            continue
        if re.match(r'^\d{1,2}:\d{2}$', txt):
            continue
        if "LUNES" in txt.upper() and "MARTES" in txt.upper():
            continue
        if txt.upper() in ["LUNES", "MARTES", "MIÉRCOLES", "MIERCOLES", "JUEVES", "VIERNES", "SÁBADO", "SABADO", "DOMINGO"]:
            continue
        if x0 < 70 or x0 > W - 70:
            continue
        title = clean_title(txt)
        if len(title) < 3:
            continue

        days = []
        for i, dc in enumerate(centers):
            left = 80 if i == 0 else (centers[i-1] + dc) / 2
            right = W - 40 if i == len(centers)-1 else (dc + centers[i+1]) / 2
            if left <= x0 < right or left < x1 <= right or (x0 <= left and x1 >= right):
                days.append(i)
        if not days:
            cx = (x0 + x1) / 2
            days = [min(range(len(centers)), key=lambda i: abs(cx - centers[i]))]

        sm = y_to_mins(y0)
        em = y_to_mins(y1)
        if em <= sm:
            em = sm + 60

        for d in days:
            s = base + timedelta(days=d, hours=sm//60, minutes=sm%60)
            e = base + timedelta(days=d, hours=em//60, minutes=em%60)
            if e <= s:
                continue
            k = (s, e, title, d)
            if k in seen:
                continue
            seen.add(k)
            programs.append({"titulo": title, "sta": s.strftime("%Y-%m-%d/%H:%M"), "end": e.strftime("%Y-%m-%d/%H:%M")})

    programs = sorted(programs, key=lambda x: x["sta"])

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(programs, f, indent=2, ensure_ascii=False)

    print(f"Listo: {len(programs)} programas en {OUTPUT_FILE}", file=sys.stderr)
    for p in programs:
        if p["sta"].startswith("2026-11-06"):
            print(f"  {p['sta']} - {p['end']} - {p['titulo']}", file=sys.stderr)

if __name__ == "__main__":
    main()
