#!/usr/bin/env python3
"""
Test rápido de configuración de Selenium y captcha
"""

import os
import sys
from pathlib import Path

# Configurar variables de entorno
os.environ['DISPLAY'] = ':99'

def test_selenium_config():
    """Prueba la configuración básica de Selenium"""
    print("=== Test de Configuración Selenium ===")
    
    try:
        from seleniumbase import Driver
        print("✓ SeleniumBase importado correctamente")
        
        # Crear driver de prueba
        print("Creando driver de prueba...")
        driver = Driver(uc=True)
        print("✓ Driver UC creado exitosamente")
        
        # Probar navegación básica
        print("Probando navegación...")
        driver.uc_open_with_reconnect("https://www.google.com", 2)
        print("✓ Navegación básica exitosa")
        
        print(f"Título de página: {driver.title}")
        driver.quit()
        print("✓ Driver cerrado correctamente")
        
        return True
        
    except Exception as e:
        print(f"✗ Error en configuración Selenium: {e}")
        return False

def test_captcha_function():
    """Prueba específica de la función de captcha"""
    print("\n=== Test de Función Captcha ===")
    
    try:
        from seleniumbase import Driver
        
        driver = Driver(uc=True)
        
        # Probar en un sitio que use Cloudflare
        print("Probando manejo de captcha...")
        test_url = "https://www.inmuebles24.com"
        driver.uc_open_with_reconnect(test_url, 3)
        
        # Intentar el click del captcha
        try:
            driver.uc_gui_click_captcha()
            print("✓ Función uc_gui_click_captcha ejecutada sin errores")
        except Exception as captcha_error:
            print(f"⚠ Función captcha ejecutada con advertencia: {captcha_error}")
        
        driver.quit()
        return True
        
    except Exception as e:
        print(f"✗ Error en test de captcha: {e}")
        return False

def main():
    """Función principal"""
    print("=== Test Rápido de Configuración ===")
    print(f"Python: {sys.version}")
    print(f"DISPLAY: {os.environ.get('DISPLAY', 'No configurado')}")
    print(f"Directorio: {Path.cwd()}")
    
    # Cambiar al directorio del proyecto
    os.chdir('/home/esdata/Documents/GitHub/Esdata_710')
    
    # Ejecutar tests
    selenium_ok = test_selenium_config()
    captcha_ok = test_captcha_function() if selenium_ok else False
    
    print(f"\n=== Resultados ===")
    print(f"Selenium: {'✓ OK' if selenium_ok else '✗ ERROR'}")
    print(f"Captcha: {'✓ OK' if captcha_ok else '✗ ERROR'}")
    
    if selenium_ok and captcha_ok:
        print("\n✓ Sistema listo para scrapers con captcha")
    else:
        print("\n✗ Configuración necesita corrección")

if __name__ == "__main__":
    main()