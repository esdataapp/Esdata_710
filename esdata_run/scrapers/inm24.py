"""
Scraper principal para Inmuebles24.

Navega a través de las páginas de resultados haciendo clic en el botón "Siguiente"
para imitar el comportamiento humano y evitar bloqueos. Extrae la información
básica de cada anuncio y guarda las URLs para el scraper de detalle.
"""
import sys
import logging
import time
import pandas as pd
from pathlib import Path
from bs4 import BeautifulSoup
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Añadir el directorio raíz del proyecto al sys.path
# para permitir importaciones absolutas desde cualquier lugar.
# Añadir el directorio raíz del proyecto al sys.path
# para permitir importaciones absolutas desde cualquier lugar.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from esdata_run.core.context import ScraperContext
from esdata_run.utils.browser import get_browser

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def extract_page_data(page_source: str) -> pd.DataFrame:
    """
    Parsea el HTML de una página de resultados y extrae los datos de los anuncios.
    """
    soup = BeautifulSoup(page_source, 'html.parser')
    cards = soup.find_all("div", class_="postingCardLayout-module__posting-card-layout")
    data = []

    if not cards:
        logger.warning("No se encontraron 'posting cards' en la página.")
        return pd.DataFrame()

    for card in cards:
        temp_dict = {}
        
        link_tag = card.select_one("h3[data-qa='POSTING_CARD_DESCRIPTION'] a")
        if not link_tag or not link_tag.has_attr('href'):
            continue

        temp_dict['url'] = "https://www.inmuebles24.com" + link_tag['href']
        temp_dict['nombre'] = link_tag.get_text(strip=True)
        
        price_tag = card.select_one("div[data-qa='POSTING_CARD_PRICE']")
        temp_dict['precio'] = price_tag.get_text(strip=True) if price_tag else None

        location_tag = card.select_one("h2[data-qa='POSTING_CARD_LOCATION']")
        temp_dict['ubicacion'] = location_tag.get_text(strip=True) if location_tag else None
        
        data.append(temp_dict)
        
    return pd.DataFrame(data)


def run(context: ScraperContext):
    """
    Punto de entrada principal para el scraper.
    """
    logger.info(f"Iniciando scraper para la URL: {context.url}")
    all_data = []
    
    with get_browser(context.scraper_name, headless=not context.requires_gui) as driver:
        try:
            driver.uc_open_with_reconnect(context.url, 10)
        except Exception as e:
            logger.error(f"No se pudo cargar la URL inicial {context.url}: {e}", exc_info=True)
            return False

        page_count = 1
        while True:
            logger.info(f"Procesando página {page_count}...")
            try:
                # Esperar a que las tarjetas de anuncios estén presentes
                WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.postingCardLayout-module__posting-card-layout"))
                )
                logger.info("Tarjetas de anuncios encontradas. Extrayendo datos...")
                
                # Intentar resolver captcha si es necesario (no fallará si no hay)
                driver.uc_click_captcha(reconnect_time=3)

                page_source = driver.page_source
                df_page = extract_page_data(page_source)

                if not df_page.empty:
                    all_data.append(df_page)
                    logger.info(f"Página {page_count}: Se encontraron {len(df_page)} anuncios.")
                else:
                    logger.warning(f"Página {page_count}: No se extrajeron datos. Terminando bucle.")
                    break

                # Buscar el botón "Siguiente" y hacer clic
                next_button = driver.find_element(By.CSS_SELECTOR, "a[data-qa='PAGING_NEXT']")
                if "disabled" in next_button.get_attribute("class"):
                    logger.info("El botón 'Siguiente' está deshabilitado. Fin de la paginación.")
                    break
                
                logger.info("Haciendo clic en 'Siguiente'...")
                driver.execute_script("arguments[0].click();", next_button)
                page_count += 1
                time.sleep(3) # Pausa prudencial después de hacer clic

            except TimeoutException:
                logger.warning("Tiempo de espera agotado buscando anuncios. Puede ser el final de los resultados o una página de error.")
                break
            except NoSuchElementException:
                logger.info("No se encontró el botón 'Siguiente'. Se asume que es la última página.")
                break
            except Exception as e:
                logger.error(f"Error inesperado en la página {page_count}: {e}", exc_info=True)
                break

    if not all_data:
        logger.error("No se pudo extraer ningún dato de ninguna página.")
        return False

    final_df = pd.concat(all_data, ignore_index=True).drop_duplicates(subset=['url'])
    final_df.to_csv(context.output_path, index=False)
    logger.info(f"Scraping completado. Se guardaron {len(final_df)} URLs únicas en: {context.output_path}")
    
    return True

if __name__ == '__main__':
    # Este bloque permite ejecutar el scraper de forma independiente para pruebas.
    # El adaptador de scrapers (scraper_adapter.py) no usa este bloque.
    try:
        scraper_context = ScraperContext.from_env()
        run(scraper_context)
    except Exception as e:
        logger.critical(f"El scraper falló al ejecutarse de forma independiente: {e}", exc_info=True)
        sys.exit(1)
