import sqlite3
import json
import sys
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hik_bot.db")
OUTPUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hik_data.json")


def main():
    if not os.path.exists(DB_PATH):
        print(f"Error: no se encontró la base de datos '{DB_PATH}'")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    cur = conn.cursor()

    cur.execute(
        "SELECT id, fecha, hora, total_aprobados, total_rechazados, "
        "total_errores, duracion_segundos FROM ejecuciones ORDER BY fecha, hora"
    )
    ejecuciones = [
        {
            "id": r["id"],
            "fecha": r["fecha"],
            "hora": r["hora"],
            "aprobados": r["total_aprobados"],
            "rechazados": r["total_rechazados"],
            "errores": r["total_errores"],
            "duracion_segundos": r["duracion_segundos"],
        }
        for r in cur.fetchall()
    ]

    cur.execute(
        "SELECT pais, empresa, certificacion, idioma, accion, motivo_error, fecha "
        "FROM usuarios ORDER BY fecha"
    )
    usuarios = [
        {
            "pais": r["pais"],
            "empresa": r["empresa"],
            "certificacion": r["certificacion"],
            "idioma": r["idioma"],
            "accion": r["accion"],
            "motivo_error": r["motivo_error"],
            "fecha": r["fecha"],
            "bot": "selfpaced" if r["idioma"] else "certificate",
        }
        for r in cur.fetchall()
    ]

    cur.execute(
        "SELECT "
        "COUNT(CASE WHEN accion='APPROVED' THEN 1 END) AS aprobados, "
        "COUNT(CASE WHEN accion='REJECTED' THEN 1 END) AS rechazados, "
        "COUNT(CASE WHEN accion='ERROR' THEN 1 END) AS errores, "
        "COUNT(CASE WHEN accion='MANUAL_REVIEW' THEN 1 END) AS manual_review "
        "FROM usuarios"
    )
    counts = cur.fetchone()

    ultima_ejecucion = None
    if ejecuciones:
        last = ejecuciones[-1]
        ultima_ejecucion = f"{last['fecha']} {last['hora']}"

    data = {
        "generado": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "totales": {
            "ejecuciones": len(ejecuciones),
            "aprobados": counts["aprobados"],
            "rechazados": counts["rechazados"],
            "errores": counts["errores"],
            "manual_review": counts["manual_review"],
            "ultima_ejecucion": ultima_ejecucion,
        },
        "ejecuciones": ejecuciones,
        "usuarios": usuarios,
    }

    conn.close()

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    total_usuarios = len(usuarios)
    print(
        f"Exportados: {len(ejecuciones)} ejecuciones, "
        f"{total_usuarios} usuarios -> {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()
