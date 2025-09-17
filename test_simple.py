#!/usr/bin/env python3
"""
Prueba simple del sistema - versión Ubuntu
"""

import os
import sys
from pathlib import Path
import subprocess

# Configurar variables de entorno
os.environ['DISPLAY'] = ':99'

def test_single_scraper():
    """Prueba un solo scraper con captcha"""
    print("=== Prueba Individual de Scraper con Captcha ===")
    
    # Probar inm24 directamente (necesita captcha)
    scraper_path = Path("Scrapers/inm24.py")
    
    if scraper_path.exists():
        print(f"Ejecutando: {scraper_path}")
        try:
            # Ejecutar solo 1 iteración para prueba rápida
            result = subprocess.run([
                sys.executable, "-c", 
                "import sys; sys.path.append('Scrapers'); "
                "exec(open('Scrapers/inm24.py').read().replace('total_urls = 200', 'total_urls = 1'))"
            ], capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                print("✓ Scraper ejecutado exitosamente")
                print(f"Output: {result.stdout[:300]}...")
                if result.stderr:
                    print(f"Stderr: {result.stderr[:200]}...")
            else:
                print(f"✗ Error en scraper (código {result.returncode})")
                print(f"Output: {result.stdout[:300]}...")
                print(f"Error: {result.stderr[:300]}...")
                
        except subprocess.TimeoutExpired:
            print("✗ Timeout - scraper demoró más de 1 minuto")
        except Exception as e:
            print(f"✗ Error ejecutando scraper: {e}")
    else:
        print(f"✗ Scraper no encontrado: {scraper_path}")

def test_adapter():
    """Prueba el adaptador mejorado"""
    print("\n=== Prueba Adaptador Mejorado ===")
    
    try:
        from improved_scraper_adapter import ImprovedScraperAdapter
        
        # Crear instancia del adaptador
        adapter = ImprovedScraperAdapter(Path('/home/esdata/Documents/GitHub/Esdata_710'))
        
        # Probar con una tarea de ejemplo
        test_task = {
            'scraper_name': 'inm24',
            'website': 'Inm24',
            'city': 'Gdl',
            'operation': 'Ven',
            'product': 'Dep',
            'url': 'https://inmuebles24.com/departamentos-en-venta-en-guadalajara-pagina-1.html',
            'order_num': 1
        }
        
        print("Ejecutando adaptador con tarea de prueba...")
        result = adapter.adapt_and_execute_scraper(test_task)
        print(f"Resultado: {result}")
        
    except Exception as e:
        print(f"✗ Error en adaptador: {e}")

def main():
    """Función principal"""
    print("=== Sistema de Pruebas - Ubuntu 24.04 ===")
    print(f"Python: {sys.version}")
    print(f"DISPLAY: {os.environ.get('DISPLAY', 'No configurado')}")
    print(f"Directorio: {Path.cwd()}")
    
    # Cambiar al directorio del proyecto
    os.chdir('/home/esdata/Documents/GitHub/Esdata_710')
    
    # Ejecutar pruebas
    test_single_scraper()
    test_adapter()
    
    print("\n=== Pruebas Completadas ===")

if __name__ == "__main__":
    main()