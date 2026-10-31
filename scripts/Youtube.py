#!/usr/bin/env python3
"""
Convierte un DIRECTO de YouTube en m3u8 100% live
Requiere: yt-dlp y ffmpeg
"""

import subprocess
import sys
import os

def youtube_live_to_m3u8(youtube_url: str, output_name: str = "live"):
    output_m3u8 = f"{output_name}.m3u8"
    output_dir = f"{output_name}_segments"

    os.makedirs(output_dir, exist_ok=True)

    print(f"Iniciando live desde: {youtube_url}")
    print(f"m3u8 en vivo: {output_m3u8}")
    print("Presiona Ctrl+C para detener\n")

    yt_cmd = [
        "yt-dlp",
        "-f", "best",
        "-o", "-",
        "--no-warnings",
        "--live-from-start",
        youtube_url
    ]

    ff_cmd = [
        "ffmpeg",
        "-re",
        "-i", "pipe:0",
        "-c", "copy",
        "-f", "hls",
        "-hls_time", "4",
        "-hls_list_size", "6",
        "-hls_flags", "delete_segments+append_list",
        "-hls_segment_filename", f"{output_dir}/seg_%03d.ts",
        output_m3u8
    ]

    try:
        yt_process = subprocess.Popen(yt_cmd, stdout=subprocess.PIPE)
        ff_process = subprocess.Popen(ff_cmd, stdin=yt_process.stdout)
        yt_process.stdout.close()
        ff_process.wait()
    except KeyboardInterrupt:
        print("\nStream detenido")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # Prueba con el directo que mandaste
    url = "https://www.youtube.com/live/i8CofgVJ_K8"
    nombre = "youtube_live_test"

    if len(sys.argv) >= 2:
        url = sys.argv[1]
    if len(sys.argv) >= 3:
        nombre = sys.argv[2]

    youtube_live_to_m3u8(url, nombre)
