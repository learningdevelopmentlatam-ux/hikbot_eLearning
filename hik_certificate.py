"""
=============================================================================
HIK_CERTIFICATE — Bot para sección Certificate
=============================================================================

Flujo:
  1. Navegar a Certificate tab
  2. Por cada usuario:
     - Validación local dice ES persona → APROBAR
     - Validación local dice NO es persona → MANUAL_REVIEW (se registra en BD, se omite)
  3. Marcar APROBAR → Approve → confirmar popups
  4. Repetir hasta tabla vacía
  5. Guardar en DB
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
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
from hik_login import HikLogin
from hik_names import HikNames
from hik_db import HikDB

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("HikBot")

URL_CERTIFICATE = "https://elearning-admin.hikvision.com/todoList/pending?openTab=Certificate"

db    = HikDB()
names = HikNames()


# ── Navegación ────────────────────────────────────────────────────────────────

def ir_a_certificate(driver):
    driver.get(URL_CERTIFICATE)
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr"))
        )
        log.info("  Tabla Certificate cargada")
    except TimeoutException:
        log.warning("  Tabla no apareció en 15s")
    time.sleep(2)


# ── Índices de columnas ───────────────────────────────────────────────────────

def encontrar_indices(driver):
    encabezados = driver.find_elements(By.CSS_SELECTOR, "table thead th")
    idx_name    = None
    idx_company = None
    idx_cert    = None

    for i, th in enumerate(encabezados):
        texto = th.text.strip().lower()
        if texto == "name":
            idx_name = i
        if texto == "company":
            idx_company = i
        if texto == "certification":
            idx_cert = i

    log.info(f"  Columnas → Name: {idx_name} | Company: {idx_company} | Certification: {idx_cert}")
    return idx_name, idx_company, idx_cert


# ── Clasificar filas ──────────────────────────────────────────────────────────

def clasificar_filas(driver, idx_name, idx_company, idx_cert):
    filas    = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
    aprobar  = []
    manual   = []
    pendientes_gemini = []

    for i, fila in enumerate(filas):
        try:
            celdas = fila.find_elements(By.TAG_NAME, "td")
            if len(celdas) <= max(idx_name, idx_company, idx_cert):
                continue

            nombre  = celdas[idx_name].text.strip()
            email   = celdas[2].text.strip() if len(celdas) > 2 else ""
            pais    = celdas[3].text.strip() if len(celdas) > 3 else ""
            empresa = celdas[idx_company].text.strip()
            cert    = celdas[idx_cert].text.strip()

            if not nombre:
                continue

            usuario = {
                "nombre":        nombre,
                "email":         email,
                "pais":          pais,
                "empresa":       empresa,
                "certificacion": cert,
                "idioma":        "",
                "fila":          fila,
            }

            if names.es_persona(nombre, empresa):
                pendientes_gemini.append(usuario)
            else:
                manual.append(usuario)
                log.warning(f"  [Names] '{nombre}' — omitido para revisión manual")

        except Exception as e:
            log.warning(f"  Error leyendo fila {i}: {e}")

    if pendientes_gemini:
        nombres_a_validar = [u["nombre"] for u in pendientes_gemini]
        log.info(f"  Enviando {len(nombres_a_validar)} nombres a Gemini en lote...")
        resultados = names.validar_lote(nombres_a_validar)

        for u in pendientes_gemini:
            if resultados.get(u["nombre"], False):
                aprobar.append(u)
            else:
                manual.append(u)
                log.warning(f"  [Names] '{u['nombre']}' — Gemini dice no persona, revisión manual")

    log.info(f"  Clasificados → APROBAR: {len(aprobar)} | MANUAL_REVIEW: {len(manual)}")
    return aprobar, manual


# ── Marcar checkboxes ─────────────────────────────────────────────────────────

def marcar_checkboxes(driver, usuarios):
    marcados = []
    filas_actuales = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")

    for fila in filas_actuales:
        try:
            celdas = fila.find_elements(By.TAG_NAME, "td")
            if len(celdas) < 2:
                continue
            nombre_fila = celdas[1].text.strip()

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

def click_approve(driver, marcados_ref, idx_cert):
    try:
        # Cerrar cualquier popup abierto antes de intentar Approve
        try:
            popup = driver.find_element(By.CSS_SELECTOR, ".el-message-box__wrapper")
            if popup.is_displayed():
                confirm = driver.find_element(
                    By.XPATH,
                    "//div[contains(@class,'el-message-box__wrapper')]//button[normalize-space()='Confirm']"
                )
                driver.execute_script("arguments[0].click();", confirm)
                log.info("  Popup previo cerrado antes de Approve")
                time.sleep(1)
        except Exception:
            pass

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
                log.info(f"  Tabla vacía tras {transcurrido}s — Approve completado")
                tabla_actualizada = True
                break

        aprobados_ref = {(u["nombre"], u["certificacion"]) for u in marcados_ref}
        tiempo_limite = 120
        intervalo = 10
        transcurrido = 0
        tabla_actualizada = False

        log.info("  Esperando que el servidor procese el Approve...")

        while transcurrido < tiempo_limite:
            time.sleep(intervalo)
            transcurrido += intervalo
            driver.refresh()
            try:
                WebDriverWait(driver, 15).until(
                    lambda d: d.find_elements(By.CSS_SELECTOR, "table tbody tr") or
                            d.find_elements(By.CSS_SELECTOR, "table tbody")
                )
                time.sleep(3)
            except TimeoutException:
                # Verificar si la tabla existe pero está vacía
                try:
                    tbody = driver.find_element(By.CSS_SELECTOR, "table tbody")
                    filas = tbody.find_elements(By.TAG_NAME, "tr")
                    if len(filas) == 0:
                        log.info(f"  Tabla vacía tras {transcurrido}s — Approve completado")
                        tabla_actualizada = True
                        break
                except Exception:
                    pass
                log.warning(f"  Tabla no cargó en intento {transcurrido}s")
                continue

            filas = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
            nombres_en_tabla = set()
            for fila in filas:
                celdas = fila.find_elements(By.TAG_NAME, "td")
                if len(celdas) > idx_cert:
                    nombres_en_tabla.add((celdas[1].text.strip(), celdas[idx_cert].text.strip()))

            pendientes = aprobados_ref & nombres_en_tabla
            log.info(f"  Tiempo: {transcurrido}s | Aprobados aún en tabla: {len(pendientes)}")

            if not pendientes:
                log.info(f"  Tabla actualizada tras {transcurrido}s")
                tabla_actualizada = True
                break

        if not tabla_actualizada:
            log.warning("  Página no actualizó en 2 minutos — registrando aprobados y deteniendo")
            return "TIMEOUT"

        log.info("  Tabla recargada tras Approve")
        return True

    except Exception as e:
        log.error(f"  Error en Approve: {e}")
        return True
    
# ── Ciclo principal ───────────────────────────────────────────────────────────

def procesar(driver, ejec_id):
    idx_name, idx_company, idx_cert = encontrar_indices(driver)
    total_aprobados = 0
    total_manual    = 0
    total_errores   = 0

    ya_registrados_manual = set()

    while True:
        time.sleep(5)
        aprobar, manual = clasificar_filas(driver, idx_name, idx_company, idx_cert)

        if not aprobar:
            log.info("  Sin pendientes para aprobar — fin del proceso")
            break

        if aprobar:
            log.info(f"\n  --- APROBANDO {len(aprobar)} ---")
            for u in aprobar:
                log.info(f"  → {u['nombre']} | {u['empresa']} | {u['certificacion']}")

            marcados = marcar_checkboxes(driver, aprobar)
            if marcados:
                ok = click_approve(driver, marcados, idx_cert)
                for u in marcados:
                    if ok == "TIMEOUT" or ok:
                        db.registrar_usuario(ejec_id, {**u, "accion": "APPROVED"})
                        total_aprobados += 1
                    else:
                        db.registrar_usuario(ejec_id, {
                            **u,
                            "accion": "ERROR",
                            "motivo_error": "Falló Approve antes de confirmar"
                        })
                        total_errores += 1
                if ok == "TIMEOUT":
                    log.warning("  Deteniendo ejecución por timeout de página")
                    break

        for u in manual:
            clave = (u["nombre"], u["certificacion"])
            if clave not in ya_registrados_manual:
                db.registrar_usuario(ejec_id, {**u, "accion": "MANUAL_REVIEW"})
                ya_registrados_manual.add(clave)
                total_manual += 1

    return total_aprobados, total_manual, total_errores


# ── Main (solo si se ejecuta standalone) ──────────────────────────────────────

if __name__ == "__main__":
    opts = webdriver.ChromeOptions()
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--incognito")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), options=opts
    )

    inicio  = datetime.now()
    ejec_id = db.iniciar_ejecucion()
    log.info(f"Ejecución ID: {ejec_id}")

    try:
        HikLogin(driver).ejecutar()
        time.sleep(3)
        ir_a_certificate(driver)
        time.sleep(2)

        aprobados, manual, errores = procesar(driver, ejec_id)

        duracion = int((datetime.now() - inicio).total_seconds())
        db.cerrar_ejecucion(ejec_id, aprobados, 0, errores, duracion)

        log.info(f"\n{'='*50}")
        log.info(f"  Aprobados     : {aprobados}")
        log.info(f"  Manual Review : {manual}")
        log.info(f"  Errores       : {errores}")
        log.info(f"  Duración      : {duracion}s")
        log.info(f"{'='*50}")

    finally:
        driver.quit()
