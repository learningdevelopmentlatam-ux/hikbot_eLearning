import time
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
from hik_login import HikLogin

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("HikBot")

URL_CERTIFICATE = "https://elearning-admin.hikvision.com/todoList/pending?openTab=Certificate"

opts = webdriver.ChromeOptions()
opts.add_argument("--window-size=1920,1080")

driver = webdriver.Chrome(
    service=Service(ChromeDriverManager().install()), options=opts
)

try:
    HikLogin(driver).ejecutar()
    time.sleep(3)

    driver.get(URL_CERTIFICATE)
    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr"))
    )
    log.info("  Tabla cargada — esperando 5 segundos antes de refresh")
    time.sleep(5)

    driver.get(URL_CERTIFICATE)
    time.sleep(8)

    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "table"))
    )
    log.info("  Página recargada correctamente")

    input("  Presiona Enter para cerrar el browser...")

finally:
    driver.quit()