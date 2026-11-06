
#!/usr/bin/env python3

import json
import sys
import urllib.request
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from collections import defaultdict

import pdfplumber

# ==========================================================
# CONFIGURACION
# ==========================================================

PDF_URL = "https://televisaregional.tv/pdf/veracruz-c8.pdf"

TZ = ZoneInfo("America/Mexico_City")

OUTPUT_FILE = "telever.json"

TEMP_FILE = "temp_programacion.pdf"

# Primer dia del PDF
START_DATE = datetime(2026, 11, 2, tzinfo=TZ)

DIAS = [
    "lunes",
    "martes",
    "miércoles",
    "jueves",
    "viernes",
    "sábado",
    "domingo"
]

# Separacion vertical para unir lineas de un mismo programa
LINE_TOLERANCE = 3

# Distancia maxima entre lineas de un mismo bloque
BLOCK_GAP = 14


# ==========================================================
# DESCARGAR PDF
# ==========================================================

def download_pdf(url, dest=TEMP_FILE):

    print("Descargando PDF...", file=sys.stderr)

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    with urllib.request.urlopen(request, timeout=40) as response:

        with open(dest, "wb") as file:
            file.write(response.read())

    return dest


# ==========================================================
# LIMPIAR TITULOS
# ==========================================================

def clean_title(raw):

    title = str(raw).replace("\n", " ")

    title = re.sub(r"\s+", " ", title).strip()

    # Eliminar informacion que no pertenece al titulo
    title = re.sub(
        r"\b(GRABADO|REPETICIÓN|REPETICION|LOCAL|VIVO|B-15)\b",
        "",
        title,
        flags=re.IGNORECASE
    )

    # Eliminar indicadores A/B al final
    title = re.sub(
        r"\s+\b[AB]\b\s*$",
        "",
        title,
        flags=re.IGNORECASE
    )

    # Limpiar caracteres sobrantes
    title = re.sub(r"\s+", " ", title)

    title = title.strip(" -.,:")

    if len(title) < 3:
        return ""

    return title.title()


# ==========================================================
# IDENTIFICAR COLUMNAS DE LOS DIAS
# ==========================================================

def get_day_columns(words):

    centers = {}

    for day in DIAS:

        matches = [
            word for word in words
            if word["text"].lower().startswith(day)
        ]

        if not matches:
            raise ValueError(
                f"No se encontro la columna del dia: {day}"
            )

        word = min(matches, key=lambda w: w["top"])

        centers[day] = (
            word["x0"] + word["x1"]
        ) / 2

    return centers


# ==========================================================
# IDENTIFICAR ESCALA HORARIA DEL PDF
# ==========================================================

def get_time_anchors(words, first_day_x):

    anchors = []

    for word in words:

        text = word["text"].strip()

        # Solamente horas de la columna izquierda
        if word["x0"] >= first_day_x:
            continue

        match = re.fullmatch(
            r"(\d{2}):(\d{2})",
            text
        )

        if not match:
            continue

        hour = int(match.group(1))
        minute = int(match.group(2))

        if hour > 23 or minute != 0:
            continue

        y = (word["top"] + word["bottom"]) / 2

        anchors.append((y, hour * 60))

    anchors = sorted(set(anchors))

    if len(anchors) < 20:
        raise ValueError(
            "No se pudieron identificar suficientes "
            "marcas horarias en el PDF."
        )

    return anchors


# ==========================================================
# CONVERTIR COORDENADAS DEL PDF A MINUTOS
# ==========================================================

def y_to_minutes(y, anchors):

    for index in range(len(anchors) - 1):

        y1, m1 = anchors[index]
        y2, m2 = anchors[index + 1]

        if y1 <= y <= y2:

            if y2 == y1:
                return m1

            ratio = (y - y1) / (y2 - y1)

            return m1 + ratio * (m2 - m1)

    # Extrapolacion de los extremos
    if y < anchors[0][0]:

        y1, m1 = anchors[0]
        y2, m2 = anchors[1]

    else:

        y1, m1 = anchors[-2]
        y2, m2 = anchors[-1]

    if y2 == y1:
        return m1

    return m1 + ((y - y1) / (y2 - y1)) * (m2 - m1)


# ==========================================================
# AGRUPAR PALABRAS EN LINEAS
# ==========================================================

def group_lines(words):

    words = sorted(
        words,
        key=lambda w: (w["top"], w["x0"])
    )

    lines = []

    for word in words:

        if not lines:

            lines.append([word])
            continue

        previous_top = sum(
            w["top"] for w in lines[-1]
        ) / len(lines[-1])

        if abs(word["top"] - previous_top) <= LINE_TOLERANCE:

            lines[-1].append(word)

        else:

            lines.append([word])

    result = []

    for line in lines:

        line = sorted(line, key=lambda w: w["x0"])

        text = " ".join(
            w["text"] for w in line
        )

        result.append({
            "text": text,
            "top": min(w["top"] for w in line),
            "bottom": max(w["bottom"] for w in line),
            "words": line
        })

    return result


# ==========================================================
# AGRUPAR LINEAS EN BLOQUES DE PROGRAMACION
# ==========================================================

def group_program_blocks(lines):

    if not lines:
        return []

    blocks = []

    current = [lines[0]]

    for line in lines[1:]:

        previous = current[-1]

        gap = line["top"] - previous["bottom"]

        if gap <= BLOCK_GAP:

            current.append(line)

        else:

            blocks.append(current)

            current = [line]

    blocks.append(current)

    result = []

    for block in blocks:

        raw_title = " ".join(
            line["text"] for line in block
        )

        title = clean_title(raw_title)

        if not title:
            continue

        top = min(
            line["top"] for line in block
        )

        bottom = max(
            line["bottom"] for line in block
        )

        center = (top + bottom) / 2

        result.append({
            "titulo": title,
            "center": center
        })

    return result


# ==========================================================
# REDONDEAR A INTERVALOS DE 15 MINUTOS
# ==========================================================

def round_quarter(minutes):

    return int(round(minutes / 15) * 15)


# ==========================================================
# FORMATEAR FECHA
# ==========================================================

def format_datetime(day_offset, minutes):

    date = START_DATE + timedelta(days=day_offset)

    date = date.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0
    )

    date += timedelta(minutes=minutes)

    return date.strftime("%Y-%m-%d/%H:%M")


# ==========================================================
# EXTRAER PROGRAMACION
# ==========================================================

def parse_pdf_schedule(pdf_path):

    programs = []

    with pdfplumber.open(pdf_path) as pdf:

        page = pdf.pages[0]

        words = page.extract_words(
            x_tolerance=2,
            y_tolerance=3,
            keep_blank_chars=False,
            use_text_flow=False
        )

        if not words:
            raise ValueError(
                "El PDF no contiene texto extraible."
            )

        # Identificar columnas
        day_centers = get_day_columns(words)

        ordered_days = [
            day_centers[day]
            for day in DIAS
        ]

        # Limites entre columnas
        boundaries = []

        for index in range(len(ordered_days) - 1):

            boundaries.append(
                (ordered_days[index] + ordered_days[index + 1]) / 2
            )

        # Escala de horas
        anchors = get_time_anchors(
            words,
            ordered_days[0]
        )

        # Procesar cada dia
        for day_index, day in enumerate(DIAS):

            print(
                f"Procesando {day}...",
                file=sys.stderr
            )

            day_words = []

            for word in words:

                x = (word["x0"] + word["x1"]) / 2

                # Ignorar encabezados
                if word["top"] < 35:
                    continue

                # Ignorar textos del eje horario
                if x < ordered_days[0] - 20:
                    continue

                # Determinar columna
                assigned_day = 0

                for boundary in boundaries:

                    if x > boundary:
                        assigned_day += 1
                    else:
                        break

                if assigned_day != day_index:
                    continue

                # Ignorar etiquetas horarias
                if re.fullmatch(
                    r"\d{2}:\d{2}|:\d{2}",
                    word["text"]
                ):
                    continue

                day_words.append(word)

            # Crear lineas
            lines = group_lines(day_words)

            # Crear bloques
            blocks = group_program_blocks(lines)

            # Ordenar por posicion vertical
            blocks.sort(
                key=lambda item: item["center"]
            )

            # Convertir centros a minutos
            detected = []

            for block in blocks:

                minute = y_to_minutes(
                    block["center"],
                    anchors
                )

                minute = round_quarter(minute)

                minute = max(0, min(1440, minute))

                detected.append({
                    "titulo": block["titulo"],
                    "center": minute
                })

            # Eliminar duplicados cercanos
            filtered = []

            for item in detected:

                if filtered:

                    previous = filtered[-1]

                    if (
                        item["titulo"] == previous["titulo"]
                        and abs(
                            item["center"] - previous["center"]
                        ) <= 15
                    ):
                        continue

                filtered.append(item)

            # Calcular limites entre bloques
            if not filtered:
                print(
                    f"ADVERTENCIA: No se detectaron programas el {day}",
                    file=sys.stderr
                )
                continue

            boundaries_minutes = [0]

            for index in range(len(filtered) - 1):

                current_center = filtered[index]["center"]

                next_center = filtered[index + 1]["center"]

                middle = round_quarter(
                    (current_center + next_center) / 2
                )

                boundaries_minutes.append(middle)

            boundaries_minutes.append(1440)

            # Crear JSON
            for index, item in enumerate(filtered):

                start_minute = boundaries_minutes[index]

                end_minute = boundaries_minutes[index + 1]

                if end_minute <= start_minute:
                    continue

                programs.append({
                    "titulo": item["titulo"],
                    "sta": format_datetime(
                        day_index,
                        start_minute
                    ),
                    "end": format_datetime(
                        day_index,
                        end_minute
                    )
                })

            print(
                f"  {len(filtered)} bloques detectados",
                file=sys.stderr
            )

    # Orden cronologico
    programs.sort(
        key=lambda item: item["sta"]
    )

    # Eliminar duplicados exactos
    unique = []
    seen = set()

    for program in programs:

        key = (
            program["sta"],
            program["end"],
            program["titulo"]
        )

        if key in seen:
            continue

        seen.add(key)

        unique.append(program)

    return unique


# ==========================================================
# MAIN
# ==========================================================

def main():

    try:

        pdf_path = download_pdf(PDF_URL)

        print(
            "Analizando bloques de programacion...",
            file=sys.stderr
        )

        programs = parse_pdf_schedule(pdf_path)

        if not programs:

            raise ValueError(
                "No se extrajo ninguna programacion."
            )

        with open(
            OUTPUT_FILE,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                programs,
                file,
                indent=2,
                ensure_ascii=False
            )

        print(
            "\n================================",
            file=sys.stderr
        )

        print(
            f"LISTO: {len(programs)} programas",
            file=sys.stderr
        )

        print(
            f"Archivo: {OUTPUT_FILE}",
            file=sys.stderr
        )

        print(
            "================================",
            file=sys.stderr
        )

        print(
            "\nMuestra:",
            file=sys.stderr
        )

        for program in programs[:10]:

            print(
                f"{program['sta']} - "
                f"{program['end']} | "
                f"{program['titulo']}",
                file=sys.stderr
            )

    except Exception as error:

        print(
            f"\nERROR: {error}",
            file=sys.stderr
        )

        sys.exit(1)


if __name__ == "__main__":
    main()
