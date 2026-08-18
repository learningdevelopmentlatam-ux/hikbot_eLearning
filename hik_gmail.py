"""
=============================================================================
HIK_GMAIL — Lector de código de verificación vía IMAP
=============================================================================

Responsabilidad única:
  Conectarse a Gmail por IMAP, esperar el email de Hikvision
  y retornar el código de 6 dígitos.

Remitente esperado : no-reply-eLearning@hikvision.com
Patrón del cuerpo  : "Your verification code is 512019."

Requiere en .env:
  ADMIN_USER      → email Gmail (mismo que hace login en Hikvision)
  GMAIL_APP_PASS  → App Password de 16 caracteres (sin espacios)

=============================================================================
"""
import imaplib
import email
import re
import time
import logging
import os
from email.header import decode_header
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger("HikBot")

# ── Constantes ────────────────────────────────────────────────────────────────

IMAP_SERVER      = "imap.gmail.com"
IMAP_PORT        = 993
REMITENTE        = "no-reply-eLearning@hikvision.com"
PATRON_CODIGO    = re.compile(r'Your verification code is (\d{6})')
TIMEOUT_GMAIL    = 120   # segundos máximo esperando el email
INTERVALO_POLL   = 5     # segundos entre cada intento


class HikGmail:
    """
    Conecta a Gmail por IMAP y extrae el código de verificación
    del email más reciente de Hikvision.

    Uso:
        gmail = HikGmail()
        codigo = gmail.esperar_codigo()  # retorna "512019" o lanza Exception
    """

    def __init__(self):
        self.usuario  = os.getenv("ADMIN_USER", "").strip()
        self.app_pass = os.getenv("GMAIL_APP_PASS", "").replace(" ", "").strip()
        self._validar_credenciales()

    # =========================================================================
    # PUNTO DE ENTRADA
    # =========================================================================

    def esperar_codigo(self) -> str:
        """
        Espera hasta TIMEOUT_GMAIL segundos a que llegue el email
        con el código de verificación.

        Retorna el código como string (ej: "512019").
        Lanza Exception si se agota el tiempo o hay error de conexión.
        """
        log.info(f"  Gmail: esperando email de {REMITENTE} (máx {TIMEOUT_GMAIL}s)...")

        # Registrar momento exacto antes de pedir el código
        # para no confundir con emails viejos
        timestamp_inicio = time.time()

        elapsed = 0
        while elapsed < TIMEOUT_GMAIL:
            try:
                codigo = self._buscar_codigo(timestamp_inicio)
                if codigo:
                    log.info(f"  Gmail: código encontrado ✓")
                    return codigo
            except Exception as e:
                log.warning(f"  Gmail: error en intento ({e}), reintentando...")

            time.sleep(INTERVALO_POLL)
            elapsed += INTERVALO_POLL
            log.info(f"  Gmail: esperando... ({elapsed}s / {TIMEOUT_GMAIL}s)")

        raise Exception(
            f"Gmail: tiempo agotado ({TIMEOUT_GMAIL}s) esperando email de Hikvision. "
            f"Verifica que el email llegó a {self.usuario} y que el remitente "
            f"es exactamente '{REMITENTE}'."
        )

    # =========================================================================
    # LÓGICA INTERNA
    # =========================================================================

    def _buscar_codigo(self, timestamp_inicio: float) -> str | None:
        mail = self._conectar()
        try:
            mail.select("INBOX")

            _, ids = mail.search(None, f'(FROM "{REMITENTE}")')
            log.info(f"  Gmail: IDs encontrados → {ids}")

            if not ids or not ids[0]:
                log.info("  Gmail: ningún email del remitente")
                return None

            id_list = ids[0].split()
            log.info(f"  Gmail: total emails del remitente → {len(id_list)}")

            for uid in reversed(id_list):
                _, data = mail.fetch(uid, "(RFC822)")
                msg = email.message_from_bytes(data[0][1])

                fecha_email = self._timestamp_email(msg)
                log.info(f"  Gmail: email {uid} → fecha {fecha_email} / inicio {timestamp_inicio - 60}")

                if fecha_email and fecha_email < timestamp_inicio - 60:
                    log.info(f"  Gmail: email {uid} muy antiguo, saltando")
                    continue

                codigo = self._extraer_codigo(msg)
                if codigo:
                    mail.store(uid, "+FLAGS", "\\Seen")
                    return codigo

            return None

        finally:
            try:
                mail.logout()
            except Exception:
                pass

    def _conectar(self) -> imaplib.IMAP4_SSL:
        """Abre y retorna conexión IMAP autenticada."""
        try:
            mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT, timeout=30)
            mail.login(self.usuario, self.app_pass)
            return mail
        except imaplib.IMAP4.error as e:
            raise Exception(
                f"Gmail: error de autenticación IMAP. "
                f"Verifica ADMIN_USER y GMAIL_APP_PASS en el .env. "
                f"Detalle: {e}"
            )

    def _extraer_codigo(self, msg) -> str | None:
        """
        Extrae el código de 6 dígitos del cuerpo del email.
        Maneja emails plain text y multipart.
        """
        cuerpo = self._obtener_cuerpo(msg)
        if not cuerpo:
            return None

        match = PATRON_CODIGO.search(cuerpo)
        return match.group(1) if match else None

    def _obtener_cuerpo(self, msg) -> str:
        texto = ""
        if msg.is_multipart():
            for parte in msg.walk():
                tipo = parte.get_content_type()
                if tipo == "text/plain":
                    payload = parte.get_payload(decode=True)
                    if payload:
                        texto += payload.decode(
                            parte.get_content_charset() or "utf-8", errors="replace"
                        )
                elif tipo == "text/html" and not texto:
                    # Fallback a HTML si no hay texto plano
                    payload = parte.get_payload(decode=True)
                    if payload:
                        html = payload.decode(
                            parte.get_content_charset() or "utf-8", errors="replace"
                        )
                        # Quitar tags HTML para buscar el código
                        import re
                        texto = re.sub(r'<[^>]+>', ' ', html)
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                texto = payload.decode(
                    msg.get_content_charset() or "utf-8", errors="replace"
                )
        
        log.info(f"  Gmail: cuerpo extraído → {len(texto)} caracteres")
        return texto

    def _timestamp_email(self, msg) -> float | None:
        """Retorna el timestamp Unix de la fecha del email, o None si no puede parsear."""
        from email.utils import parsedate_to_datetime
        try:
            fecha_str = msg.get("Date", "")
            if fecha_str:
                return parsedate_to_datetime(fecha_str).timestamp()
        except Exception:
            pass
        return None

    # =========================================================================
    # VALIDACIÓN
    # =========================================================================

    def _validar_credenciales(self):
        errores = []
        if not self.usuario:
            errores.append("ADMIN_USER no está definido en .env")
        if not self.app_pass:
            errores.append("GMAIL_APP_PASS no está definido en .env")
        elif len(self.app_pass) != 16:
            errores.append(
                f"GMAIL_APP_PASS tiene {len(self.app_pass)} caracteres — "
                f"debe tener exactamente 16 (sin espacios)"
            )
        if errores:
            raise Exception("HikGmail — errores de configuración:\n" + "\n".join(f"  · {e}" for e in errores))
