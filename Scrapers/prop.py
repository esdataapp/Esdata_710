"""prop.py - Scraper Propiedades.com (modo armonizado URL)

Refactor:
  - Modo URL (SCRAPER_MODE=url) produce CSV normalizado con columnas estándar.
  - Modo legacy/debug guarda HTML y primeras coincidencias para inspección.
Columnas estándar: source_scraper, website, city, operation, product, listing_url, collected_at
"""
from __future__ import annotations
import os
import re
import time
import datetime as dt
import pandas as pd
import requests
from bs4 import BeautifulSoup

DDIR = 'data/'
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
HEADERS = {"User-Agent": USER_AGENT}

def resolve_base_url(scraper_name: str = 'prop') -> str | None:
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
                w = os.environ.get('SCRAPER_WEBSITE', '')
                c = os.environ.get('SCRAPER_CITY', '')
                o = os.environ.get('SCRAPER_OPERATION', '')
                p = os.environ.get('SCRAPER_PRODUCT', '')
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
                print(f"[prop] No se pudo leer CSV de URLs ({path}): {e}")
                continue
    return None

def build_page_url(base_url: str, page: int) -> str:
    # Patrón '?pagina=N' o añadirlo
    if 'pagina=' in base_url:
        return re.sub(r'pagina=\d+', f'pagina={page}', base_url)
    sep = '&' if '?' in base_url else '?'
    return f"{base_url}{sep}pagina={page}"

def parse_listing_urls(html: str) -> list[str]:
    soup = BeautifulSoup(html, 'html.parser')
    urls = []
    # Heurística: enlaces con '/inmueble/' o '/propiedad/'
    for a in soup.find_all('a', href=True):
        href = a['href']
        if any(k in href for k in ['/inmueble/', '/propiedad/', '/departamento-']):
            if href.startswith('/'):
                href_full = 'https://propiedades.com' + href
            elif href.startswith('http'):
                href_full = href
            else:
                continue
            urls.append(href_full)
    # Dedupe preserving order
    seen = set()
    out = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out

def fetch_page(url: str) -> str | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        if r.status_code != 200:
            print(f"[prop] Status {r.status_code} en {url}")
            return None
        return r.text
    except Exception as e:
        print(f"[prop] Error solicitando {url}: {e}")
        return None

def url_mode_collect():
    base_url = resolve_base_url('prop')
    output_file = os.environ.get('SCRAPER_OUTPUT_FILE')
    if not base_url or not output_file:
        print('[prop:url-mode] Faltan SCRAPER_INPUT_URL o SCRAPER_OUTPUT_FILE')
        return False
    meta = {
        'source_scraper': 'prop',
        'website': os.environ.get('SCRAPER_WEBSITE', 'Prop'),
        'city': os.environ.get('SCRAPER_CITY', ''),
        'operation': os.environ.get('SCRAPER_OPERATION', ''),
        'product': os.environ.get('SCRAPER_PRODUCT', ''),
        'batch_id': os.environ.get('SCRAPER_BATCH_ID', '')
    }
    try:
        max_pages = int(os.environ.get('SCRAPER_MAX_PAGES', '120'))
    except Exception:
        max_pages = 120
    aggregated = []
    seen = set()
    consecutive_empty = 0
    for page in range(1, max_pages + 1):
        page_url = build_page_url(base_url, page)
        print(f"[prop:url-mode] Página {page}: {page_url}")
        html = fetch_page(page_url)
        if not html:
            consecutive_empty += 1
            if consecutive_empty >= 2:
                print('[prop:url-mode] 2 páginas sin contenido; fin.')
                break
            continue
        urls = parse_listing_urls(html)
        now_iso = dt.datetime.utcnow().isoformat()
        new_count = 0
        for u in urls:
            if u not in seen:
                seen.add(u)
                aggregated.append({
                    'source_scraper': meta['source_scraper'],
                    'website': meta['website'],
                    'city': meta['city'],
                    'operation': meta['operation'],
                    'product': meta['product'],
                    'listing_url': u,
                    'collected_at': now_iso
                })
                new_count += 1
        print(f"[prop:url-mode] Nuevos enlaces página {page}: {new_count}")
        if new_count == 0:
            consecutive_empty += 1
        else:
            consecutive_empty = 0
        if consecutive_empty >= 2:
            print('[prop:url-mode] 2 páginas consecutivas sin nuevos enlaces; fin.')
            break
        time.sleep(1.5)

    if not aggregated:
        print('[prop:url-mode] Sin URLs recolectadas')
        # Ensure directory exists
        try:
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
        except Exception:
            pass
        pd.DataFrame(columns=['source_scraper','website','city','operation','product','listing_url','collected_at']).to_csv(output_file, index=False)
        return True
    out_df = pd.DataFrame(aggregated)
    # Ensure directory exists for non-empty write
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
    print(f"[prop:url-mode] Archivo URLs actualizado: {output_file} ({len(out_df)} filas)")
    return True

def legacy_debug():
    print('[prop] Modo legacy/debug')
    test_url = os.environ.get('SCRAPER_INPUT_URL') or 'https://propiedades.com/df/departamentos?pagina=1'
    html = fetch_page(test_url)
    if not html:
        return False
    os.makedirs(DDIR, exist_ok=True)
    with open(os.path.join(DDIR,'prop_debug.html'),'w',encoding='utf-8') as f:
        f.write(html)
    urls = parse_listing_urls(html)
    pd.DataFrame({'listing_url': urls}).to_csv(os.path.join(DDIR,'prop_debug_urls.csv'), index=False)
    print(f"[prop:legacy] Debug guardado ({len(urls)} urls)")
    return True

def main():
    mode = os.environ.get('SCRAPER_MODE','url')
    if mode == 'url':
        return url_mode_collect()
    return legacy_debug()

if __name__ == '__main__':
    main()