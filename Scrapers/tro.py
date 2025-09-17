"""tro.py - Scraper Trovit (modo armonizado URL)

Este refactor implementa el patrón armonizado de 'colector de URLs' utilizado por el orquestador.
Comportamiento:
  - Si SCRAPER_MODE=url => genera/actualiza un CSV normalizado con columnas estándar.
  - (Legacy simplificado) Si no está en modo URL, intenta una sola página y guarda estructura mínima.

Columnas estándar de salida (modo URL):
  source_scraper, website, city, operation, product, listing_url, collected_at

Variables inyectadas por adapter/orchestrator:
  SCRAPER_MODE, SCRAPER_OUTPUT_FILE, SCRAPER_INPUT_URL, SCRAPER_WEBSITE,
  SCRAPER_CITY, SCRAPER_OPERATION, SCRAPER_PRODUCT, SCRAPER_BATCH_ID
"""

from __future__ import annotations

import os
import re
import sys
import time
import datetime as dt
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

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

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/118.0.0.0 Safari/537.36"
)
HEADERS = {"User-Agent": USER_AGENT}

DDIR = 'data/'  # puede ser sobrescrito por adapter si se usa legacy
def resolve_base_url(scraper_name: str = 'tro') -> str | None:
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
                print(f"[tro] No se pudo leer CSV de URLs ({path}): {e}")
                continue
    return None


def parse_listing_cards(html: str) -> list[dict]:
    """Extrae URLs de listings desde el HTML de una página Trovit.
    Estratégicamente buscamos enlaces a detalles que suelen tener '/detalle/' o parámetros con 'cod.'
    Este selector es heurístico y puede requerir actualización futura.
    """
    soup = BeautifulSoup(html, 'html.parser')
    listings = []
    # Heurística: enlaces dentro de artículos o divs con clase 'item'
    for a in soup.select('a'):  # broad, luego filtramos
        href = a.get('href')
        if not href:
            continue
        # Filtrar patrones típicos de Trovit (heurísticos)
        if 'trovit.com.mx' in href or href.startswith('/'):
            if any(k in href.lower() for k in ['property', 'detalle', 'cod.', 'adlist', 'listing']):
                # Normalizar URL completa
                if href.startswith('/'):
                    href_full = 'https://casas.trovit.com.mx' + href
                else:
                    href_full = href
                listings.append({'listing_url': href_full})
    # Eliminar duplicados preserve order
    seen = set()
    unique = []
    for item in listings:
        u = item['listing_url']
        if u not in seen:
            seen.add(u)
            unique.append(item)
    return unique

def fetch_page(url: str, timeout: int = 30) -> str | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        if r.status_code != 200:
            print(f"[tro] Status inesperado {r.status_code} en {url}")
            return None
        return r.text
    except Exception as e:
        print(f"[tro] Error solicitando {url}: {e}")
        return None

def build_page_url(base_url: str, page_number: int) -> str:
    """Construye la URL de paginación.
    Si base_url ya tiene '/page.N' se reemplaza, si no se añade '/page.N'."""
    # reconocer patrón page.<num>
    if re.search(r'/page\.\d+', base_url):
        return re.sub(r'/page\.\d+', f'/page.{page_number}', base_url)
    # Añadir sufijo si no existe
    if base_url.endswith('/'):
        return base_url + f'page.{page_number}'
    return base_url + f'/page.{page_number}'

def collect_url_mode():
    base_url = resolve_base_url('tro')
    output_file = os.environ.get('SCRAPER_OUTPUT_FILE')
    if not base_url or not output_file:
        print('[tro:url-mode] Faltan SCRAPER_INPUT_URL o SCRAPER_OUTPUT_FILE; abortando')
        return False

    meta = {
        'source_scraper': 'tro',
        'website': _env_abbreviation('SCRAPER_WEBSITE', 'PaginaWeb') or 'Tro',
        'city': _env_abbreviation('SCRAPER_CITY', 'Ciudad'),
        'operation': _env_abbreviation('SCRAPER_OPERATION', 'Operacion'),
        'product': _env_abbreviation('SCRAPER_PRODUCT', 'ProductoPaginaWeb'),
        'batch_id': os.environ.get('SCRAPER_BATCH_ID', '')
    }

    max_pages = 120  # límite alto por defecto
    try:
        max_pages = int(os.environ.get('SCRAPER_MAX_PAGES', '120'))
    except Exception:
        max_pages = 120
    aggregated_rows = []
    seen_urls = set()
    consecutive_empty = 0

    for page in range(1, max_pages + 1):
        page_url = build_page_url(base_url, page)
        print(f"[tro:url-mode] Página {page}: {page_url}")
        html = fetch_page(page_url)
        if not html:
            consecutive_empty += 1
            if consecutive_empty >= 2:
                print('[tro:url-mode] 2 páginas consecutivas sin contenido; deteniendo.')
                break
            continue
        cards = parse_listing_cards(html)
        new_this_page = 0
        now_iso = dt.datetime.utcnow().isoformat()
        for c in cards:
            url_val = c['listing_url']
            if url_val not in seen_urls:
                seen_urls.add(url_val)
                aggregated_rows.append({
                    'source_scraper': meta['source_scraper'],
                    'website': meta['website'],
                    'city': meta['city'],
                    'operation': meta['operation'],
                    'product': meta['product'],
                    'listing_url': url_val,
                    'collected_at': now_iso,
                    # no hay columnas ricas actualmente; dejamos placeholders opcionales
                })
                new_this_page += 1
        print(f"[tro:url-mode] Nuevos enlaces página {page}: {new_this_page}")
        if new_this_page == 0:
            consecutive_empty += 1
        else:
            consecutive_empty = 0
        if consecutive_empty >= 2:
            print('[tro:url-mode] 2 páginas consecutivas sin nuevos enlaces; fin.')
            break
        # Pequeña pausa para no saturar
        time.sleep(1.5)

    if not aggregated_rows:
        print('[tro:url-mode] No se recolectaron URLs')
        # Crear archivo vacío con cabecera estándar (para evitar fallo de orquestador)
        try:
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
        except Exception:
            pass
        pd.DataFrame(columns=['source_scraper','website','city','operation','product','listing_url','collected_at']).to_csv(output_file, index=False, encoding='utf-8')
        return True

    out_df = pd.DataFrame(aggregated_rows)
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
    print(f"[tro:url-mode] Archivo actualizado: {output_file} ({len(out_df)} filas)")
    return True

def legacy_single_page_debug():
    """Pequeño modo legacy/debug para inspeccionar estructura actual.
    Guarda HTML bruto y listado de enlaces detectados en carpeta temporal dentro de DDIR.
    """
    url = os.environ.get('SCRAPER_INPUT_URL') or 'https://casas.trovit.com.mx/index.php/cod.search_homes/type.1/what_d.Mexico'
    html = fetch_page(url)
    if not html:
        return False
    os.makedirs(DDIR, exist_ok=True)
    with open(os.path.join(DDIR, 'trovit_debug.html'), 'w', encoding='utf-8') as f:
        f.write(html)
    cards = parse_listing_cards(html)
    debug_csv = os.path.join(DDIR, 'trovit_debug_urls.csv')
    pd.DataFrame(cards).to_csv(debug_csv, index=False)
    print(f"[tro:legacy] Debug guardado: {debug_csv} ({len(cards)} urls)")
    return True

def main():
    mode = os.environ.get('SCRAPER_MODE', 'url')
    if mode == 'url':
        return collect_url_mode()
    print('[tro] Modo legacy/debug')
    return legacy_single_page_debug()

if __name__ == '__main__':
    main()