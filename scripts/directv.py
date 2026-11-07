#!/usr/bin/env python3
"""
EPG DSPORTS 1610 / 1612 / 1613
Intercepta las peticiones de la página de programación.
"""

import json
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

TZ = ZoneInfo("America/Mexico_City")
URL = "https://www.directvsports.com/programacion/"
CANALES_OBJETIVO = {"1610", "1612", "1613"}

def main():
    captured = []

    def handle_response(response):
        try:
            url = response.url
            if response.status != 200:
                return
            content_type = response.headers.get("content-type", "")
            if "json" not in content_type and "javascript" not in content_type:
                return
            # Guardar cualquier respuesta que parezca EPG / schedule / programación
            if any(k in url.lower() for k in ["epg", "schedule", "program", "guia", "guide", "canal", "channel", "event"]):
                try:
                    body = response.json()
                    captured.append({"url": url, "data": body})
                    print(f"[CAPTURA] {url[:120]}", file=sys.stderr)
                except:
                    pass
        except:
            pass

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="es-MX",
            viewport={"width": 1440, "height": 900}
        )
        page = context.new_page()
        page.on("response", handle_response)

        print("Cargando página y capturando peticiones...", file=sys.stderr)
        page.goto(URL, wait_until="networkidle", timeout=90000)
        page.wait_for_timeout(8000)

        # Intentar interactuar un poco para forzar más cargas (opcional)
        try:
            page.keyboard.press("Escape")
            page.wait_for_timeout(1000)
            # Scroll para que cargue más
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(2000)
        except:
            pass

        browser.close()

    if not captured:
        print("No se capturó ninguna petición de EPG. La página puede estar bloqueada o el endpoint cambió.", file=sys.stderr)
        # Guardar debug de todas las URLs que sí respondieron
        print("Revisa la consola del navegador (Network) y dime qué URL carga la programación.", file=sys.stderr)
        return

    print(f"\nSe capturaron {len(captured)} respuestas útiles.", file=sys.stderr)

    # Buscar datos de canales 1610/1612/1613
    programs_by_channel = {c: [] for c in CANALES_OBJETIVO}

    for item in captured:
        data = item["data"]
        # Recorrer el JSON buscando estructuras de programas
        def walk(obj, path=""):
            if isinstance(obj, dict):
                # Buscar campos típicos de canal o programa
                channel_id = None
                for key in ["channelId", "channel", "id", "numero", "number", "canal"]:
                    if key in obj and str(obj[key]) in CANALES_OBJETIVO:
                        channel_id = str(obj[key])
                        break
                if channel_id:
                    title = obj.get("title") or obj.get("titulo") or obj.get("name") or obj.get("programa") or ""
                    start = obj.get("start") or obj.get("startDate") or obj.get("sta") or obj.get("inicio")
                    end = obj.get("end") or obj.get("endDate") or obj.get("stop") or obj.get("fin")
                    if title:
                        programs_by_channel[channel_id].append({
                            "titulo": title,
                            "sta": str(start) if start else "",
                            "end": str(end) if end else "",
                            "raw": obj
                        })
                for k, v in obj.items():
                    walk(v, path + "." + k)
            elif isinstance(obj, list):
                for i, v in enumerate(obj):
                    walk(v, path + f"[{i}]")

        walk(data)

    # Escribir archivos
    now = datetime.now(TZ)
    for cid in CANALES_OBJETIVO:
        progs = programs_by_channel[cid]
        # Limpiar duplicados
        seen = set()
        clean = []
        for p in progs:
            key = (p["titulo"], p["sta"])
            if key not in seen and p["titulo"]:
                seen.add(key)
                clean.append({
                    "titulo": p["titulo"],
                    "sta": p["sta"] or now.strftime("%Y-%m-%d/%H:%M"),
                    "end": p["end"] or ""
                })

        fname = f"{cid}.json"
        with open(fname, "w", encoding="utf-8") as f:
            json.dump(clean, f, indent=2, ensure_ascii=False)
        print(f"{fname} → {len(clean)} programas", file=sys.stderr)

    if not any(programs_by_channel.values()):
        print("\nNo se encontraron programas de 1610/1612/1613 en las respuestas.", file=sys.stderr)
        print("Las URLs capturadas fueron:", file=sys.stderr)
        for c in captured:
            print(f"  {c['url']}", file=sys.stderr)
        print("\nPega aquí una de esas URLs (o el JSON que devuelve) y te armo el parser exacto.", file=sys.stderr)

if __name__ == "__main__":
    main()
