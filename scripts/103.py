#!/usr/bin/env python3

import json
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

CHANNEL = "103"
TZ = ZoneInfo("America/Mexico_City")
OUTPUT_FILE = "mvshub-103.json"

def scrape_channel(channel_number: str) -> list[dict]:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        print(f"Cargando EPG...", file=sys.stderr)
        page.goto("https://mvshub.com.mx/#spa/epg", wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(6000)
        data = page.evaluate("""
            (targetChannel) => {
                const channels = document.querySelectorAll('.epg-channel');
                const scheduleRows = document.querySelectorAll('.epg-schedules');
                let channelIdx = -1;
                channels.forEach((ch, idx) => {
                    const num = ch.querySelector('.number')?.innerText?.trim();
                    if (num === targetChannel) channelIdx = idx;
                });
                if (channelIdx === -1 || !scheduleRows[channelIdx]) return {error: true};
                const row = scheduleRows[channelIdx];
                const progs = [];
                row.querySelectorAll('.epg-schedule').forEach(prog => {
                    const content = prog.querySelector('.epg-schedule-content');
                    const fullText = content ? content.innerText : prog.innerText;
                    const lines = fullText.split('\\n').map(l => l.trim()).filter(Boolean);
                    const title = lines[0] || '';
                    if (title) {
                        const rect = prog.getBoundingClientRect();
                        const parentRect = row.getBoundingClientRect();
                        progs.push({
                            titulo: title,
                            left: rect.left - parentRect.left,
                            width: rect.width
                        });
                    }
                });
                return {programs: progs};
            }
        """, channel_number)
        browser.close()
        if data.get("error"):
            print(f"Canal {channel_number} no encontrado", file=sys.stderr)
            return []
        now = datetime.now(TZ)
        base = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=2)
        programs = []
        progs_data = data.get("programs", [])
        if not progs_data:
            return []
        total_width = sum(p["width"] for p in progs_data) or 1
        current = base
        for p in progs_data:
            duration_min = max(15, int((p["width"] / total_width) * 6 * 60))
            end = current + timedelta(minutes=duration_min)
            programs.append({
                "titulo": p["titulo"],
                "sta": current.strftime("%Y-%m-%d/%H:%M"),
                "end": end.strftime("%Y-%m-%d/%H:%M"),
            })
            current = end
        print(f"Canal {channel_number}: {len(programs)} programas", file=sys.stderr)
        return programs

def main():
    programs = scrape_channel(CHANNEL)
    if programs:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(programs, f, indent=2, ensure_ascii=False)
        print(f"Listo: {len(programs)} programas en {OUTPUT_FILE}", file=sys.stderr)
    else:
        print("Sin resultados", file=sys.stderr)

if __name__ == "__main__":
    main()
