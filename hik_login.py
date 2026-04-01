"""
=============================================================================
HIK_LOGIN — Módulo de login para HikBot v2.0
=============================================================================

Flujo:
  1. Navegar a URL login
  2. Ingresar email + password
  3. Click "Send Verification Code"
  4. hik_gmail.py espera y extrae el código automáticamente
  5. Ingresar código en el campo
  6. Click "Sign in"
  7. Verificar redirección exitosa

Requiere en .env:
  ADMIN_USER   → email
  ADMIN_PASS   → password de Hikvision

=============================================================================
"""

import time
import logging
import os
from dotenv import load_dotenv
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from hik_gmail import HikGmail

load_dotenv()

log = logging.getLogger("HikBot")


class HikLogin:
    """
    Ejecuta el login completo de Hikvision eLearning.

    Parámetros
    ----------
    driver  : WebDriver de Selenium ya iniciado
    timeout : segundos de espera para elementos (default 15)
    """

    def __init__(self, driver, timeout: int = 15):
        self.driver   = driver
        self.wait     = WebDriverWait(driver, timeout)
        self.url      = "https://elearning-admin.hikvision.com/login"
        self.usuario  = os.getenv("ADMIN_USER", "").strip()
        self.password = os.getenv("ADMIN_PASS", "").strip()
        self._validar_credenciales()

    # =========================================================================
    # PUNTO DE ENTRADA
    # =========================================================================

    def ejecutar(self):
        log.info("→ Iniciando login...")
        self.driver.get(self.url)
        self._esperar_pagina_cargada()

        self._ingresar_email()
        self._ingresar_password()
        self._click_send_verification_code()

        codigo = HikGmail().esperar_codigo()

        self._ingresar_codigo(codigo)
        self._click_sign_in()
        self._verificar_login_exitoso()

        log.info("✓ Login completado")

    # =========================================================================
    # PASOS
    # =========================================================================

    def _esperar_pagina_cargada(self):
        try:
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='password']"))
            )
            time.sleep(0.5)
            log.info("  Página de login cargada")
        except TimeoutException:
            raise Exception("La página de login no cargó — verifica la URL y tu conexión")

    def _ingresar_email(self):
        campo = self._buscar_campo(
            [
                "input[name='loginName']",
                "input[name='account']",
                "input[name='email']",
                "input[name='username']",
                "input[type='email']",
                "input[type='text']",
            ],
            "email"
        )
        campo.clear()
        campo.send_keys(self.usuario)
        log.info("  Email ingresado")
        time.sleep(0.3)

    def _ingresar_password(self):
        campo = self._buscar_campo(
            ["input[type='password']"],
            "password"
        )
        campo.clear()
        campo.send_keys(self.password)
        log.info("  Password ingresado")
        time.sleep(0.3)

    def _click_send_verification_code(self):
        try:
            btn = self.wait.until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//button[normalize-space()='Send Verification Code']")
                )
            )
            btn.click()
            log.info("  'Send Verification Code' clickeado — esperando email...")
            time.sleep(1)
        except TimeoutException:
            raise Exception(
                "No se encontró el botón 'Send Verification Code'. "
                "Abre DevTools (F12), inspecciona el botón y verifica su texto exacto."
            )

    def _ingresar_codigo(self, codigo: str):
        campo = None

        for selector in [
            "input[placeholder*='Verification' i]",
            "input[placeholder*='code' i]",
            "input[placeholder*='código' i]",
            ".verification-code input",
        ]:
            try:
                el = self.driver.find_element(By.CSS_SELECTOR, selector)
                if el.is_displayed():
                    campo = el
                    break
            except NoSuchElementException:
                continue

        if not campo:
            inputs = [
                el for el in self.driver.find_elements(By.CSS_SELECTOR, "input")
                if el.is_displayed() and el.get_attribute("type") not in ["hidden", "submit", "button"]
            ]
            log.info(f"  Inputs visibles encontrados: {len(inputs)}")
            for i, inp in enumerate(inputs):
                log.info(f"    [{i}] type={inp.get_attribute('type')} placeholder={inp.get_attribute('placeholder')} name={inp.get_attribute('name')}")
            if len(inputs) >= 3:
                campo = inputs[2]

        if not campo:
            raise Exception("No se encontró el campo de código de verificación")

        campo.clear()
        campo.send_keys(codigo)
        log.info(f"  Código {codigo} ingresado")
        time.sleep(0.5)

    def _click_sign_in(self):
        try:
            btn = self.wait.until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//button[normalize-space()='Sign in']")
                )
            )
            btn.click()
            log.info("  'Sign in' clickeado")
        except TimeoutException:
            raise Exception(
                "El botón 'Sign in' no se habilitó tras ingresar el código. "
                "Posible causa: código incorrecto o expirado."
            )

    def _verificar_login_exitoso(self):
        url_login = self.url.rstrip("/")
        try:
            WebDriverWait(self.driver, 20).until(
                lambda d: url_login not in d.current_url
            )
            log.info(f"  Sesión iniciada — {self.driver.current_url}")
        except TimeoutException:
            error_msg = self._leer_error_pantalla()
            raise Exception(
                "Login falló — la página no redirigió tras Sign in. "
                + (f"Mensaje: '{error_msg}'" if error_msg
                   else "Verifica usuario, contraseña y código.")
            )

    # =========================================================================
    # UTILIDADES
    # =========================================================================

    def _buscar_campo(self, selectores: list, nombre: str):
        for selector in selectores:
            try:
                el = self.driver.find_element(By.CSS_SELECTOR, selector)
                if el.is_displayed():
                    return el
            except NoSuchElementException:
                continue
        raise Exception(
            f"No se encontró el campo '{nombre}'. "
            f"Abre DevTools (F12), inspecciona el campo y agrega su selector "
            f"al inicio de la lista en hik_login.py"
        )

    def _leer_error_pantalla(self) -> str:
        for selector in [".el-form-item__error", ".error-msg", ".alert-danger",
                         "[class*='error']", "[class*='Error']"]:
            try:
                el = self.driver.find_element(By.CSS_SELECTOR, selector)
                if el.is_displayed() and el.text.strip():
                    return el.text.strip()
            except NoSuchElementException:
                continue
        return ""

    def _validar_credenciales(self):
        errores = []
        if not self.usuario:
            errores.append("ADMIN_USER no está definido en .env")
        if not self.password:
            errores.append("ADMIN_PASS no está definido en .env")
        if errores:
            raise Exception(
                "HikLogin — errores de configuración:\n"
                + "\n".join(f"  · {e}" for e in errores)
            )