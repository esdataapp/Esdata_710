#!/usr/bin/env python3
"""lam.py - Scraper Lamudi (modo armonizado URL)

Refactor para integrarse al orquestador:
  - Modo URL (SCRAPER_MODE=url): genera archivo normalizado con columnas estándar.
  - Modo legacy: se conserva una versión reducida para compatibilidad temporal.

Columnas estándar: source_scraper, website, city, operation, product, listing_url, collected_at
"""
from __future__ import annotations

import os
import sys
import time
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

DDIR = 'data/'

def resolve_base_url(scraper_name: str = 'lam') -> str | None:
    """Obtiene la URL base de SCRAPER_INPUT_URL o del CSV <scraper>_urls.csv.
    Filtra por Website/Ciudad/Operacion/Producto usando envs del orquestador.
    """
    env_url = os.environ.get('SCRAPER_INPUT_URL')
    if env_url:
        return env_url
    base_dir = os.environ.get('SCRAPER_BASE_DIR') or os.getcwd()
    candidates = [
        os.path.join(base_dir, 'urls', f'{scraper_name}_urls.csv'),
        os.path.join(base_dir, 'Urls', f'{scraper_name}_urls.csv')
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

                # Columnas esperadas: PaginaWeb, Ciudad, Operacion, ProductoPaginaWeb, URL
                mask = (
                    (df['PaginaWeb'].astype(str) == w) &
                    (df['Ciudad'].astype(str) == c) &
                    (df['Operacion'].astype(str) == o) &
                    (df['ProductoPaginaWeb'].astype(str) == p)
                )
                row = df[mask].head(1)
                if not row.empty:
                    return str(row.iloc[0]['URL'])
                # Fallback: primera fila si no hay match exacto
                if len(df) > 0:
                    return str(df.iloc[0]['URL'])
            except Exception as e:
                print(f"[lam] No se pudo leer CSV de URLs ({path}): {e}")
                continue
    return None

def parse_cards(html: str) -> pd.DataFrame:
    cols = ['nombre','descripcion','ubicacion','url','precio','tipo','habitaciones','baños','metros_cuadrados','estacionamientos']
    data = pd.DataFrame(columns=cols)
    soup = BeautifulSoup(html, 'html.parser')
    cards = soup.find_all("div", class_="snippet js-snippet normal")
    for card in cards:
        temp = {c: None for c in cols}
        temp['tipo'] = 'venta'
        title_span = card.find("span", class_="snippet__content__title")
        if title_span:
            temp['nombre'] = title_span.get_text(strip=True)
        link_a = card.find("a", href=True)
        if link_a:
            temp['url'] = "https://www.lamudi.com.mx" + link_a['href']
        desc_div = card.find("div", class_="snippet__content__description")
        if desc_div:
            temp['descripcion'] = desc_div.get_text(strip=True)
        loc_span = card.find("span", attrs={"data-test": "snippet-content-location"})
        if loc_span:
            temp['ubicacion'] = loc_span.get_text(strip=True)
        price_div = card.find("div", class_="snippet__content__price")
        if price_div:
            temp['precio'] = price_div.get_text(strip=True)
        rooms_span = card.find("span", attrs={"data-test": "bedrooms-value"})
        if rooms_span:
            temp['habitaciones'] = rooms_span.get_text(strip=True)
        bathrooms_span = card.find("span", attrs={"data-test": "full-bathrooms-value"})
        if bathrooms_span:
            temp['baños'] = bathrooms_span.get_text(strip=True)
        area_span = card.find("span", attrs={"data-test": "area-value"})
        if area_span:
            temp['metros_cuadrados'] = area_span.get_text(strip=True)
        parking_span = card.find("span", attrs={"data-test": "amenity-value"})
        if parking_span:
            temp['estacionamientos'] = parking_span.get_text(strip=True)
        data = pd.concat([data, pd.DataFrame([temp])], ignore_index=True)
    return data

def save_legacy(df_page: pd.DataFrame):
    today_str = dt.date.today().isoformat()
    out_dir = os.path.join(DDIR, today_str)
    os.makedirs(out_dir, exist_ok=True)
    fname = os.path.join(out_dir, "lamudi-guadalajara-venta.csv")
    try:
        df_existing = pd.read_csv(fname)
    except FileNotFoundError:
        df_existing = pd.DataFrame()
    final_df = pd.concat([df_existing, df_page], ignore_index=True)
    final_df.to_csv(fname, index=False)
    print(f"[lam:legacy] Datos guardados en: {fname}")

def build_page_url(base_url: str, page: int) -> str:
    # Lamudi usa '?page=N' — reemplazar si existe, si no añadir
    import re
    if 'page=' in base_url:
        return re.sub(r'page=\d+', f'page={page}', base_url)
    sep = '&' if '?' in base_url else '?'
    return f"{base_url}{sep}page={page}"

def url_mode_collect():
    base_url = resolve_base_url('lam')
    output_file = os.environ.get('SCRAPER_OUTPUT_FILE')
    if not base_url or not output_file:
        print('[lam:url-mode] Faltan SCRAPER_INPUT_URL o SCRAPER_OUTPUT_FILE')
        return False
    meta = {
        'source_scraper': 'lam',
        'website': _env_abbreviation('SCRAPER_WEBSITE', 'PaginaWeb') or 'Lam',
        'city': _env_abbreviation('SCRAPER_CITY', 'Ciudad'),
        'operation': _env_abbreviation('SCRAPER_OPERATION', 'Operacion'),
        'product': _env_abbreviation('SCRAPER_PRODUCT', 'ProductoPaginaWeb'),
        'batch_id': os.environ.get('SCRAPER_BATCH_ID', '')
    }
    # Límite de páginas configurable
    try:
        max_pages = int(os.environ.get('SCRAPER_MAX_PAGES', '120'))
    except Exception:
        max_pages = 120
    aggregated = []
    seen = set()
    consecutive_empty = 0
    for page in range(1, max_pages + 1):
        page_url = build_page_url(base_url, page)
        print(f"[lam:url-mode] Página {page}: {page_url}")
        driver = Driver(uc=True, headless=True)
        try:
            driver.uc_open_with_reconnect(page_url, 4)
            try:
                driver.uc_gui_click_captcha()
            except Exception:
                pass
            time.sleep(4)
            html = driver.page_source
            df_cards = parse_cards(html)
            now_iso = dt.datetime.utcnow().isoformat()
            new_count = 0
            # Construcción extendida con columnas originales (prefijo raw_)
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
                        # extras
                        'raw_nombre': row.get('nombre'),
                        'raw_descripcion': row.get('descripcion'),
                        'raw_ubicacion': row.get('ubicacion'),
                        'raw_precio': row.get('precio'),
                        'raw_tipo': row.get('tipo'),
                        'raw_habitaciones': row.get('habitaciones'),
                        'raw_banos': row.get('baños'),
                        'raw_metros_cuadrados': row.get('metros_cuadrados'),
                        'raw_estacionamientos': row.get('estacionamientos'),
                    })
                    new_count += 1
            print(f"[lam:url-mode] Nuevos enlaces página {page}: {new_count}")
            if new_count == 0:
                consecutive_empty += 1
            else:
                consecutive_empty = 0
            if consecutive_empty >= 2:
                print('[lam:url-mode] 2 páginas consecutivas sin nuevos enlaces; fin.')
                break
        except Exception as e:
            print(f"[lam:url-mode] Error página {page}: {e}")
            break
        finally:
            driver.quit()
        time.sleep(1.5)

    if not aggregated:
        print('[lam:url-mode] Sin URLs recolectadas')
        pd.DataFrame(columns=['source_scraper','website','city','operation','product','listing_url','collected_at']).to_csv(output_file, index=False)
        return True
    out_df = pd.DataFrame(aggregated)
    if os.path.exists(output_file):
        try:
            prev = pd.read_csv(output_file)
            out_df = pd.concat([prev, out_df], ignore_index=True)
        except Exception:
            pass
    out_df.drop_duplicates(subset=['listing_url'], inplace=True)
    out_df.to_csv(output_file, index=False, encoding='utf-8')
    print(f"[lam:url-mode] Archivo URLs actualizado: {output_file} ({len(out_df)} filas)")
    return True

def legacy_run():
    print('[lam] Modo legacy')
    i = 1
    total_urls = 5
    while i <= total_urls:
        URL = build_page_url(os.environ.get('SCRAPER_INPUT_URL', 'https://www.lamudi.com.mx/jalisco/zapopan/departamento/for-sale/') or 'https://www.lamudi.com.mx/jalisco/zapopan/departamento/for-sale/', i)
        print(f"[lam:legacy] Iteración {i} / {total_urls} -> {URL}")
        driver = Driver(uc=True, headless=True)
        i += 1
        try:
            driver.uc_open_with_reconnect(URL, 4)
            try:
                driver.uc_gui_click_captcha()
            except Exception:
                pass
            html = driver.page_source
            df_page = parse_cards(html)
            save_legacy(df_page)
        except Exception as e:
            print(f"[lam:legacy] Error página: {e}")
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