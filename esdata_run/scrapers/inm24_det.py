"""
Scraper de detalle para Inmuebles24.

Lee un archivo CSV con URLs de anuncios, visita cada una y extrae la
información detallada, incluyendo características que se revelan al
hacer clic en botones interactivos.
"""
import sys
import logging
import time
import re
import pandas as pd
from pathlib import Path
from bs4 import BeautifulSoup
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ... (existing content) ...
# Añadir el directorio raíz del proyecto al sys.path
# para permitir importaciones absolutas desde cualquier lugar.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from esdata_run.core.context import ScraperContext
from esdata_run.utils.browser import get_browser

# Configuración de logging
# ... (existing content) ...
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def extract_main_details(soup: BeautifulSoup) -> dict:
    """Extrae los detalles principales y visibles de la página."""
    data = {}
    
    # Título principal
    h1 = soup.find("h1", class_="title-property")
    data["titulo"] = h1.get_text(strip=True) if h1 else ""

    # Descripción
    desc_div = soup.find("div", id="longDescription")
    data["descripcion"] = desc_div.get_text(" ", strip=True) if desc_div else ""

    # Precio
    price_span = soup.select_one("div.price-value span")
    data["precio"] = price_span.get_text(strip=True) if price_span else ""

    # Dirección
    address_h4 = soup.select_one("div.section-location-property h4")
    data["direccion"] = address_h4.get_text(strip=True) if address_h4 else ""

    # Características de iconos
    features_ul = soup.find("ul", id="section-icon-features-property")
    if features_ul:
        for li in features_ul.find_all("li", class_="icon-feature"):
            text = re.sub(r'\s+', ' ', li.get_text(" ", strip=True)).strip()
            if "icon-stotal" in str(li):
                data["area_total"] = text
            elif "icon-scubierta" in str(li):
                data["area_cubierta"] = text
            elif "icon-bano" in str(li):
                data["banos"] = text
            elif "icon-cochera" in str(li):
                data["estacionamientos"] = text
            elif "icon-dormitorio" in str(li):
                data["recamaras"] = text
            elif "icon-toilete" in str(li):
                data["medio_banos"] = text
            elif "icon-antiguedad" in str(li):
                data["antiguedad"] = text
            
    return data

def extract_interactive_details(driver) -> dict:
    """Hace clic en los botones de 'General' y extrae la información."""
    interactive_data = {}
    try:
        container = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "reactGeneralFeatures"))
        )
        buttons = container.find_elements(By.TAG_NAME, "button")
        logger.info(f"Encontrados {len(buttons)} botones de características interactivas.")

        for button in buttons:
            try:
                button_text = button.text.strip().lower().replace(" ", "_")
                if not button_text:
                    continue
                
                driver.execute_script("arguments[0].scrollIntoView(true);", button)
                WebDriverWait(driver, 5).until(EC.element_to_be_clickable(button))
                driver.execute_script("arguments[0].click();", button)
                time.sleep(0.5)

                details_container = button.find_element(By.XPATH, "./following-sibling::div")
                features = [elem.text.strip() for elem in details_container.find_elements(By.TAG_NAME, "span") if elem.text.strip()]
                interactive_data[button_text] = "; ".join(features)
            except Exception:
                logger.warning(f"No se pudo extraer información del botón '{button.text}'.", exc_info=True)
    except TimeoutException:
        logger.warning("No se encontró el contenedor de características interactivas.")
    except Exception as e:
        logger.error(f"Error al extraer detalles interactivos: {e}", exc_info=True)
        
    return interactive_data

def run(context: ScraperContext):
    """Punto de entrada principal para el scraper de detalle."""
    if not context.dependency_path or not context.dependency_path.exists():
        logger.error(f"No se encontró el archivo de dependencia necesario: {context.dependency_path}")
        return False

    logger.info(f"Leyendo URLs desde: {context.dependency_path}")
    urls_df = pd.read_csv(context.dependency_path)
    if 'url' not in urls_df.columns:
        logger.error("El archivo de dependencia no contiene la columna 'url'.")
        return False
        
    urls_to_scrape = urls_df["url"].dropna().unique().tolist()
    logger.info(f"Se procesarán {len(urls_to_scrape)} URLs únicas.")
    
    all_details = []
    with get_browser(context.scraper_name, headless=not context.requires_gui) as driver:
        for i, url in enumerate(urls_to_scrape, 1):
            logger.info(f"Procesando URL {i}/{len(urls_to_scrape)}: {url}")
            try:
                driver.uc_open_with_reconnect(url, 10)
                WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "h1.title-property"))
                )
                
                soup = BeautifulSoup(driver.page_source, "html.parser")
                
                # Extraer datos
                main_data = extract_main_details(soup)
                interactive_data = extract_interactive_details(driver)
                
                # Combinar datos
                full_details = main_data
                full_details.update(interactive_data)
                full_details['url_origen'] = url
                
                all_details.append(full_details)
                
            except Exception as e:
                logger.error(f"Fallo al procesar la URL de detalle {url}: {e}", exc_info=True)
                continue

    if not all_details:
        logger.error("No se pudo extraer ningún detalle de ninguna URL.")
        return False

    final_df = pd.DataFrame(all_details)
    final_df.to_csv(context.output_path, index=False, encoding="utf-8")
    logger.info(f"Scraping de detalle completado. Se guardaron {len(final_df)} registros en: {context.output_path}")
    
    return True

if __name__ == '__main__':
    try:
        scraper_context = ScraperContext.from_env()
        run(scraper_context)
    except Exception as e:
        logger.critical(f"El scraper de detalle falló al ejecutarse de forma independiente: {e}", exc_info=True)
        sys.exit(1)
