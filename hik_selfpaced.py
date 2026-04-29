"""
=============================================================================
HIK_SELFPACED — Bot para sección Self-paced Training
=============================================================================
Misma lógica que hik_self-pacedTraining.py original. Solo se renombró el
archivo (sin guión, para poder importarlo) y se protegió el bloque main
con `if __name__ == "__main__":` para permitir su uso como módulo desde
hik_main.py sin que se ejecute automáticamente.
=============================================================================
"""

import time
import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from hik_login import HikLogin
from hik_db import HikDB

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("HikBot")

URL_PENDING = "https://elearning-admin.hikvision.com/todoList/pending?openTab=SelfPacedTraining"
# MENSAJE_REJECT = (
#     "Esta certificación no esta disponible en tu pais, revisa el calendario "
#     "para asistir a las certificaciones disponibles en tu zona "
#     "https://www.hikvision.com/es-la/support/tools/capacitaciones-y-certificaciones-hikvision/"
# )

MENSAJE_MAINTENANCE = (
    "Queremos informarle que esta certificación está dirigida exclusivamente a centros de RMA autorizados de Hikvision. "
    "Si desea más información comuníquese con lina.daza@hikvision.com"
)

MENSAJE_HCSP = (
    "Esta Certificación se debe tomar de manera presencial con un instructor certificado y con equipos específicos. "
    "Consulta en tu región las próximas fechas y certifícate con nosotros. "
    "https://www.hikvision.com/es-la/support/tools/capacitaciones-y-certificaciones-hikvision/"
)
db = HikDB()


# ── Navegación ────────────────────────────────────────────────────────────────

def ir_a_self_paced(driver):
    driver.get(URL_PENDING)
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr"))
        )
    except TimeoutException:
        log.warning("  Tabla no apareció en 15s")
    time.sleep(2)
    try:
        tab = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable(
                (By.XPATH, "//*[contains(text(),'Self-paced') or contains(text(),'Self-Paced')]")
            )
        )
        tab.click()
        time.sleep(3)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr"))
        )
        log.info("  Tab Self-paced activado")
    except TimeoutException:
        log.info("  Tab ya activo")

# ── Índices de columnas ───────────────────────────────────────────────────────

def encontrar_indices(driver):
    try:
        contenedor = driver.find_element(By.CSS_SELECTOR, ".el-table__header-wrapper")
        driver.execute_script("arguments[0].scrollLeft = 9999", contenedor)
        time.sleep(1.5)
    except Exception:
        try:
            driver.execute_script("document.querySelector('.el-table__body-wrapper').scrollLeft = 9999")
            time.sleep(1.5)
        except Exception:
            pass

    encabezados = driver.find_elements(By.CSS_SELECTOR, "table thead th")
    log.info(f"  Total encabezados: {len(encabezados)}")
    for i, th in enumerate(encabezados):
        log.info(f"  [{i}]: '{th.text.strip()}'")

    idx_lang = None
    idx_cert = None
    for i, th in enumerate(encabezados):
        texto = th.text.strip().lower()
        if texto == "language":
            idx_lang = i
        if texto == "certification":
            idx_cert = i
    log.info(f"  Columnas → Language: {idx_lang} | Certification: {idx_cert}")
    return idx_lang, idx_cert

def clasificar_filas(driver, idx_lang, idx_cert):
    filas   = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
    aprobar  = []
    rechazar = []
    manual   = []

    for i, fila in enumerate(filas):
        try:
            celdas = fila.find_elements(By.TAG_NAME, "td")
            if len(celdas) <= max(idx_lang, idx_cert):
                continue

            nombre  = celdas[1].text.strip()
            email   = celdas[2].text.strip()
            pais    = celdas[3].text.strip()
            empresa = celdas[5].text.strip()
            idioma  = celdas[idx_lang].text.strip()
            cert    = celdas[idx_cert].text.strip()

            if not nombre and not idioma:
                continue

            es_thermal     = "HCSA-Thermal" in cert
            es_display     = "HCSA-Display" in cert
            es_maintenance = "HCSA-Maintenance" in cert or "HCSA Maintenance" in cert
            es_hcsp        = "HCSP" in cert

            usuario = {
                "nombre":        nombre,
                "email":         email,
                "pais":          pais,
                "empresa":       empresa,
                "certificacion": cert,
                "idioma":        idioma,
                "fila":          fila,
            }

            if es_thermal or es_display:
                aprobar.append(usuario)
            elif es_maintenance:
                rechazar.append({**usuario, "mensaje_reject": MENSAJE_MAINTENANCE})
            elif es_hcsp:
                rechazar.append({**usuario, "mensaje_reject": MENSAJE_HCSP})
            else:
                manual.append(usuario)

        except Exception as e:
            log.warning(f"  Error leyendo fila {i}: {e}")

    log.info(f"  Clasificados → APROBAR: {len(aprobar)} | RECHAZAR: {len(rechazar)} | MANUAL_REVIEW: {len(manual)}")
    return aprobar, rechazar, manual

# ── Marcar checkboxes ─────────────────────────────────────────────────────────

def marcar_checkboxes(driver, usuarios):
    marcados = []
    # Releer todas las filas frescas del DOM
    filas_actuales = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")

    for fila in filas_actuales:
        try:
            celdas = fila.find_elements(By.TAG_NAME, "td")
            if len(celdas) < 2:
                continue
            nombre_fila = celdas[1].text.strip()

            # Buscar si esta fila está en la lista de usuarios a marcar
            usuario_match = next(
                (u for u in usuarios if u["nombre"] == nombre_fila), None
            )
            if not usuario_match:
                continue

            checkbox = fila.find_element(By.CSS_SELECTOR, "input[type='checkbox']")
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", checkbox)
            time.sleep(0.2)
            if not checkbox.is_selected():
                driver.execute_script("arguments[0].click();", checkbox)
                time.sleep(0.2)
            marcados.append(usuario_match)
            log.info(f"  ✓ Marcado: {nombre_fila}")
        except Exception as e:
            log.warning(f"  Error marcando fila: {e}")
    return marcados


# ── Approve ───────────────────────────────────────────────────────────────────

def click_approve(driver):
    aprobado = False
    try:
        btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[normalize-space()='Approve']"))
        )
        btn.click()
        log.info("  Click Approve")
        time.sleep(2)

        for _ in range(2):
            try:
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, ".el-message-box__wrapper")
                    )
                )
                confirm = driver.find_element(
                    By.XPATH,
                    "//div[contains(@class,'el-message-box__wrapper')]//button[normalize-space()='Confirm']"
                )
                driver.execute_script("arguments[0].click();", confirm)
                log.info("  Popup confirmado")
                time.sleep(1)
            except TimeoutException:
                break

        aprobado = True

    except Exception as e:
        log.error(f"  Error en Approve antes de confirmar: {e}")
        return False

    try:
        time.sleep(3)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr"))
        )
        log.info("  Tabla recargada tras Approve")
    except Exception as e:
        log.warning(f"  Error esperando tabla (Approve ya confirmado): {e}")

    return aprobado
# ── Reject ────────────────────────────────────────────────────────────────────

def click_reject(driver, mensaje):
    try:
        # Esperar que no haya popups abiertos
        try:
            WebDriverWait(driver, 3).until(
                EC.invisibility_of_element_located(
                    (By.CSS_SELECTOR, ".el-dialog__wrapper")
                )
            )
        except TimeoutException:
            pass

        # Click en botón Reject usando JavaScript para evitar intercepción
        btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[normalize-space()='Reject']"))
        )
        driver.execute_script("arguments[0].click();", btn)
        log.info("  Click Reject")
        time.sleep(2)

        # Seleccionar "Other"
        other = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable(
                (By.XPATH, "//label[contains(.,'Other')] | //span[normalize-space()='Other']/..")
            )
        )
        driver.execute_script("arguments[0].click();", other)
        log.info("  'Other' seleccionado")
        time.sleep(1)

        # Escribir mensaje
        campo = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (By.XPATH, "//textarea[@placeholder='Please input']")
            )
        )
        campo.clear()
        campo.send_keys(mensaje)
        log.info("  Mensaje escrito")
        time.sleep(0.5)

        # Confirm
        confirm = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable(
                (By.XPATH, "//div[contains(@class,'button--line')]//button[normalize-space()='Confirm']")
            )
        )
        driver.execute_script("arguments[0].click();", confirm)
        log.info("  Reject confirmado")

        # Esperar recarga de tabla
        time.sleep(3)
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr"))
            )
        except TimeoutException:
            pass
        log.info("  Tabla recargada tras Reject")
        return True

    except Exception as e:
        log.error(f"  Error en Reject: {e}")
        return False


# ── Ciclo principal ───────────────────────────────────────────────────────────

def procesar(driver, ejec_id):
    idx_lang, idx_cert = encontrar_indices(driver)
    total_aprobados  = 0
    total_rechazados = 0
    total_errores    = 0
    total_manual     = 0
    ya_registrados_manual = set()  # ← FUERA del while

    while True:
        time.sleep(2)
        aprobar, rechazar, manual = clasificar_filas(driver, idx_lang, idx_cert)

        # Registrar manuales nuevos sin duplicar
        for u in manual:
            clave = (u["nombre"], u["certificacion"])
            if clave not in ya_registrados_manual:
                db.registrar_usuario(ejec_id, {**u, "accion": "MANUAL_REVIEW"})
                ya_registrados_manual.add(clave)
                total_manual += 1
                log.info(f"  [MANUAL] {u['nombre']} | {u['certificacion']}")

        # Si no hay nada para aprobar ni rechazar → terminar
        if not aprobar and not rechazar:
            log.info("  Sin pendientes — fin del proceso")
            break

        # RONDA APROBAR
        if aprobar:
            log.info(f"\n  --- APROBANDO {len(aprobar)} ---")
            for u in aprobar:
                log.info(f"  → {u['nombre']} | {u['certificacion']} | {u['idioma'][:40]}")

            marcados = marcar_checkboxes(driver, aprobar)

            if marcados:
                ok = click_approve(driver)
                if ok:
                    for u in marcados:
                        db.registrar_usuario(ejec_id, {**u, "accion": "APPROVED"})
                        total_aprobados += 1
                else:
                    for u in marcados:
                        db.registrar_usuario(ejec_id, {
                            **u,
                            "accion": "ERROR",
                            "motivo_error": "Falló Approve"
                        })
                        total_errores += 1
            continue

        # RONDA RECHAZAR — uno por uno por mensaje distinto
        if rechazar:
            log.info(f"\n  --- RECHAZANDO {len(rechazar)} ---")
            for u in rechazar:
                log.info(f"  ✗ {u['nombre']} | {u['certificacion']}")
                marcados = marcar_checkboxes(driver, [u])
                if marcados:
                    ok = click_reject(driver, u["mensaje_reject"])
                    log.info(f"  click_reject retornó: {ok}")
                    if ok:
                        db.registrar_usuario(ejec_id, {**u, "accion": "REJECTED"})
                        total_rechazados += 1
                    else:
                        db.registrar_usuario(ejec_id, {
                            **u,
                            "accion": "ERROR",
                            "motivo_error": "Falló Reject"
                        })
                        total_errores += 1

    return total_aprobados, total_rechazados, total_errores

# ── Main (solo si se ejecuta standalone) ──────────────────────────────────────

if __name__ == "__main__":
    opts = webdriver.ChromeOptions()
    opts.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), options=opts
    )

    inicio   = datetime.now()
    ejec_id  = db.iniciar_ejecucion()
    log.info(f"Ejecución ID: {ejec_id}")

    try:
        HikLogin(driver).ejecutar()
        time.sleep(3)
        ir_a_self_paced(driver)
        time.sleep(2)

        aprobados, rechazados, errores = procesar(driver, ejec_id)

        duracion = int((datetime.now() - inicio).total_seconds())
        db.cerrar_ejecucion(ejec_id, aprobados, rechazados, errores, duracion)

        log.info(f"\n{'='*50}")
        log.info(f"  Aprobados  : {aprobados}")
        log.info(f"  Rechazados : {rechazados}")
        log.info(f"  Errores    : {errores}")
        log.info(f"  Duración   : {duracion}s")
        log.info(f"{'='*50}")

        input("\nBot terminado — revisa navegador y DB. Enter para cerrar...")

    finally:
        driver.quit()
