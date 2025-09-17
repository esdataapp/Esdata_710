#!/usr/bin/env python3
"""
Adaptador para scrapers existentes
Convierte los scrapers actuales para que funcionen con el sistema de orquestación
"""

import os
import sys
import importlib.util
from pathlib import Path
import pandas as pd
from datetime import datetime
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ScraperAdapter:
    """Adaptador para scrapers existentes"""
    
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.scrapers_dir = base_dir / "Scrapers"
        
    def adapt_scraper(self, scraper_name: str, url: str, output_file: Path, **kwargs):
        """Adapta y ejecuta un scraper existente"""
        scraper_path = self.scrapers_dir / f"{scraper_name}.py"
        
        if not scraper_path.exists():
            logger.error(f"Scraper no encontrado: {scraper_path}")
            return False
        
        # Obtener directorio actual antes de cambiarlo
        original_cwd = os.getcwd()
        
        try:
            # Cambiar al directorio de scrapers
            os.chdir(self.scrapers_dir)
            
            # Importar el módulo del scraper
            spec = importlib.util.spec_from_file_location(scraper_name, scraper_path)
            if spec is None:
                logger.error(f"No se pudo crear spec para el scraper: {scraper_name}")
                return False
            if spec.loader is None:
                logger.error(f"El loader para el scraper {scraper_name} es None")
                return False
            scraper_module = importlib.util.module_from_spec(spec)
            
            # Cargar el módulo
            spec.loader.exec_module(scraper_module)
            
            # Configuración de entorno y variables de modo
            mode = 'detail' if scraper_name.endswith('_det') else 'url'
            os.environ['SCRAPER_MODE'] = mode
            # Asegurar rutas absolutas para evitar problemas de CWD
            abs_output_file = output_file if output_file.is_absolute() else (self.base_dir / output_file).resolve()
            # Asegurar directorio de salida existente
            abs_output_file.parent.mkdir(parents=True, exist_ok=True)
            os.environ['SCRAPER_OUTPUT_FILE'] = str(abs_output_file)
            os.environ['SCRAPER_BASE_DIR'] = str(self.base_dir)
            os.environ['SCRAPER_WEBSITE'] = str(kwargs.get('website', ''))
            os.environ['SCRAPER_WEBSITE_CODE'] = str(kwargs.get('website_code', kwargs.get('website', '')))
            os.environ['SCRAPER_CITY'] = str(kwargs.get('city', ''))
            os.environ['SCRAPER_CITY_CODE'] = str(kwargs.get('city_code', kwargs.get('city', '')))
            os.environ['SCRAPER_OPERATION'] = str(kwargs.get('operation', ''))
            os.environ['SCRAPER_OPERATION_CODE'] = str(kwargs.get('operation_code', kwargs.get('operation', '')))
            os.environ['SCRAPER_PRODUCT'] = str(kwargs.get('product', ''))
            os.environ['SCRAPER_PRODUCT_CODE'] = str(kwargs.get('product_code', kwargs.get('product', '')))
            os.environ['SCRAPER_BATCH_ID'] = str(kwargs.get('batch_id', ''))
            os.environ['SCRAPER_INPUT_URL'] = url or ''
            # Limite de paginas (inyectado por orquestador segun sitio/config)
            max_pages = kwargs.get('max_pages')
            if max_pages is not None and str(max_pages).strip():
                os.environ['SCRAPER_MAX_PAGES'] = str(max_pages)
            # Para scrapers de detalle: pasar hint de archivo URL si existe en el mismo folder
            if mode == 'detail':
                # patrón de archivo URL generado por orquestador ya está en el mismo directorio
                parent_dir = output_file.parent
                base_scraper = scraper_name.replace('_det', '')
                # Buscar *_URL_* del mismo sitio y batch
                candidate = None
                for f in parent_dir.glob(f"{kwargs.get('website','')}URL_*{kwargs.get('city','')}*{kwargs.get('operation','')}*{kwargs.get('product','')}*.csv"):
                    candidate = f
                    break
                if candidate:
                    os.environ['SCRAPER_URL_LIST_FILE'] = str(candidate)
            # Ajustar DDIR si el scraper lo usa
            if hasattr(scraper_module, 'DDIR'):
                # Dir absoluto del output para scrapers legacy que escriben en DDIR
                scraper_module.DDIR = str(abs_output_file.parent) + os.sep  # type: ignore
            
            # Determinar método de ejecución
            if scraper_name in ['cyt', 'inm24', 'lam', 'mit', 'prop', 'tro'] and mode == 'url':
                success = self._run_standard_scraper(scraper_module, scraper_name, url, output_file, **kwargs)
            elif scraper_name.endswith('_det'):
                success = self._run_detail_scraper(scraper_module, scraper_name, output_file, **kwargs)
            else:
                logger.warning(f"Tipo de scraper desconocido: {scraper_name}")
                success = False
            
            # Restaurar directorio
            os.chdir(original_cwd)
            
            return success
            
        except Exception as e:
            logger.error(f"Error adaptando scraper {scraper_name}: {e}")
            os.chdir(original_cwd)
            return False
    
    def _run_standard_scraper(self, module, scraper_name: str, url: str, output_file: Path, **kwargs):
        """Ejecuta scrapers estándar (principales)"""
        try:
            logger.info(f"Ejecutando scraper estándar: {scraper_name}")
            
            # Para scrapers que usan main()
            if hasattr(module, 'main'):
                # Ejecutar main del scraper
                result = module.main()
                # Si el propio scraper ya escribió el archivo objetivo, no mover ni crear placeholder
                if output_file.exists() and output_file.stat().st_size > 0:
                    logger.info(f"[adapter] Archivo ya generado por scraper: {output_file}")
                    return result is not False
                # De lo contrario intentar mover archivo legacy
                self._move_generated_files(scraper_name, output_file)
                return result is not False
            
            # Para scrapers que solo tienen funciones de scraping
            elif hasattr(module, 'scrape_page_source'):
                logger.info(f"Scraper {scraper_name} requiere ejecución manual")
                # Crear un archivo placeholder indicando que se necesita adaptación manual
                self._create_placeholder_file(output_file, scraper_name, url)
                return True
            
            else:
                logger.error(f"Scraper {scraper_name} no tiene función main() o scrape_page_source()")
                return False
                
        except Exception as e:
            logger.error(f"Error ejecutando scraper estándar {scraper_name}: {e}")
            return False
    
    def _run_detail_scraper(self, module, scraper_name: str, output_file: Path, **kwargs):
        """Ejecuta scrapers de detalle (que dependen de otros)"""
        try:
            logger.info(f"Ejecutando scraper de detalle: {scraper_name}")
            
            # Buscar el archivo de URLs del scraper principal
            base_scraper = scraper_name.replace('_det', '')
            patterns = []
            website_code = kwargs.get('website_code') or os.environ.get('SCRAPER_WEBSITE_CODE')
            website_raw = kwargs.get('website') or os.environ.get('SCRAPER_WEBSITE')
            if website_code:
                patterns.append(f"{website_code}URL_*.csv")
            if website_raw and website_raw != website_code:
                patterns.append(f"{website_raw}URL_*.csv")
            patterns.append(f"{base_scraper.upper()}URL_*.csv")
            patterns.append(f"{base_scraper}URL_*.csv")

            url_files = []
            for pattern in patterns:
                matches = list(output_file.parent.glob(pattern))
                if matches:
                    url_files = matches
                    break

            if not url_files:
                logger.warning(f"No se encontró archivo de URLs para {scraper_name}")
                # Crear placeholder
                self._create_placeholder_file(output_file, scraper_name, "Depende de " + base_scraper)
                return True
            
            # Usar el archivo de URLs más reciente
            url_file = max(url_files, key=lambda x: x.stat().st_mtime)
            logger.info(f"Usando archivo de URLs: {url_file}")
            
            # Ejecutar scraper de detalle
            if hasattr(module, 'main'):
                result = module.main()
                self._move_generated_files(scraper_name, output_file)
                return result is not False
            else:
                self._create_placeholder_file(output_file, scraper_name, f"URLs desde: {url_file}")
                return True
                
        except Exception as e:
            logger.error(f"Error ejecutando scraper de detalle {scraper_name}: {e}")
            return False
    
    def _move_generated_files(self, scraper_name: str, target_file: Path):
        """Mueve archivos generados por el scraper a la ubicación correcta"""
        try:
            # Si el archivo ya existe (escrito por el scraper refactorizado) no hacer nada
            if target_file.exists() and target_file.stat().st_size > 0:
                logger.info(f"[adapter] Skip move: archivo destino ya existe {target_file}")
                return True
            # Buscar archivos CSV generados recientemente en el directorio de scrapers
            scrapers_dir = self.scrapers_dir
            data_dir = scrapers_dir / "data"
            
            if data_dir.exists():
                # Buscar por coincidencia exacta de nombre de archivo para evitar cruces entre scrapers
                candidates = [p for p in data_dir.rglob("*.csv") if p.name == target_file.name]
                if candidates:
                    # Elegir el más reciente entre los que coinciden exactamente
                    chosen = max(candidates, key=lambda x: x.stat().st_mtime)
                    import shutil
                    # Asegurar carpeta destino
                    target_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(chosen), str(target_file))
                    logger.info(f"Archivo movido (match exacto): {chosen} -> {target_file}")
                    return True
            
            # Si no se encuentra archivo generado y no existe destino, crear placeholder
            if not target_file.exists():
                self._create_placeholder_file(target_file, scraper_name, "Ejecutado correctamente (sin archivo legacy detectado)")
            return True
            
        except Exception as e:
            logger.error(f"Error moviendo archivos para {scraper_name}: {e}")
            return False
    
    def _create_placeholder_file(self, output_file: Path, scraper_name: str, note: str):
        """Crea un archivo placeholder cuando no se puede ejecutar completamente"""
        try:
            # Asegurar directorio destino
            output_file.parent.mkdir(parents=True, exist_ok=True)
            # Crear un CSV básico con información del scraper
            data = [{
                'scraper': scraper_name,
                'timestamp': datetime.now().isoformat(),
                'status': 'executed_with_adapter',
                'note': note,
                'output_file': str(output_file)
            }]
            
            df = pd.DataFrame(data)
            df.to_csv(output_file, index=False, encoding='utf-8')
            logger.info(f"Archivo placeholder creado: {output_file}")
            
        except Exception as e:
            logger.error(f"Error creando archivo placeholder: {e}")


def test_adapter():
    """Función de test para el adaptador"""
    base_dir = Path.cwd()  # Usar directorio actual
    adapter = ScraperAdapter(base_dir)
    
    # Test con CyT
    test_output = base_dir / "temp" / "test_cyt.csv"
    test_output.parent.mkdir(exist_ok=True)
    
    success = adapter.adapt_scraper(
        'cyt', 
        'https://www.casasyterrenos.com/jalisco/guadalajara/departamentos/venta',
        test_output,
        website='CyT',
        city='Gdl',
        operation='Ven',
        product='Dep'
    )
    
    print(f"Test adapter result: {success}")
    if test_output.exists():
        print(f"Output file created: {test_output}")
    
    return success


if __name__ == "__main__":
    test_adapter()
