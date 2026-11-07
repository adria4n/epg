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
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="es-MX",
            viewport={"width": 1400, "height": 900}
        )
        page = context.new_page()
        print("Abriendo página...", file=sys.stderr)
        page.goto(URL, wait_until="networkidle", timeout=90000)
        page.wait_for_timeout(8000)

        # Cerrar modales
        for txt in ["Aceptar", "Continuar", "Cerrar", "OK", "Acepto", "Entendido"]:
            try:
                page.get_by_text(txt, exact=False).first.click(timeout=1000)
            except:
                pass

        print("\n=== DEBUG: Textos visibles en la zona del selector ===", file=sys.stderr)
        debug = page.evaluate("""
            () => {
                const texts = [];
                document.querySelectorAll('button, div, span, a, select, option').forEach(el => {
                    const t = (el.innerText || '').trim();
                    if (t && t.length < 40 && /HOY|NOV|DOM|LUN|MAR|MIÉ|JUE|VIE|SÁB/i.test(t)) {
                        texts.push(t);
                    }
                });
                return [...new Set(texts)].slice(0, 30);
            }
        """)
        for t in debug:
            print(f"  '{t}'", file=sys.stderr)

        results = {c: [] for c in CANALES}

        # Intentar abrir el dropdown de días de varias formas
        opened = False
        for selector in [
            "text=HOY",
            "text=/HOY/i",
            "[class*='day']",
            "[class*='date']",
            "button:has-text('HOY')",
            "div:has-text('HOY')",
        ]:
            try:
                page.locator(selector).first.click(timeout=2000)
                page.wait_for_timeout(800)
                opened = True
                print(f"Dropdown abierto con: {selector}", file=sys.stderr)
                break
            except:
                continue

        if not opened:
            print("No se pudo abrir el selector de días. Revisa el debug de arriba.", file=sys.stderr)

        dias = ["HOY", "DOM", "LUN", "MAR", "MIÉ", "JUE"]

        for dia in dias:
            print(f"\nSeleccionando día que contenga: {dia}", file=sys.stderr)
            try:
                # Buscar cualquier elemento que contenga el texto del día
                loc = page.get_by_text(dia, exact=False).first
                loc.click(timeout=4000)
                page.wait_for_timeout(2500)
                print(f"  OK: {dia}", file=sys.stderr)
            except Exception as e:
                print(f"  Falló {dia}: {e}", file=sys.stderr)
                continue

            # Extraer programas
            data = page.evaluate("""
                (canales) => {
                    const out = {};
                    canales.forEach(c => out[c] = []);
                    document.querySelectorAll('div, tr, section, li').forEach(el => {
                        const text = (el.innerText || '').trim();
                        for (const c of canales) {
                            if (text.includes(c) && text.length > 10 && text.length < 800) {
                                const lines = text.split(/\\n|\\r/).map(l => l.trim())
                                    .filter(l => l.length > 4 && !l.includes(c) && !/HOY|NOV|\\d{1,2}:\\d{2}/.test(l));
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

    # Generar JSON
    now = datetime.now(TZ)
    for cid in CANALES:
        titles = list(dict.fromkeys([t for t in results[cid] if len(t) > 3]))
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
