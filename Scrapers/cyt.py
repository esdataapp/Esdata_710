#!/usr/bin/env python3
"""cyt.py - Scraper Casas y Terrenos (modo armonizado URL)

Refactor para integrarse al orquestador moderno:
  - Modo URL (SCRAPER_MODE=url): genera archivo normalizado con columnas estándar
  - Modo legacy (fallback): mantiene scraping básico previo para compatibilidad temporal

Columnas salida (modo URL): source_scraper, website, city, operation, product, listing_url, collected_at
"""
from __future__ import annotations

import os
import sys
import time
import datetime as dt
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

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

DDIR = 'data/'  # sobrescrito por adapter si aplica legacy

# Selector heurístico de cards
CARD_XPATH = "//div[contains(@class, 'mx-2') and contains(@class, 'w-[320px]')]"

def extract_cards(html: str) -> pd.DataFrame:
    columns = ['descripcion', 'ubicacion', 'url', 'precio', 'tipo', 'habitaciones', 'baños', 'estacionamientos', 'superficie', 'codigo']
    data = pd.DataFrame(columns=columns)
    soup = BeautifulSoup(html, 'html.parser')
    cards = soup.find_all("div", class_=lambda x: x and "mx-2" in x and "w-[320px]" in x)
    for card in cards:
        temp = {c: None for c in columns}
        temp['tipo'] = 'venta'
        link = card.find("a", target="_blank")
        if link:
            desc_span = card.find("span", class_=lambda x: x and "text-text-primary font-bold line-clamp-2" in x)
            temp['descripcion'] = desc_span.get_text(strip=True) if desc_span else None
            temp['url'] = link.get('href')
        ubic = card.find("span", class_=lambda x: x and "text-blue-cyt" in x)
        temp['ubicacion'] = ubic.get_text(strip=True) if ubic else None
        precio = card.find("span", class_=lambda x: x and "text-blue-cyt font-bold" in x)
        temp['precio'] = precio.get_text(strip=True) if precio else None
        features = card.find_all("p", class_=lambda x: x and "text-sm" in x)
        if len(features) >= 4:
            temp['habitaciones'] = features[0].get_text(strip=True)
            temp['baños'] = features[1].get_text(strip=True)
            temp['estacionamientos'] = features[2].get_text(strip=True)
            temp['superficie'] = features[3].get_text(strip=True)
        codigo = card.find("span", class_=lambda x: x and "text-extralight" in x)
        if codigo:
            temp['codigo'] = codigo.get_text(strip=True).replace("Código: ", "")
        data = pd.concat([data, pd.DataFrame([temp])], ignore_index=True)
    return data

def save_legacy(df_page: pd.DataFrame):
    today_str = dt.date.today().isoformat()
    out_dir = os.path.join(DDIR, today_str)
    os.makedirs(out_dir, exist_ok=True)
    fname = os.path.join(out_dir, "casasyterrenos-departamento-zapopan-venta.csv")
    try:
        df_existing = pd.read_csv(fname)
    except FileNotFoundError:
        df_existing = pd.DataFrame()
    final_df = pd.concat([df_existing, df_page], ignore_index=True)
    final_df.to_csv(fname, index=False)
    print(f"[cyt:legacy] Datos guardados en: {fname}")

def resolve_base_url(scraper_name: str = 'cyt') -> str | None:
    """Resuelve la URL base desde SCRAPER_INPUT_URL o desde <scraper>_urls.csv
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
                print(f"[cyt] No se pudo leer CSV de URLs ({path}): {e}")
                continue
    return None

def url_mode_collect():
    base_url = resolve_base_url('cyt')
    output_file = os.environ.get('SCRAPER_OUTPUT_FILE')
    if not base_url or not output_file:
        print('[cyt:url-mode] Faltan SCRAPER_INPUT_URL o SCRAPER_OUTPUT_FILE')
        return False
    meta = {
        'source_scraper': 'cyt',
        'website': _env_abbreviation('SCRAPER_WEBSITE', 'PaginaWeb') or 'CyT',
        'city': _env_abbreviation('SCRAPER_CITY', 'Ciudad'),
        'operation': _env_abbreviation('SCRAPER_OPERATION', 'Operacion'),
        'product': _env_abbreviation('SCRAPER_PRODUCT', 'ProductoPaginaWeb'),
        'batch_id': os.environ.get('SCRAPER_BATCH_ID', '')
    }
    # Estrategia: detectar parámetro de paginación '?pagina=' o final '?desde=' incremental.
    # En la URL original parece usarse '?desde=' como offset. Asumimos incremento de 1 y tope de seguridad.
    urls_seen = set()
    aggregated = []
    try:
        max_pages = int(os.environ.get('SCRAPER_MAX_PAGES', '120'))
    except Exception:
        max_pages = 120
    consecutive_empty = 0
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(60)
    try:
        for page in range(0, max_pages):
            # Heurística: reemplazar "results_page=" valor final
            if 'results_page=' in base_url:
                page_url = re_sub_results_page(base_url, page)
            else:
                sep = '&' if '?' in base_url else '?'
                page_url = f"{base_url}{sep}results_page={page}"
            print(f"[cyt:url-mode] Página lógica {page}: {page_url}")
            try:
                driver.get(page_url)
                WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.XPATH, CARD_XPATH)))
                html = driver.page_source
                df_cards = extract_cards(html)
                now_iso = dt.datetime.utcnow().isoformat()
                new_count = 0
                # extender con columnas originales como raw_*
                for _, row in df_cards.iterrows():
                    url = row.get('url')
                    if not url:
                        continue
                    if url not in urls_seen:
                        urls_seen.add(url)
                        aggregated.append({
                            'source_scraper': meta['source_scraper'],
                            'website': meta['website'],
                            'city': meta['city'],
                            'operation': meta['operation'],
                            'product': meta['product'],
                            'listing_url': url,
                            'collected_at': now_iso,
                            'raw_descripcion': row.get('descripcion'),
                            'raw_ubicacion': row.get('ubicacion'),
                            'raw_precio': row.get('precio'),
                            'raw_tipo': row.get('tipo'),
                            'raw_habitaciones': row.get('habitaciones'),
                            'raw_banos': row.get('baños'),
                            'raw_estacionamientos': row.get('estacionamientos'),
                            'raw_superficie': row.get('superficie'),
                            'raw_codigo': row.get('codigo'),
                        })
                        new_count += 1
                print(f"[cyt:url-mode] Nuevos enlaces página {page}: {new_count}")
                if new_count == 0:
                    consecutive_empty += 1
                else:
                    consecutive_empty = 0
                if consecutive_empty >= 2:
                    print('[cyt:url-mode] 2 páginas seguidas sin nuevos enlaces, fin.')
                    break
                time.sleep(2)
            except Exception as e:
                print(f"[cyt:url-mode] Error página {page}: {e}")
                break
    finally:
        driver.quit()

    if not aggregated:
        print('[cyt:url-mode] Sin URLs recolectadas')
        try:
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
        except Exception:
            pass
        pd.DataFrame(columns=['source_scraper','website','city','operation','product','listing_url','collected_at']).to_csv(output_file, index=False)
        return True
    out_df = pd.DataFrame(aggregated)
    try:
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
    except Exception:
        pass
    if os.path.exists(output_file):
        try:
            prev = pd.read_csv(output_file)
            out_df = pd.concat([prev, out_df], ignore_index=True)
        except Exception:
            pass
    out_df.drop_duplicates(subset=['listing_url'], inplace=True)
    out_df.to_csv(output_file, index=False, encoding='utf-8')
    print(f"[cyt:url-mode] Archivo URLs actualizado: {output_file} ({len(out_df)} filas)")
    return True

def re_sub_results_page(url: str, page: int) -> str:
    import re
    # Reemplaza valor tras 'results_page='
    if 'results_page=' not in url:
        return url
    return re.sub(r'(results_page=)\d+', rf'\g<1>{page}', url)

def legacy_run():
    print('[cyt] Modo legacy (acumulativo)')
    options = Options()
    options.add_argument('--headless=new')
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(60)
    total_pages = 5
    for i in range(0, total_pages):
        URL = re_sub_results_page(os.environ.get('SCRAPER_INPUT_URL', '' ) or 'https://www.casasyterrenos.com/jalisco/zapopan/departamentos/venta?desde=0&hasta=1000000000&utm_source=results_page=0', i)
        print(f"[cyt:legacy] Página {i}")
        try:
            driver.get(URL)
            WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.XPATH, CARD_XPATH)))
            html = driver.page_source
            df_page = extract_cards(html)
            save_legacy(df_page)
        except Exception as e:
            print(f"[cyt:legacy] Error página {i}: {e}")
            break
    driver.quit()
    return True

def main():
    mode = os.environ.get('SCRAPER_MODE', 'url')
    if mode == 'url':
        return url_mode_collect()
    return legacy_run()

if __name__ == '__main__':
    main()