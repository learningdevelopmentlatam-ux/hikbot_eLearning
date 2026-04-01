import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from hik_login import HikLogin

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

opts = webdriver.ChromeOptions()
opts.add_argument("--window-size=1920,1080")

driver = webdriver.Chrome(
    service=Service(ChromeDriverManager().install()), options=opts
)

try:
    HikLogin(driver).ejecutar()
    input("✓ Login OK — revisa el navegador. Enter para cerrar...")
finally:
    driver.quit()