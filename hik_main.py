"""
=============================================================================
HIK_MAIN — Orquestador de HikBot
=============================================================================

Coordina ambos bots (Self-paced Training + Certificate) en un único flujo:

  1. Crea un único driver de Chrome
  2. Hace un único login compartido
  3. Abre UNA sola ejecución en BD (compartida por ambos bots)
  4. Ejecuta hik_selfpaced.procesar()
  5. Ejecuta hik_certificate.procesar()
  6. Cierra la ejecución con los totales SUMADOS de ambos bots
  7. Cierra el driver

=============================================================================
"""

import time
import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

from hik_login import HikLogin
from hik_db import HikDB

import hik_selfpaced   as bot_selfpaced
import hik_certificate as bot_certificate

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("HikMain")


# ── Helpers ───────────────────────────────────────────────────────────────────

def correr_bot(nombre, ir_a_seccion, procesar, driver, ejec_id):
    """
    Ejecuta un bot usando el ejec_id compartido (no crea ni cierra ejecución).
    Retorna (aprobados, rechazados_o_manual, errores, duracion).
    """
    log.info(f"\n{'#'*60}")
    log.info(f"#  Iniciando bot: {nombre}")
    log.info(f"{'#'*60}")

    inicio = datetime.now()

    try:
        ir_a_seccion(driver)
        time.sleep(2)
        aprobados, segundo_total, errores = procesar(driver, ejec_id)
    except Exception as e:
        log.error(f"  Error fatal en bot {nombre}: {e}")
        aprobados, segundo_total, errores = 0, 0, 1

    duracion = int((datetime.now() - inicio).total_seconds())

    log.info(f"\n{'-'*50}")
    log.info(f"  [{nombre}] Aprobados : {aprobados}")
    if nombre == "Self-paced Training":
        log.info(f"  [{nombre}] Rechazados: {segundo_total}")
    else:
        log.info(f"  [{nombre}] Manual    : {segundo_total}")
    log.info(f"  [{nombre}] Errores   : {errores}")
    log.info(f"  [{nombre}] Duración  : {duracion}s")
    log.info(f"{'-'*50}")

    return aprobados, segundo_total, errores, duracion


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    opts = webdriver.ChromeOptions()
    opts.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=opts
    )

    db = HikDB()
    inicio_total = datetime.now()

    # UNA sola ejecución compartida por los dos bots
    ejec_id = db.iniciar_ejecucion()
    log.info(f"Ejecución ID (compartida): {ejec_id}")

    try:
        # 1) LOGIN ÚNICO ──────────────────────────────────────────────────────
        log.info("\n>>> Login único compartido <<<")
        HikLogin(driver).ejecutar()
        time.sleep(3)
        log.info("  Login completado\n")

        # 2) BOT SELF-PACED TRAINING ──────────────────────────────────────────
        sp_apr, sp_rej, sp_err, sp_dur = correr_bot(
            nombre       = "Self-paced Training",
            ir_a_seccion = bot_selfpaced.ir_a_self_paced,
            procesar     = bot_selfpaced.procesar,
            driver       = driver,
            ejec_id      = ejec_id,
        )

        # 3) BOT CERTIFICATE ──────────────────────────────────────────────────
        ce_apr, ce_man, ce_err, ce_dur = correr_bot(
            nombre       = "Certificate",
            ir_a_seccion = bot_certificate.ir_a_certificate,
            procesar     = bot_certificate.procesar,
            driver       = driver,
            ejec_id      = ejec_id,
        )

        # 4) CERRAR ÚNICA EJECUCIÓN CON TOTALES SUMADOS ───────────────────────
        duracion_total   = int((datetime.now() - inicio_total).total_seconds())
        total_aprobados  = sp_apr + ce_apr
        total_rechazados = sp_rej            # Certificate no tiene rechazados
        total_errores    = sp_err + ce_err

        db.cerrar_ejecucion(
            ejec_id,
            total_aprobados,
            total_rechazados,
            total_errores,
            duracion_total,
        )

        # 5) RESUMEN GLOBAL ───────────────────────────────────────────────────
        log.info(f"\n{'='*60}")
        log.info(f"  RESUMEN GLOBAL (ejecución {ejec_id})")
        log.info(f"{'='*60}")
        log.info(f"  Self-paced  → Aprobados: {sp_apr} | Rechazados: {sp_rej} | Errores: {sp_err}")
        log.info(f"  Certificate → Aprobados: {ce_apr} | Manual: {ce_man} | Errores: {ce_err}")
        log.info(f"  TOTAL       → Aprobados: {total_aprobados} | Rechazados: {total_rechazados} | Errores: {total_errores}")
        log.info(f"  Duración total: {duracion_total}s")
        log.info(f"{'='*60}")

        input("\nBots terminados — revisa navegador y DB. Enter para cerrar...")

    finally:
        driver.quit()
        log.info("Driver cerrado. Fin.")


if __name__ == "__main__":
    main()

