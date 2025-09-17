#!/usr/bin/env python3
"""
Test largo de INM24 - Usar URLs reales del CSV y procesar todas las páginas
"""

import os
import sys
import pandas as pd
import datetime as dt
from pathlib import Path
from bs4 import BeautifulSoup
from seleniumbase import Driver
import time

# Configurar variables de entorno
os.environ['DISPLAY'] = ':99'

def load_inm24_urls():
    """Cargar URLs del archivo CSV de INM24"""
    csv_path = '/home/esdata/Documents/GitHub/Esdata_710/urls/inm24_urls.csv'
    
    try:
        df = pd.read_csv(csv_path, encoding='utf-8')
        print(f"✓ CSV cargado: {len(df)} URLs encontradas")
        
        # Filtrar solo URLs válidas (no vacías)
        valid_mask = df['URL'].notna()
        valid_urls = df[valid_mask].copy()
        # Filtrar URLs no vacías
        non_empty_mask = valid_urls['URL'].str.strip() != ''
        valid_urls = valid_urls[non_empty_mask].copy()
        print(f"✓ URLs válidas: {len(valid_urls)}")
        
        if len(valid_urls) > 0:
            first_url = valid_urls.iloc[0]
            print(f"✓ Primera URL seleccionada:")
            print(f"  - PaginaWeb: {first_url['PaginaWeb']}")
            print(f"  - Ciudad: {first_url['Ciudad']}")
            print(f"  - Operacion: {first_url['Operacion']}")
            print(f"  - Producto: {first_url['ProductoPaginaWeb']}")
            print(f"  - URL Base: {first_url['URL']}")
            
            return first_url
        else:
            print("✗ No se encontraron URLs válidas")
            return None
            
    except Exception as e:
        print(f"✗ Error cargando CSV: {e}")
        return None

def convert_url_to_paginated(base_url):
    """Convertir URL base a formato paginado"""
    # La mayoría de URLs de inmuebles24 se pueden paginar agregando -pagina-N.html
    if base_url.endswith('.html'):
        # Remover .html del final
        base_without_extension = base_url[:-5]
        return base_without_extension + '-pagina-{}.html'
    else:
        # Si no termina en .html, agregar el formato de paginación
        return base_url.rstrip('/') + '-pagina-{}.html'

def scrape_page_source(html):
    """Extraer datos de una página de INM24"""
    columns = ['nombre', 'descripcion', 'ubicacion', 'url', 'precio', 'tipo', 'habitaciones', 'baños']
    data = pd.DataFrame(columns=columns)
    soup = BeautifulSoup(html, 'html.parser')
    cards = soup.find_all("div", class_="postingCardLayout-module__posting-card-layout")

    for card in cards:
        temp_dict = {col: None for col in columns}
        temp_dict['tipo'] = 'venta'
        
        # Nombre y descripción
        desc_h3 = card.find("h3", {"data-qa": "POSTING_CARD_DESCRIPTION"})
        if desc_h3:
            link_a = desc_h3.find("a")
            if link_a:
                temp_dict['nombre'] = link_a.get_text(strip=True)
                temp_dict['descripcion'] = link_a.get_text(strip=True)
                temp_dict['url'] = "https://www.inmuebles24.com" + link_a.get('href', '')
        
        # Precio
        price_div = card.find("div", {"data-qa": "POSTING_CARD_PRICE"})
        if price_div:
            temp_dict['precio'] = price_div.get_text(strip=True)
        
        # Ubicación
        address_div = card.find("div", class_="postingLocations-module__location-address")
        address_txt = address_div.get_text(strip=True) if address_div else ""
        loc_h2 = card.find("h2", {"data-qa": "POSTING_CARD_LOCATION"})
        loc_txt = loc_h2.get_text(strip=True) if loc_h2 else ""
        temp_dict['ubicacion'] = f"{address_txt}, {loc_txt}" if address_txt and loc_txt else address_txt or loc_txt
        
        # Características
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

def save_data(df_page, url_info, page_num):
    """Guardar datos en archivo CSV"""
    today_str = dt.date.today().isoformat()
    
    # Crear estructura de directorios
    ciudad_clean = url_info['Ciudad'].replace('Ã¡', 'a').replace('Ã', 'n')
    producto_clean = url_info['ProductoPaginaWeb'].replace(' ', '_')
    
    out_dir = Path('data') / 'Inmuebles24' / ciudad_clean / url_info['Operacion'] / producto_clean / today_str
    out_dir.mkdir(parents=True, exist_ok=True)
    
    fname = out_dir / f"inmuebles24-{ciudad_clean}-{producto_clean}-{url_info['Operacion']}.csv"
    
    try:
        df_existing = pd.read_csv(fname)
    except FileNotFoundError:
        df_existing = pd.DataFrame()
    
    # Combinar datos existentes con nuevos
    final_df = pd.concat([df_existing, df_page], ignore_index=True)
    final_df.to_csv(fname, index=False)
    
    print(f"✓ Página {page_num}: {len(df_page)} propiedades guardadas en: {fname}")
    return len(df_page)

def test_inm24_complete():
    """Test completo de INM24 con todas las páginas del primer URL"""
    print("=== TEST LARGO INM24 - URL REAL ===")
    
    # Cambiar al directorio del proyecto
    os.chdir('/home/esdata/Documents/GitHub/Esdata_710')
    
    # Cargar URL del CSV
    url_info = load_inm24_urls()
    if not url_info:
        print("✗ No se pudo cargar URL, abortando test")
        return
    
    # Convertir a formato paginado
    base_url = url_info['URL']
    paginated_template = convert_url_to_paginated(base_url)
    print(f"✓ Plantilla de paginación: {paginated_template}")
    
    # Variables para el scraping
    page_num = 1
    max_pages = 200  # Límite máximo para evitar loops infinitos
    consecutive_empty = 0  # Contador de páginas vacías consecutivas
    max_empty = 3  # Máximo de páginas vacías consecutivas antes de parar
    total_properties = 0
    
    print(f"\n🚀 Iniciando scraping masivo de {url_info['PaginaWeb']}")
    print(f"📍 {url_info['Ciudad']} - {url_info['Operacion']} - {url_info['ProductoPaginaWeb']}")
    print(f"⏰ Inicio: {dt.datetime.now().strftime('%H:%M:%S')}")
    print("-" * 60)
    
    while page_num <= max_pages and consecutive_empty < max_empty:
        # Construir URL de la página actual
        current_url = paginated_template.format(page_num)
        
        print(f"\n[{page_num:03d}/{max_pages}] Procesando: {current_url}")
        
        driver = Driver(uc=True)
        
        try:
            # Navegar a la página
            driver.uc_open_with_reconnect(current_url, 4)
            
            # Manejar captcha de Cloudflare
            driver.uc_gui_click_captcha()
            
            # Esperar a que cargue la página
            time.sleep(5)
            
            # Obtener HTML y extraer datos
            html = driver.page_source
            df_page = scrape_page_source(html)
            
            if len(df_page) > 0:
                # Hay datos, guardar y resetear contador de páginas vacías
                properties_found = save_data(df_page, url_info, page_num)
                total_properties += properties_found
                consecutive_empty = 0
                
                print(f"    ✓ {properties_found} propiedades encontradas")
                
            else:
                # Página vacía
                consecutive_empty += 1
                print(f"    ⚠ Página vacía ({consecutive_empty}/{max_empty})")
                
                if consecutive_empty >= max_empty:
                    print(f"\n🛑 Deteniendo: {max_empty} páginas vacías consecutivas")
                    break
            
        except Exception as e:
            print(f"    ✗ Error en página {page_num}: {e}")
            consecutive_empty += 1
            
            if consecutive_empty >= max_empty:
                print(f"\n🛑 Deteniendo por errores consecutivos")
                break
        
        finally:
            driver.quit()
        
        # Incrementar contador
        page_num += 1
        
        # Pausa entre páginas para no sobrecargar el servidor
        time.sleep(2)
    
    # Resumen final
    end_time = dt.datetime.now().strftime('%H:%M:%S')
    pages_processed = page_num - 1
    
    print("\n" + "="*60)
    print("🎉 TEST COMPLETADO")
    print(f"⏰ Fin: {end_time}")
    print(f"📄 Páginas procesadas: {pages_processed}")
    print(f"🏠 Total propiedades encontradas: {total_properties}")
    print(f"📊 Promedio por página: {total_properties/pages_processed:.1f}" if pages_processed > 0 else "📊 Sin datos")
    print("="*60)

def main():
    """Función principal"""
    try:
        test_inm24_complete()
    except KeyboardInterrupt:
        print("\n\n⚠ Interrumpido por usuario")
    except Exception as e:
        print(f"\n\n✗ Error fatal: {e}")

if __name__ == "__main__":
    main()