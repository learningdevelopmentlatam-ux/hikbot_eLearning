"""
=============================================================================
HIK_CERTIFICATE — Bot para sección Certificate
=============================================================================

Flujo:
  1. Navegar a Certificate tab
  2. Por cada usuario:
     - nombre == empresa → RECHAZAR
     - Groq dice NO es persona → RECHAZAR  
     - Si pasa ambos filtros → APROBAR
  3. Marcar APROBAR → Approve → confirmar popups
  4. Marcar RECHAZAR → Reject → Other + mensaje → Confirm
  5. Repetir hasta tabla vacía
  6. Guardar en DB

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
from hik_names import HikNames
from hik_db import HikDB

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("HikBot")

URL_CERTIFICATE = "https://elearning-admin.hikvision.com/todoList/pending?openTab=Certificate"

MENSAJE_REJECT = (
    "No se emite certificación a nombre de empresa, por favor coloque "
    "su nombre y vuelva a solicitar el certificado"
)

db     = HikDB()
names  = HikNames()


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
    filas  = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
    aprobar  = []
    rechazar = []

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

            # Solo rechazar si nombre == empresa
            # La validación de Groq es opcional — solo como log informativo
            es_persona = names.es_persona(nombre, empresa)

            if nombre.lower() == empresa.lower():
                rechazar.append(usuario)
            else:
                aprobar.append(usuario)
                if not es_persona:
                    log.warning(f"  [Names] Nombre sospechoso pero aprobado: '{nombre}' — revisar manualmente")

        except Exception as e:
            log.warning(f"  Error leyendo fila {i}: {e}")

    log.info(f"  Clasificados → APROBAR: {len(aprobar)} | RECHAZAR: {len(rechazar)}")
    return aprobar, rechazar


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

        time.sleep(3)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr"))
        )
        log.info("  Tabla recargada tras Approve")
        return True

    except Exception as e:
        log.error(f"  Error en Approve: {e}")
        return False


# ── Reject ────────────────────────────────────────────────────────────────────

def click_reject(driver):
    try:
        try:
            WebDriverWait(driver, 3).until(
                EC.invisibility_of_element_located(
                    (By.CSS_SELECTOR, ".el-dialog__wrapper")
                )
            )
        except TimeoutException:
            pass

        btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[normalize-space()='Reject']"))
        )
        driver.execute_script("arguments[0].click();", btn)
        log.info("  Click Reject")
        time.sleep(2)

        other = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable(
                (By.XPATH, "//label[contains(.,'Other')] | //span[normalize-space()='Other']/..")
            )
        )
        driver.execute_script("arguments[0].click();", other)
        log.info("  'Other' seleccionado")
        time.sleep(1)

        campo = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (By.XPATH, "//textarea[@placeholder='Please input']")
            )
        )
        campo.clear()
        campo.send_keys(MENSAJE_REJECT)
        log.info("  Mensaje escrito")
        time.sleep(0.5)

        confirm = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable(
                (By.XPATH, "//button[normalize-space()='Confirm']")
            )
        )
        driver.execute_script("arguments[0].click();", confirm)
        log.info("  Reject confirmado")

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
    idx_name, idx_company, idx_cert = encontrar_indices(driver)
    total_aprobados  = 0
    total_rechazados = 0
    total_errores    = 0

    while True:
        time.sleep(2)
        aprobar, rechazar = clasificar_filas(driver, idx_name, idx_company, idx_cert)

        if not aprobar and not rechazar:
            log.info("  Tabla vacía — fin del proceso")
            break

        if aprobar:
            log.info(f"\n  --- APROBANDO {len(aprobar)} ---")
            for u in aprobar:
                log.info(f"  → {u['nombre']} | {u['empresa']} | {u['certificacion']}")

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

        if rechazar:
            log.info(f"\n  --- RECHAZANDO {len(rechazar)} ---")
            for u in rechazar:
                log.info(f"  ✗ {u['nombre']} | {u['empresa']} | {u['certificacion']}")

            marcados = marcar_checkboxes(driver, rechazar)
            if marcados:
                ok = click_reject(driver)
                if ok:
                    for u in marcados:
                        db.registrar_usuario(ejec_id, {**u, "accion": "REJECTED"})
                        total_rechazados += 1
                else:
                    for u in marcados:
                        db.registrar_usuario(ejec_id, {
                            **u,
                            "accion": "ERROR",
                            "motivo_error": "Falló Reject"
                        })
                        total_errores += 1

    return total_aprobados, total_rechazados, total_errores


# ── Main ──────────────────────────────────────────────────────────────────────

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

    aprobados, rechazados, errores = procesar(driver, ejec_id)

    duracion = int((datetime.now() - inicio).total_seconds())
    db.cerrar_ejecucion(ejec_id, aprobados, rechazados, errores, duracion)

    log.info(f"\n{'='*50}")
    log.info(f"  Aprobados  : {aprobados}")
    log.info(f"  Rechazados : {rechazados}")
    log.info(f"  Errores    : {errores}")
    log.info(f"  Duración   : {duracion}s")
    log.info(f"{'='*50}")

finally:
    driver.quit()