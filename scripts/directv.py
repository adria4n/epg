#!/usr/bin/env python3
"""
EPG DSPORTS - Canales 1610, 1612, 1613
https://www.directvsports.com/programacion/
"""

import json
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

TZ = ZoneInfo("America/Mexico_City")
URL = "https://www.directvsports.com/programacion/"

# Canales que quieres
CANALES = {
    "1610": "DSPORTS",
    "1612": "DSPORTS 2",
    "1613": "DSPORTS+",
}

def extract_grid(page):
    """Extrae programas visibles del grid actual"""
    return page.evaluate("""
        () => {
            const result = {};
            // Ajusta los selectores según el DOM real (inspecciona con DevTools)
            document.querySelectorAll('[class*="channel"], [class*="row"], .epg-row, tr').forEach(row => {
                const numEl = row.querySelector('[class*="number"], .channel-number, .num');
                if (!numEl) return;
                const num = (numEl.innerText || '').trim();
                if (!['1610','1612','1613'].includes(num)) return;

                const programs = [];
                row.querySelectorAll('[class*="program"], .event, .show, td:not(.channel)').forEach(cell => {
                    const title = (cell.innerText || '').trim();
                    if (title && title.length > 2) {
                        programs.push(title);
                    }
                });
                if (programs.length) result[num] = programs;
            });
            return result;
        }
    """)

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="es-MX",
            viewport={"width": 1400, "height": 900}
        )
        page = context.new_page()

        print("Cargando programación DSPORTS...", file=sys.stderr)
        page.goto(URL, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(5000)

        # Cerrar posibles modales / aceptar cookies si aparecen
        for txt in ["Aceptar", "Continuar", "Cerrar", "OK"]:
            try:
                page.get_by_text(txt, exact=False).first.click(timeout=2000)
            except:
                pass

        all_programs = {}

        # Días a scrapear (HOY + siguientes)
        days = ["HOY", "DOM, 8 NOV.", "LUN, 9 NOV.", "MAR, 10 NOV.", "MIÉ, 11 NOV.", "JUE, 12 NOV."]

        for day_label in days:
            print(f"Procesando: {day_label}", file=sys.stderr)
            try:
                # Abrir selector de día si está cerrado
                page.get_by_text("HOY", exact=False).first.click(timeout=3000)
                page.wait_for_timeout(800)
                page.get_by_text(day_label, exact=False).first.click(timeout=5000)
                page.wait_for_timeout(2500)
            except Exception as e:
                print(f"  No se pudo seleccionar {day_label}: {e}", file=sys.stderr)
                continue

            grid = extract_grid(page)
            for cid, titles in grid.items():
                if cid not in all_programs:
                    all_programs[cid] = []
                all_programs[cid].extend(titles)

        browser.close()

    # Generar JSON por canal (mismo formato que tu script original)
    now = datetime.now(TZ)
    for cid, titles in all_programs.items():
        programs = []
        # Aquí puedes mejorar el parseo de horas si el grid las expone
        base = now.replace(hour=0, minute=0, second=0, microsecond=0)
        for i, title in enumerate(titles):
            sta = base + timedelta(minutes=30 * i)
            end = sta + timedelta(minutes=30)
            programs.append({
                "titulo": title,
                "sta": sta.strftime("%Y-%m-%d/%H:%M"),
                "end": end.strftime("%Y-%m-%d/%H:%M"),
            })

        outfile = f"{cid}.json"
        with open(outfile, "w", encoding="utf-8") as f:
            json.dump(programs, f, indent=2, ensure_ascii=False)
        print(f"Listo: {len(programs)} programas → {outfile}", file=sys.stderr)

if __name__ == "__main__":
    main()
