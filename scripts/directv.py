#!/usr/bin/env python3
"""
EPG DSPORTS - 1610, 1612, 1613
https://www.directvsports.com/programacion/
"""

import json
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

TZ = ZoneInfo("America/Mexico_City")
URL = "https://www.directvsports.com/programacion/"
CANALES = ["1610", "1612", "1613"]

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # headless=False para que veas que funciona
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="es-MX",
            viewport={"width": 1400, "height": 900}
        )
        page = context.new_page()
        print("Abriendo página...", file=sys.stderr)
        page.goto(URL, wait_until="networkidle", timeout=90000)
        page.wait_for_timeout(6000)

        # Cerrar modales si aparecen
        for txt in ["Aceptar", "Continuar", "Cerrar", "OK", "Acepto"]:
            try:
                page.get_by_text(txt, exact=False).first.click(timeout=1500)
            except:
                pass

        results = {c: [] for c in CANALES}

        # Días a procesar
        dias = ["HOY", "DOM, 8 NOV.", "LUN, 9 NOV.", "MAR, 10 NOV.", "MIÉ, 11 NOV.", "JUE, 12 NOV."]

        for dia in dias:
            print(f"Seleccionando {dia}...", file=sys.stderr)
            try:
                page.get_by_text("HOY", exact=False).first.click(timeout=3000)
                page.wait_for_timeout(500)
                page.get_by_text(dia, exact=False).first.click(timeout=5000)
                page.wait_for_timeout(3000)
            except Exception as e:
                print(f"  Error día {dia}: {e}", file=sys.stderr)
                continue

            # Extraer programas de los canales
            data = page.evaluate("""
                (canales) => {
                    const out = {};
                    canales.forEach(c => out[c] = []);
                    // Busca filas que contengan el número de canal
                    document.querySelectorAll('div, tr, section').forEach(el => {
                        const text = el.innerText || '';
                        for (const c of canales) {
                            if (text.includes(c) && text.length < 500) {
                                const lines = text.split('\\n').map(l => l.trim()).filter(l => l && l.length > 3 && !l.includes(c));
                                if (lines.length) out[c].push(...lines);
                            }
                        }
                    });
                    return out;
                }
            """, CANALES)

            for c in CANALES:
                results[c].extend(data.get(c, []))

        browser.close()

    # Generar archivos JSON
    now = datetime.now(TZ)
    for cid in CANALES:
        titles = list(dict.fromkeys(results[cid]))  # quitar duplicados manteniendo orden
        programs = []
        base = now.replace(hour=0, minute=0, second=0, microsecond=0)
        for i, title in enumerate(titles):
            sta = base + timedelta(minutes=30 * i)
            end = sta + timedelta(minutes=30)
            programs.append({
                "titulo": title,
                "sta": sta.strftime("%Y-%m-%d/%H:%M"),
                "end": end.strftime("%Y-%m-%d/%H:%M"),
            })

        fname = f"{cid}.json"
        with open(fname, "w", encoding="utf-8") as f:
            json.dump(programs, f, indent=2, ensure_ascii=False)
        print(f"{fname} → {len(programs)} programas", file=sys.stderr)

if __name__ == "__main__":
    main()
