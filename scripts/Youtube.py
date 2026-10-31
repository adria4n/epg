#!/usr/bin/env python3
"""
Convierte un DIRECTO de YouTube en m3u8 100% live
Requiere: yt-dlp y ffmpeg (deben estar instalados)
"""

import subprocess
import sys
import os
import shutil

def check_dependencies():
    missing = []
    if not shutil.which("yt-dlp"):
        missing.append("yt-dlp")
    if not shutil.which("ffmpeg"):
        missing.append("ffmpeg")
    if missing:
        print(f"ERROR: Faltan dependencias: {', '.join(missing)}")
        print("En GitHub Actions agrega este step antes:")
        print("  - run: |")
        print("      sudo apt-get update")
        print("      sudo apt-get install -y ffmpeg")
        print("      pip install yt-dlp")
        sys.exit(1)

def youtube_live_to_m3u8(youtube_url: str, output_name: str = "live"):
    check_dependencies()

    output_m3u8 = f"{output_name}.m3u8"
    output_dir = f"{output_name}_segments"
    os.makedirs(output_dir, exist_ok=True)

    print(f"Iniciando live desde: {youtube_url}")
    print(f"Generando: {output_m3u8}")

    cmd = (
        f'yt-dlp -f best -o - --no-warnings --live-from-start "{youtube_url}" | '
        f'ffmpeg -re -i pipe:0 -c copy -f hls '
        f'-hls_time 4 -hls_list_size 6 '
        f'-hls_flags delete_segments+append_list '
        f'-hls_segment_filename "{output_dir}/seg_%03d.ts" '
        f'"{output_m3u8}"'
    )

    try:
        subprocess.run(cmd, shell=True, check=True)
        print(f"\nListo: {output_m3u8}")
    except subprocess.CalledProcessError as e:
        print(f"Error al convertir: {e}")
        # Fallback: solo extraer URL
        try:
            result = subprocess.run(
                ["yt-dlp", "-g", "-f", "best", youtube_url],
                capture_output=True, text=True, check=True
            )
            url_m3u8 = result.stdout.strip().split("\n")[0]
            print(f"\nURL del m3u8 original:\n{url_m3u8}")
            # Guardar la URL en un archivo por si acaso
            with open(f"{output_name}_url.txt", "w") as f:
                f.write(url_m3u8)
        except Exception as e2:
            print(f"También falló extraer la URL: {e2}")

if __name__ == "__main__":
    url = "https://www.youtube.com/live/i8CofgVJ_K8"
    nombre = "youtube_live_test"

    if len(sys.argv) >= 2:
        url = sys.argv[1]
    if len(sys.argv) >= 3:
        nombre = sys.argv[2]

    youtube_live_to_m3u8(url, nombre)
