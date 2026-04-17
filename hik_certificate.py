"""
=============================================================================
HIK_CERTIFICATE — Bot para sección Certificate
=============================================================================

Flujo:
  1. Navegar a Certificate tab
  2. Por cada usuario:
     - Groq dice ES persona → APROBAR
     - Groq dice NO es persona → MANUAL_REVIEW (se registra en BD, se omite)
  3. Marcar APROBAR → Approve → confirmar popups
  4. Repetir hasta tabla vacía
  5. Guardar en DB

Nota: misma lógica que el original. Solo se protegió el bloque main con
`if __name__ == "__main__":` para permitir importarlo desde hik_main.py.
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

            es_persona = names.es_persona(nombre, empresa)

            if es_persona:
                aprobar.append(usuario)
            else:
                manual.append(usuario)
                log.warning(f"  [Names] '{nombre}' no es persona — omitido para revisión manual")

        except Exception as e:
            log.warning(f"  Error leyendo fila {i}: {e}")

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

def click_approve(driver, marcados_ref):
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

        time.sleep(8)
        max_intentos = 4
        for intento in range(max_intentos):
            driver.get(URL_CERTIFICATE)
            time.sleep(8)
            try:
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "table"))
                )
            except TimeoutException:
                break

            filas = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
            nombres_actuales = set()
            for fila in filas:
                celdas = fila.find_elements(By.TAG_NAME, "td")
                if len(celdas) > 1:
                    nombres_actuales.add(celdas[1].text.strip())

            nombres_aprobados = {u["nombre"] for u in marcados_ref}
            pendientes = nombres_actuales & nombres_aprobados

            if not pendientes:
                log.info(f"  Tabla limpia tras {intento+1} intento(s)")
                break
            else:
                log.warning(f"  Intento {intento+1}: siguen {len(pendientes)} usuarios aprobados en tabla, reintentando...")

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

    while True:
        names._cache = {}
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
               ok = click_approve(driver, marcados)
               for u in marcados:
                    if ok:
                        db.registrar_usuario(ejec_id, {**u, "accion": "APPROVED"})
                        total_aprobados += 1
                    else:
                        db.registrar_usuario(ejec_id, {
                            **u,
                            "accion": "ERROR",
                            "motivo_error": "Falló Approve antes de confirmar"
                        })
                        total_errores += 1

        total_manual += len(manual)

    return total_aprobados, total_manual, total_errores


# ── Main (solo si se ejecuta standalone) ──────────────────────────────────────

if __name__ == "__main__":
    opts = webdriver.ChromeOptions()
    opts.add_argument("--window-size=1920,1080")

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
