"""
Script de prueba aislado para el flujo completo de Inmuebles24.
Fase 1: Ejecuta el scraper principal para recolectar URLs de anuncios.
Fase 2: Ejecuta el scraper de detalle para visitar cada URL y extraer datos completos.

Este script utiliza la lógica de los scrapers originales pero la adapta para
funcionar en un entorno de prueba controlado, guardando los resultados en
el directorio /temp.
"""
import os
import re
import time
import logging
from pathlib import Path
import pandas as pd
from bs4 import BeautifulSoup
from seleniumbase import Driver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- Configuración de la Prueba ---
# Reducimos el número de páginas para una prueba más rápida
BASE_URLS_TO_TEST = [
    "https://www.inmuebles24.com/departamentos-en-venta-en-zapopan-pagina-{}.html",
    "https://www.inmuebles24.com/casas-en-venta-en-guadalajara-pagina-{}.html",
]
PAGES_PER_URL = 5 # Reducido de 30 a 5 para agilizar la prueba
URLS_PER_PAGE_LIMIT = 5 # Limitar el número de anuncios por página para acelerar
DETAIL_SCRAPE_LIMIT = 10 # Limitar el número total de detalles a scrapear

TEMP_DIR = Path("temp")
URL_LIST_OUTPUT_FILE = TEMP_DIR / "inm24_test_urls.csv"
DETAIL_OUTPUT_FILE = TEMP_DIR / "inm24_test_details.csv"

# --- Configuración de Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Opciones del Navegador ---
BROWSER_OPTIONS = {
    "uc": True,
    "headed": True,
    "args": [
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--window-size=1280,1024"
    ]
}

# --- Lógica del Scraper Principal (inm24_original.py) ---

def scrape_main_page_source(html: str) -> pd.DataFrame:
    """Extrae los datos básicos de una página de resultados."""
    columns = ['nombre', 'descripcion', 'ubicacion', 'url', 'precio', 'tipo', 'habitaciones', 'baños']
    data = []
    soup = BeautifulSoup(html, 'html.parser')
    cards = soup.find_all("div", class_="postingCardLayout-module__posting-card-layout")

    for i, card in enumerate(cards):
        if i >= URLS_PER_PAGE_LIMIT:
            break
        temp_dict = {col: None for col in columns}
        temp_dict['tipo'] = 'venta'
        desc_h3 = card.find("h3", {"data-qa": "POSTING_CARD_DESCRIPTION"})
        if desc_h3 and (link_a := desc_h3.find("a")):
            temp_dict['nombre'] = link_a.get_text(strip=True)
            temp_dict['descripcion'] = link_a.get_text(strip=True)
            temp_dict['url'] = "https://www.inmuebles24.com" + link_a.get('href', '')
        
        if price_div := card.find("div", {"data-qa": "POSTING_CARD_PRICE"}):
            temp_dict['precio'] = price_div.get_text(strip=True)
            
        address_div = card.find("div", class_="postingLocations-module__location-address")
        address_txt = address_div.get_text(strip=True) if address_div else ""
        loc_h2 = card.find("h2", {"data-qa": "POSTING_CARD_LOCATION"})
        loc_txt = loc_h2.get_text(strip=True) if loc_h2 else ""
        temp_dict['ubicacion'] = f"{address_txt}, {loc_txt}" if address_txt and loc_txt else address_txt or loc_txt
        
        if features := card.find("h3", {"data-qa": "POSTING_CARD_FEATURES"}):
            for sp in features.find_all("span"):
                txt = sp.get_text(strip=True).lower()
                if "rec" in txt: temp_dict['habitaciones'] = txt
                if "bañ" in txt: temp_dict['baños'] = txt
        
        if temp_dict.get('url'):
            data.append(temp_dict)
            
    return pd.DataFrame(data)

def run_main_scraper_phase():
    """Ejecuta la fase de recolección de URLs."""
    logging.info("--- INICIANDO FASE 1: Recolección de URLs ---")
    TEMP_DIR.mkdir(exist_ok=True)
    all_urls_df = pd.DataFrame()
    
    driver = Driver(**BROWSER_OPTIONS)
    try:
        for base_url_template in BASE_URLS_TO_TEST:
            logging.info(f"Procesando plantilla de URL: {base_url_template}")
            for i in range(1, PAGES_PER_URL + 1):
                url = base_url_template.format(i)
                logging.info(f"Página {i}/{PAGES_PER_URL} - Navegando a: {url}")
                try:
                    driver.uc_open_with_reconnect(url, 5)
                    WebDriverWait(driver, 15).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "div.postingCardLayout-module__posting-card-layout"))
                    )
                    driver.uc_gui_click_captcha()
                    
                    html = driver.page_source
                    df_page = scrape_main_page_source(html)
                    
                    if not df_page.empty:
                        all_urls_df = pd.concat([all_urls_df, df_page], ignore_index=True)
                        logging.info(f"Se encontraron {len(df_page)} anuncios en la página.")
                    else:
                        logging.warning("No se encontraron anuncios en la página.")
                        break # Si una página no tiene resultados, no seguimos con las siguientes de esa plantilla

                except Exception as e:
                    logging.error(f"Error al procesar la página {url}: {e}")
                    continue
    finally:
        driver.quit()

    if not all_urls_df.empty:
        all_urls_df.drop_duplicates(subset=['url'], inplace=True)
        all_urls_df.to_csv(URL_LIST_OUTPUT_FILE, index=False)
        logging.info(f"FASE 1 COMPLETA: Se guardaron {len(all_urls_df)} URLs en {URL_LIST_OUTPUT_FILE}")
        return True
    else:
        logging.error("FASE 1 FALLIDA: No se recolectó ninguna URL.")
        return False

# --- Lógica del Scraper de Detalle (inm24_det_original.py) ---

def scrape_property_detail(html: str) -> dict:
    """Extrae todos los datos de la página de detalle de un inmueble."""
    soup = BeautifulSoup(html, "html.parser")
    data = {}

    # Título, tipo, área, etc.
    if h2 := soup.find("h2", class_="title-type-sup-property"):
        tokens = [t.strip() for t in h2.get_text(separator="·").split("·") if t.strip()]
        data["tipo_propiedad"] = tokens[0] if len(tokens) > 0 else ""
        data["area_m2"] = tokens[1] if len(tokens) > 1 else ""
    
    # Precio
    if (price_container := soup.find("div", class_="price-container-property")) and (price_value_div := price_container.find("div", class_="price-value")):
        if span := price_value_div.find("span"):
            data["precio"] = span.get_text(strip=True)

    # Dirección
    if (location_div := soup.find("div", class_="section-location-property")) and (h4 := location_div.find("h4")):
        data["direccion"] = h4.get_text(strip=True)
        
    # Título principal
    if h1 := soup.find("h1", class_="title-property"):
        data["titulo"] = h1.get_text(strip=True)

    # Descripción
    if (desc_section := soup.find("section", class_="article-section-description")) and (long_desc := desc_section.find("div", id="longDescription")):
        data["descripcion"] = long_desc.get_text(" ", strip=True)

    # Características de iconos
    if features_ul := soup.find("ul", id="section-icon-features-property"):
        for li in features_ul.find_all("li", class_="icon-feature"):
            text = re.sub(r'\s+', ' ', li.get_text(" ", strip=True)).strip()
            if "icon-stotal" in str(li): data["area_total"] = text
            elif "icon-scubierta" in str(li): data["area_cubierta"] = text
            elif "icon-bano" in str(li): data["banos_icon"] = text
            elif "icon-cochera" in str(li): data["estacionamientos_icon"] = text
            elif "icon-dormitorio" in str(li): data["recamaras_icon"] = text
            elif "icon-toilete" in str(li): data["medio_banos_icon"] = text
            elif "icon-antiguedad" in str(li): data["antiguedad_icon"] = text
            
    return data

def extract_information_after_click(driver) -> dict:
    """Hace clic en los botones de características y extrae la información."""
    info_botones = {}
    try:
        container = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "reactGeneralFeatures"))
        )
        buttons = container.find_elements(By.TAG_NAME, "button")
        logging.info(f"Se encontraron {len(buttons)} botones de características.")

        for button in buttons:
            try:
                button_text = button.text.strip()
                if not button_text: continue
                
                driver.execute_script("arguments[0].scrollIntoView(true);", button)
                WebDriverWait(driver, 5).until(EC.element_to_be_clickable(button))
                driver.execute_script("arguments[0].click();", button)
                
                # Esperar a que el contenido se despliegue
                time.sleep(0.5) 

                details_container = button.find_element(By.XPATH, "./following-sibling::div")
                features = [elem.text.strip() for elem in details_container.find_elements(By.TAG_NAME, "span") if elem.text.strip()]
                info_botones[button_text] = "; ".join(features)
                logging.info(f"  - Extraído de '{button_text}': {len(features)} items.")
            except Exception as e:
                logging.warning(f"No se pudo extraer información del botón '{button.text}': {e}")
    except Exception as e:
        logging.error(f"Error al buscar botones de características: {e}")
    return info_botones

def run_detail_scraper_phase():
    """Ejecuta la fase de extracción de detalles."""
    logging.info("--- INICIANDO FASE 2: Extracción de Detalles ---")
    if not URL_LIST_OUTPUT_FILE.exists():
        logging.error(f"No se encontró el archivo de URLs: {URL_LIST_OUTPUT_FILE}. Abortando fase 2.")
        return False

    urls_df = pd.read_csv(URL_LIST_OUTPUT_FILE)
    urls_to_scrape = urls_df["url"].dropna().unique().tolist()[:DETAIL_SCRAPE_LIMIT]
    logging.info(f"Se van a procesar {len(urls_to_scrape)} URLs únicas (límite: {DETAIL_SCRAPE_LIMIT}).")
    
    all_details_data = []
    
    driver = Driver(**BROWSER_OPTIONS)
    try:
        for i, url in enumerate(urls_to_scrape, 1):
            logging.info(f"Procesando URL {i}/{len(urls_to_scrape)}: {url}")
            try:
                driver.uc_open_with_reconnect(url, 5)
                WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "h1.title-property"))
                )
                
                html = driver.page_source
                data = scrape_property_detail(html)
                data['url_origen'] = url
                
                botones_data = extract_information_after_click(driver)
                data.update(botones_data)
                
                all_details_data.append(data)
                
            except Exception as e:
                logging.error(f"Error al procesar la URL de detalle {url}: {e}")
                continue
    finally:
        driver.quit()

    if all_details_data:
        final_df = pd.DataFrame(all_details_data)
        final_df = final_df.replace(r'[\r\n]+', ' ', regex=True)
        final_df.to_csv(DETAIL_OUTPUT_FILE, index=False, encoding="utf-8")
        logging.info(f"FASE 2 COMPLETA: Se guardaron {len(final_df)} registros de detalle en {DETAIL_OUTPUT_FILE}")
        return True
    else:
        logging.error("FASE 2 FALLIDA: No se extrajo ningún detalle.")
        return False

    return True

def main():
    """Orquesta las dos fases de la prueba."""
    start_time = time.time()
    
    # Fase 1
    if run_main_scraper_phase():
        # Fase 2
        run_detail_scraper_phase()
        
    end_time = time.time()
    logging.info(f"Prueba completada en {end_time - start_time:.2f} segundos.")

if __name__ == "__main__":
    main()
