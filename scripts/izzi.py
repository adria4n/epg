#!/usr/bin/env python3

import json
import sys
from playwright.sync_api import sync_playwright

USERNAME = "isra@arcagroup.com.mx"
PASSWORD = "Jehova773"
OUTPUT_FILE = "izzi-license.json"

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120.0.0.0 Mobile Safari/537.36",
            viewport={"width": 412, "height": 915}
        )
        page = context.new_page()
        
        license_url = None
        
        def on_request(req):
            nonlocal license_url
            if "multi-sec.izzigo.tv" in req.url:
                license_url = req.url
                print(f"Licencia: {req.url[:80]}...", file=sys.stderr)
        
        page.on("request", on_request)
        
        print("Abriendo...", file=sys.stderr)
        page.goto("https://www.izzigo.tv/webclient/", wait_until="domcontentloaded", timeout=120000)
        page.wait_for_timeout(5000)
        
        print("Login...", file=sys.stderr)
        inputs = page.query_selector_all("input")
        for inp in inputs:
            t = (inp.get_attribute("type") or "").lower()
            p = (inp.get_attribute("placeholder") or "").lower()
            if "mail" in t or "usuario" in p or "correo" in p:
                inp.fill(USERNAME)
            elif t == "password" or "contraseña" in p:
                inp.fill(PASSWORD)
        
        page.keyboard.press("Enter")
        page.wait_for_timeout(8000)
        
        print("Buscando TV en vivo...", file=sys.stderr)
        for text in ["TV", "En vivo", "Live", "Canales", "Inicio"]:
            try:
                page.click(f"text={text}", timeout=3000)
                page.wait_for_timeout(2000)
                break
            except:
                pass
        
        try:
            page.click('[class*="channel"], [class*="card"], [class*="item"]', timeout=5000)
        except:
            pass
        
        page.wait_for_timeout(15000)
        
        browser.close()
        
        if license_url:
            with open(OUTPUT_FILE, "w") as f:
                json.dump({"license_url": license_url}, f, indent=2)
            print(f"Guardado en {OUTPUT_FILE}", file=sys.stderr)
        else:
            print("No se encontró licencia", file=sys.stderr)

if __name__ == "__main__":
    main()
