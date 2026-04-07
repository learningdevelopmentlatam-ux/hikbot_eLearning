"""
=============================================================================
HIK_DB — Base de datos SQLite para HikBot v2.0
=============================================================================

Tablas:
  ejecuciones  → resumen por cada vez que corre el bot
  usuarios     → detalle de cada usuario procesado (APPROVED/REJECTED/ERROR)

=============================================================================
"""

import sqlite3
from datetime import datetime

DB_FILE = "hik_bot.db"


class HikDB:

    def __init__(self, db_file=DB_FILE):
        self.db_file = db_file
        self._crear_tablas()

    def _conn(self):
        return sqlite3.connect(self.db_file)

    def _crear_tablas(self):
        con = self._conn()
        c = con.cursor()

        c.execute("""
            CREATE TABLE IF NOT EXISTS ejecuciones (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha             TEXT NOT NULL,
                hora              TEXT NOT NULL,
                total_aprobados   INTEGER DEFAULT 0,
                total_rechazados  INTEGER DEFAULT 0,
                total_errores     INTEGER DEFAULT 0,
                duracion_segundos INTEGER DEFAULT 0
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                ejecucion_id INTEGER,
                nombre       TEXT,
                email        TEXT,
                pais         TEXT,
                empresa      TEXT,
                certificacion TEXT,
                idioma       TEXT,
                accion       TEXT,
                motivo_error TEXT,
                fecha        TEXT,
                FOREIGN KEY (ejecucion_id) REFERENCES ejecuciones(id)
            )
        """)

        con.commit()
        con.close()

    # ── Ejecuciones ───────────────────────────────────────────────────────────

    def iniciar_ejecucion(self) -> int:
        """Crea un registro de ejecución y retorna su id."""
        con = self._conn()
        ahora = datetime.now()
        c = con.cursor()
        c.execute(
            "INSERT INTO ejecuciones (fecha, hora) VALUES (?, ?)",
            (ahora.strftime("%Y-%m-%d"), ahora.strftime("%H:%M:%S"))
        )
        ejec_id = c.lastrowid
        con.commit()
        con.close()
        return ejec_id

    def cerrar_ejecucion(self, ejec_id: int, aprobados: int, rechazados: int, errores: int, duracion: int):
        """Actualiza los totales al finalizar."""
        con = self._conn()
        con.execute(
            """UPDATE ejecuciones
               SET total_aprobados=?, total_rechazados=?, total_errores=?, duracion_segundos=?
               WHERE id=?""",
            (aprobados, rechazados, errores, duracion, ejec_id)
        )
        con.commit()
        con.close()

    # ── Usuarios ──────────────────────────────────────────────────────────────

    def registrar_usuario(self, ejec_id: int, usuario: dict):
        """
        Registra un usuario procesado.
        usuario debe tener: nombre, email, pais, empresa,
                            certificacion, idioma, accion,
                            motivo_error (opcional)
        accion: 'APPROVED' | 'REJECTED' | 'ERROR'
        """
        con = self._conn()
        con.execute(
            """INSERT INTO usuarios
               (ejecucion_id, nombre, email, pais, empresa,
                certificacion, idioma, accion, motivo_error, fecha)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                ejec_id,
                usuario.get("nombre"),
                usuario.get("email"),
                usuario.get("pais"),
                usuario.get("empresa"),
                usuario.get("certificacion"),
                usuario.get("idioma"),
                usuario.get("accion"),
                usuario.get("motivo_error"),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            )
        )
        con.commit()
        con.close()

    # ── Consultas ─────────────────────────────────────────────────────────────

    def get_ejecuciones(self, limit=50):
        con = self._conn()
        rows = con.execute(
            """SELECT id, fecha, hora, total_aprobados, total_rechazados,
                      total_errores, duracion_segundos
               FROM ejecuciones ORDER BY id DESC LIMIT ?""",
            (limit,)
        ).fetchall()
        con.close()
        return [
            {
                "id": r[0], "fecha": r[1], "hora": r[2],
                "aprobados": r[3], "rechazados": r[4],
                "errores": r[5], "duracion": r[6]
            }
            for r in rows
        ]

    def get_usuarios(self, ejec_id: int = None, accion: str = None, limit=200):
        con = self._conn()
        query = "SELECT nombre, email, pais, empresa, certificacion, idioma, accion, motivo_error, fecha FROM usuarios WHERE 1=1"
        params = []
        if ejec_id:
            query += " AND ejecucion_id=?"
            params.append(ejec_id)
        if accion:
            query += " AND accion=?"
            params.append(accion)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        rows = con.execute(query, params).fetchall()
        con.close()
        return [
            {
                "nombre": r[0], "email": r[1], "pais": r[2],
                "empresa": r[3], "certificacion": r[4], "idioma": r[5],
                "accion": r[6], "motivo_error": r[7], "fecha": r[8]
            }
            for r in rows
        ]

    def get_totales(self):
        con = self._conn()
        c = con.cursor()
        total_ejec = c.execute("SELECT COUNT(*) FROM ejecuciones").fetchone()[0]
        total_apr  = c.execute("SELECT COALESCE(SUM(total_aprobados),0) FROM ejecuciones").fetchone()[0]
        total_rec  = c.execute("SELECT COALESCE(SUM(total_rechazados),0) FROM ejecuciones").fetchone()[0]
        ultima     = c.execute("SELECT fecha||' '||hora FROM ejecuciones ORDER BY id DESC LIMIT 1").fetchone()
        con.close()
        return {
            "ejecuciones": total_ejec,
            "aprobados":   total_apr,
            "rechazados":  total_rec,
            "ultima":      ultima[0] if ultima else "—"
        }