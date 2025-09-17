#supabase pw "8.g!fdLM5UkA-_w"
import os
import sys
import time
import re
import datetime as dt
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup
from seleniumbase import Driver

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from abbreviation_utils import get_resolver

ABBREVIATIONS = get_resolver(strict=True)


def _clean_value(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def _env_abbreviation(env_var: str, context: str) -> str:
    return ABBREVIATIONS.to_abbreviation(os.environ.get(env_var, ''), context=context)

# Modo dual: si SCRAPER_MODE=url generamos un archivo de URLs normalizado
# Variables de entorno inyectadas por el orquestador/adapter:
# SCRAPER_MODE (url|detail) – aquí solo usamos 'url'
# SCRAPER_OUTPUT_FILE – ruta final del archivo que debe escribirse
# SCRAPER_WEBSITE, SCRAPER_CITY, SCRAPER_OPERATION, SCRAPER_PRODUCT
# SCRAPER_BATCH_ID

DDIR = 'data/'  # Sobrescrito por adapter

def resolve_base_url(scraper_name: str = 'inm24') -> str | None:
    """Obtiene la URL base desde SCRAPER_INPUT_URL o desde el CSV <scraper>_urls.csv
    filtrando por Website/Ciudad/Operacion/Producto.
    """
    env_url = os.environ.get('SCRAPER_INPUT_URL')
    if env_url:
        return env_url
    base_dir = os.environ.get('SCRAPER_BASE_DIR') or os.getcwd()
    candidates = [
        os.path.join(base_dir, 'urls', f'{scraper_name}_urls.csv'),
        os.path.join(base_dir, 'Urls', f'{scraper_name}_urls.csv'),
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                df = pd.read_csv(path)
                for column in ['PaginaWeb', 'Ciudad', 'Operacion', 'ProductoPaginaWeb']:
                    if column in df.columns:
                        df[column] = df[column].apply(
                            lambda v, col=column: ABBREVIATIONS.to_abbreviation(
                                _clean_value(v), context=col
                            )
                        )

                w = _env_abbreviation('SCRAPER_WEBSITE', 'PaginaWeb')
                c = _env_abbreviation('SCRAPER_CITY', 'Ciudad')
                o = _env_abbreviation('SCRAPER_OPERATION', 'Operacion')
                p = _env_abbreviation('SCRAPER_PRODUCT', 'ProductoPaginaWeb')

                mask = (
                    (df['PaginaWeb'].astype(str) == w) &
                    (df['Ciudad'].astype(str) == c) &
                    (df['Operacion'].astype(str) == o) &
                    (df['ProductoPaginaWeb'].astype(str) == p)
                )
                row = df[mask].head(1)
                if not row.empty:
                    return str(row.iloc[0]['URL'])
                if len(df) > 0:
                    return str(df.iloc[0]['URL'])
            except Exception as e:
                print(f"[inm24] No se pudo leer CSV de URLs ({path}): {e}")
                continue
    return None

def scrape_page_source(html):
    columns = ['nombre', 'descripcion', 'ubicacion', 'url', 'precio', 'tipo', 'habitaciones', 'baños']
    data = pd.DataFrame(columns=columns)
    soup = BeautifulSoup(html, 'html.parser')
    cards = soup.find_all("div", class_="postingCardLayout-module__posting-card-layout")

    for card in cards:
        temp_dict = {col: None for col in columns}
        temp_dict['tipo'] = 'venta'
        desc_h3 = card.find("h3", {"data-qa": "POSTING_CARD_DESCRIPTION"})
        if desc_h3:
            link_a = desc_h3.find("a")
            if link_a:
                temp_dict['nombre'] = link_a.get_text(strip=True)
                temp_dict['descripcion'] = link_a.get_text(strip=True)
                temp_dict['url'] = "https://www.inmuebles24.com" + link_a.get('href', '')
        price_div = card.find("div", {"data-qa": "POSTING_CARD_PRICE"})
        if price_div:
            temp_dict['precio'] = price_div.get_text(strip=True)
        address_div = card.find("div", class_="postingLocations-module__location-address")
        address_txt = address_div.get_text(strip=True) if address_div else ""
        loc_h2 = card.find("h2", {"data-qa": "POSTING_CARD_LOCATION"})
        loc_txt = loc_h2.get_text(strip=True) if loc_h2 else ""
        temp_dict['ubicacion'] = f"{address_txt}, {loc_txt}" if address_txt and loc_txt else address_txt or loc_txt
        features = card.find("h3", {"data-qa": "POSTING_CARD_FEATURES"})
        if features:
            for sp in features.find_all("span"):
                txt = sp.get_text(strip=True).lower()
                if "rec" in txt:
                    temp_dict['habitaciones'] = txt
                if "bañ" in txt:
                    temp_dict['baños'] = txt
        data = pd.concat([data, pd.DataFrame([temp_dict])], ignore_index=True)
    return data

def save_legacy(df_page):
    """Mantiene comportamiento legacy acumulando en carpeta data/YYYY-MM-DD/"""
    today_str = dt.date.today().isoformat()
    out_dir = os.path.join(DDIR, today_str)
    os.makedirs(out_dir, exist_ok=True)
    fname = os.path.join(out_dir, "inmuebles24-zapopan-departamentos-venta.csv")
    try:
        df_existing = pd.read_csv(fname)
    except FileNotFoundError:
        df_existing = pd.DataFrame()
    final_df = pd.concat([df_existing, df_page], ignore_index=True)
    final_df.to_csv(fname, index=False)
    print(f"[legacy] Datos guardados en: {fname}")

def save_url_mode(df_all_urls: pd.DataFrame, output_file: str):
    """Guarda el archivo en formato estándar de URLs para orquestador.
    Columnas mínimas: source_scraper, website, city, operation, product, listing_url, collected_at
    Si ya existe, se concatenan filas y se eliminan duplicados por listing_url.
    """
    meta = {
        'source_scraper': 'inm24',
        'website': _env_abbreviation('SCRAPER_WEBSITE', 'PaginaWeb') or 'Inm24',
        'city': _env_abbreviation('SCRAPER_CITY', 'Ciudad'),
        'operation': _env_abbreviation('SCRAPER_OPERATION', 'Operacion'),
        'product': _env_abbreviation('SCRAPER_PRODUCT', 'ProductoPaginaWeb'),
        'batch_id': os.environ.get('SCRAPER_BATCH_ID', '')
    }
    now_iso = dt.datetime.utcnow().isoformat()
    normalized_rows = []
    for _, r in df_all_urls.iterrows():
        url_val = r.get('url') or r.get('URL') or r.get('listing_url')
        if not url_val:
            continue
        normalized_rows.append({
            'source_scraper': meta['source_scraper'],
            'website': meta['website'],
            'city': meta['city'],
            'operation': meta['operation'],
            'product': meta['product'],
            'listing_url': url_val,
            'collected_at': now_iso,
            # columnas originales preservadas (prefijo raw_)
            'raw_nombre': r.get('nombre'),
            'raw_descripcion': r.get('descripcion'),
            'raw_ubicacion': r.get('ubicacion'),
            'raw_precio': r.get('precio'),
            'raw_tipo': r.get('tipo'),
            'raw_habitaciones': r.get('habitaciones'),
            'raw_banos': r.get('baños'),
        })
    if not normalized_rows:
        print("[inm24:url-mode] No se recolectaron URLs")
        return
    out_df = pd.DataFrame(normalized_rows)
    # Concatenar si existe
    if os.path.exists(output_file):
        try:
            prev = pd.read_csv(output_file)
            out_df = pd.concat([prev, out_df], ignore_index=True)
        except Exception:
            pass
    out_df.drop_duplicates(subset=['listing_url'], inplace=True)
    out_df.to_csv(output_file, index=False, encoding='utf-8')
    print(f"[inm24:url-mode] Archivo URLs actualizado: {output_file} ({len(out_df)} filas)")

def collect_url_pages():
    """Recolecta páginas partiendo de SCRAPER_INPUT_URL.
    Estrategia: si la URL contiene 'pagina-' se reemplaza el número; si no, se intenta anexar '-pagina-N'.
    Se detiene cuando una página no produce nuevas tarjetas o se excede límite duro.
    """
    base_url = resolve_base_url('inm24')
    if not base_url:
        print("[inm24:url-mode] No se pudo resolver URL base (env o CSV)")
        return pd.DataFrame()
    # Importante: NO alterar el base_url proveniente del CSV/env; solo paginar sobre él
    # Límite configurable con default alto para recorrer 'todas' las páginas
    try:
        max_pages = int(os.environ.get('SCRAPER_MAX_PAGES', '120'))
    except Exception:
        max_pages = 120
    seen_urls = set()
    aggregate = pd.DataFrame()
    for page_num in range(1, max_pages + 1):
        if 'pagina-' in base_url:
            URL = re.sub(r'pagina-\d+', f'pagina-{page_num}', base_url)
        else:
            # Inserta antes de .html si aplica
            if base_url.endswith('.html'):
                stem = base_url[:-5]
                URL = f"{stem}-pagina-{page_num}.html"
            else:
                URL = base_url.rstrip('/') + f'-pagina-{page_num}'
        print(f"[inm24:url-mode] Página {page_num}: {URL}")
        driver = Driver(uc=True, headless=True)
        try:
            driver.uc_open_with_reconnect(URL, 4)
            try:
                driver.uc_gui_click_captcha()
            except Exception:
                pass
            time.sleep(5)
            html = driver.page_source
            df_page = scrape_page_source(html)
            new_count = 0
            for u in df_page['url'].dropna().unique():
                if u not in seen_urls:
                    seen_urls.add(u)
                    new_count += 1
            aggregate = pd.concat([aggregate, df_page], ignore_index=True)
            print(f"[inm24:url-mode] Nuevos enlaces en página {page_num}: {new_count}")
            if new_count == 0:
                print("[inm24:url-mode] Sin nuevos enlaces; fin de paginación")
                break
        except Exception as e:
            print(f"[inm24:url-mode] Error página {page_num}: {e}")
            # Política: continuar hasta 2 errores consecutivos (simplificado: romper)
            break
        finally:
            driver.quit()
    return aggregate

def main():
    mode = os.environ.get('SCRAPER_MODE', 'url')
    output_file = os.environ.get('SCRAPER_OUTPUT_FILE')
    if mode == 'url' and output_file:
        print("[inm24] Ejecutando en modo URL (colector)")
        df_urls = collect_url_pages()
        save_url_mode(df_urls, output_file)
        return True
    # Legacy fallback
    print("[inm24] Ejecutando en modo legacy acumulativo")
    i = 1
    total_urls = 3  # reducido para evitar sobrecarga en modo legacy
    while i <= total_urls:
        URL = f'https://www.inmuebles24.com/departamentos-en-venta-en-zapopan-pagina-{i}.html'
        print(f"Iteración {i} of {total_urls}")
        driver = Driver(uc=True, headless=True)
        i += 1
        try:
            print(f"Navegando a: {URL}")
            driver.uc_open_with_reconnect(URL, 4)
            try:
                driver.uc_gui_click_captcha()
            except Exception:
                pass
            time.sleep(5)
            html = driver.page_source
            df_page = scrape_page_source(html)
            save_legacy(df_page)
        except Exception as e:
            print(f"Error al cargar la página: {e}")
        finally:
            driver.quit()
    return True

if __name__ == "__main__":
    main()