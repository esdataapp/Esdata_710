#!/usr/bin/env python3
"""mit.py - Scraper Mitula (modo armonizado URL)

Refactor:
  - Modo URL (SCRAPER_MODE=url): colecta enlaces normalizados
  - Modo legacy: scraping reducido acumulativo
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

DDIR = 'data/'

def resolve_base_url(scraper_name: str = 'mit') -> str | None:
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
                print(f"[mit] No se pudo leer CSV de URLs ({path}): {e}")
                continue
    return None

def parse_cards(html: str) -> pd.DataFrame:
    columns = ['nombre','precio','ubicacion','habitaciones','baños','metros_cuadrados','amenidades','fecha_publicacion','agencia','descripcion','url']
    data = pd.DataFrame(columns=columns)
    soup = BeautifulSoup(html, 'html.parser')
    cards = soup.find_all("div", class_="listing-card__content")
    for card in cards:
        tmp = {c: None for c in columns}
        title_span = card.find("span", {"data-test": "snippet__title"})
        if title_span:
            tmp['nombre'] = title_span.get_text(strip=True)
        price_span = card.find("span", {"data-test": "price__actual"})
        if price_span:
            tmp['precio'] = price_span.get_text(strip=True)
        location_div = card.find("div", {"data-test": "snippet__location"})
        if location_div:
            tmp['ubicacion'] = location_div.get_text(strip=True)
        bedrooms_p = card.find("p", {"data-test": "bedrooms"})
        if bedrooms_p:
            tmp['habitaciones'] = bedrooms_p.get_text(strip=True)
        bathrooms_p = card.find("p", {"data-test": "bathrooms"})
        if bathrooms_p:
            tmp['baños'] = bathrooms_p.get_text(strip=True)
        area_p = card.find("p", {"data-test": "floor-area"})
        if area_p:
            tmp['metros_cuadrados'] = area_p.get_text(strip=True)
        amenities = card.find_all("span", class_="listing-card__facilities__facility")
        tmp['amenidades'] = ", ".join(a.get_text(strip=True) for a in amenities) if amenities else None
        pub_info_p = card.find("p", {"data-test": "snippet__published-date-and-agency"})
        if pub_info_p:
            text = pub_info_p.get_text(strip=True)
            parts = text.split('-', 1)
            tmp['fecha_publicacion'] = parts[0].strip()
            tmp['agencia'] = parts[1].strip() if len(parts) > 1 else None
        desc_div = card.find("div", {"data-test": "snippet__description"})
        if desc_div:
            tmp['descripcion'] = desc_div.get_text(strip=True)
        detail_button = card.find("button", {"data-test": "snippet__view-detail-button"})
        if detail_button:
            parent = detail_button.find_parent("a")
            if parent and parent.get('href'):
                tmp['url'] = f"https://casas.mitula.mx{parent.get('href')}"
        data = pd.concat([data, pd.DataFrame([tmp])], ignore_index=True)
    return data

def save_legacy(df_page: pd.DataFrame):
    today_str = dt.date.today().isoformat()
    out_dir = os.path.join(DDIR, today_str)
    os.makedirs(out_dir, exist_ok=True)
    fname = os.path.join(out_dir, "mitula-zapopan-venta.csv")
    try:
        existing = pd.read_csv(fname)
    except FileNotFoundError:
        existing = pd.DataFrame()
    final_df = pd.concat([existing, df_page], ignore_index=True)
    final_df.to_csv(fname, index=False)
    print(f"[mit:legacy] Guardado: {fname}")

def build_page_url(base_url: str, page: int) -> str:
    import re
    # Mitula usa 'page=N' — reemplazar si existe
    if 'page=' in base_url:
        return re.sub(r'page=\d+', f'page={page}', base_url)
    sep = '&' if '?' in base_url else '?'
    return f"{base_url}{sep}page={page}"

def url_mode_collect():
    base_url = resolve_base_url('mit')
    output_file = os.environ.get('SCRAPER_OUTPUT_FILE')
    if not base_url or not output_file:
        print('[mit:url-mode] Faltan SCRAPER_INPUT_URL o SCRAPER_OUTPUT_FILE')
        return False
    meta = {
        'source_scraper': 'mit',
        'website': _env_abbreviation('SCRAPER_WEBSITE', 'PaginaWeb') or 'Mit',
        'city': _env_abbreviation('SCRAPER_CITY', 'Ciudad'),
        'operation': _env_abbreviation('SCRAPER_OPERATION', 'Operacion'),
        'product': _env_abbreviation('SCRAPER_PRODUCT', 'ProductoPaginaWeb'),
        'batch_id': os.environ.get('SCRAPER_BATCH_ID', '')
    }
    try:
        max_pages = int(os.environ.get('SCRAPER_MAX_PAGES', '120'))
    except Exception:
        max_pages = 120
    aggregated = []
    seen = set()
    consecutive_empty = 0
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(60)
    try:
        for page in range(1, max_pages + 1):
            page_url = build_page_url(base_url, page)
            print(f"[mit:url-mode] Página {page}: {page_url}")
            try:
                driver.get(page_url)
                WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.CLASS_NAME, 'listing-card__content')))
                html = driver.page_source
                df_cards = parse_cards(html)
                now_iso = dt.datetime.utcnow().isoformat()
                new_count = 0
                for _, row in df_cards.iterrows():
                    url = row.get('url')
                    if not url:
                        continue
                    if url not in seen:
                        seen.add(url)
                        aggregated.append({
                            'source_scraper': meta['source_scraper'],
                            'website': meta['website'],
                            'city': meta['city'],
                            'operation': meta['operation'],
                            'product': meta['product'],
                            'listing_url': url,
                            'collected_at': now_iso,
                            'raw_nombre': row.get('nombre'),
                            'raw_precio': row.get('precio'),
                            'raw_ubicacion': row.get('ubicacion'),
                            'raw_habitaciones': row.get('habitaciones'),
                            'raw_banos': row.get('baños'),
                            'raw_metros_cuadrados': row.get('metros_cuadrados'),
                            'raw_amenidades': row.get('amenidades'),
                            'raw_fecha_publicacion': row.get('fecha_publicacion'),
                            'raw_agencia': row.get('agencia'),
                            'raw_descripcion': row.get('descripcion'),
                        })
                        new_count += 1
                print(f"[mit:url-mode] Nuevos enlaces página {page}: {new_count}")
                if new_count == 0:
                    consecutive_empty += 1
                else:
                    consecutive_empty = 0
                if consecutive_empty >= 2:
                    print('[mit:url-mode] 2 páginas sin nuevos enlaces; fin.')
                    break
                time.sleep(2)
            except Exception as e:
                print(f"[mit:url-mode] Error página {page}: {e}")
                break
    finally:
        driver.quit()

    if not aggregated:
        print('[mit:url-mode] Sin URLs recolectadas')
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
    print(f"[mit:url-mode] Archivo URLs actualizado: {output_file} ({len(out_df)} filas)")
    return True

def legacy_run():
    print('[mit] Modo legacy')
    total_urls = 5
    for i in range(1, total_urls + 1):
        URL = build_page_url(os.environ.get('SCRAPER_INPUT_URL', 'https://casas.mitula.mx/find?operationType=sell&geoId=mitula-MX-poblacion-0000531914&text=Zapopan') or 'https://casas.mitula.mx/find?operationType=sell&geoId=mitula-MX-poblacion-0000531914&text=Zapopan', i)
        print(f"[mit:legacy] Página {i}")
        options = Options()
        options.add_argument('--headless=new')
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(60)
        try:
            driver.get(URL)
            WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.CLASS_NAME, 'listing-card__content')))
            html = driver.page_source
            df_page = parse_cards(html)
            save_legacy(df_page)
        except Exception as e:
            print(f"[mit:legacy] Error página {i}: {e}")
            break
        finally:
            driver.quit()
    return True

def main():
    mode = os.environ.get('SCRAPER_MODE', 'url')
    if mode == 'url':
        return url_mode_collect()
    return legacy_run()

if __name__ == '__main__':
    main()
