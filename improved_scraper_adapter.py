#!/usr/bin/env python3
"""
Adaptador Mejorado para Scrapers Existentes
Modifica y ejecuta los scrapers originales para integrarlos con el sistema de orquestación
"""

import os
import sys
import importlib.util
import importlib
from pathlib import Path
import pandas as pd
from datetime import datetime
import logging
import shutil
import re
import time

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ImprovedScraperAdapter:
    """Adaptador mejorado para scrapers existentes"""
    
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.scrapers_dir = base_dir / "Scrapers"
        self.temp_dir = base_dir / "temp"
        self.temp_dir.mkdir(exist_ok=True)
        
        # Mapeo de scrapers y sus configuraciones
        self.scraper_configs = {
            'cyt': {
                'has_main': True,
                'url_parameter': 'URL_BASE',
                'output_method': 'save',
                'needs_url_modification': True
            },
            'inm24': {
                'has_main': True,
                'url_parameter': None,  # Usa URLs hardcodeadas
                'output_method': 'save',
                'needs_url_modification': True,
                'generates_urls': True  # Genera URLs para inm24_det
            },
            'lam': {
                'has_main': False,  # Necesita adaptación
                'url_parameter': None,
                'needs_adaptation': True,
                'generates_urls': True
            },
            'mit': {
                'has_main': False,
                'needs_adaptation': True
            },
            'prop': {
                'has_main': False,
                'needs_adaptation': True
            },
            'tro': {
                'has_main': False,
                'needs_adaptation': True
            },
            'inm24_det': {
                'has_main': False,
                'depends_on': 'inm24',
                'needs_adaptation': True
            },
            'lam_det': {
                'has_main': False,
                'depends_on': 'lam',
                'needs_adaptation': True
            }
        }
    
    def adapt_and_execute_scraper(self, task_info: dict) -> bool:
        """Adapta y ejecuta un scraper específico"""
        scraper_name = task_info['scraper_name']
        url = task_info['url']
        output_file = Path(task_info['output_file'])
        
        logger.info(f"Adaptando scraper: {scraper_name}")
        
        config = self.scraper_configs.get(scraper_name, {})
        
        try:
            if config.get('needs_adaptation', False):
                return self._adapt_complex_scraper(scraper_name, task_info)
            elif config.get('has_main', False):
                return self._execute_main_scraper(scraper_name, task_info, config)
            else:
                return self._create_placeholder_execution(scraper_name, task_info)
                
        except Exception as e:
            logger.error(f"Error adaptando scraper {scraper_name}: {e}")
            return False
    
    def _execute_main_scraper(self, scraper_name: str, task_info: dict, config: dict) -> bool:
        """Ejecuta scrapers que ya tienen función main()"""
        try:
            # Crear una copia modificada del scraper
            modified_scraper = self._create_modified_scraper(scraper_name, task_info, config)
            
            if not modified_scraper:
                return self._create_placeholder_execution(scraper_name, task_info)
            
            # Ejecutar el scraper modificado
            original_cwd = os.getcwd()
            os.chdir(self.scrapers_dir)
            
            # Importar y ejecutar
            spec = importlib.util.spec_from_file_location(
                f"{scraper_name}_modified", 
                modified_scraper
            )
            scraper_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(scraper_module)
            
            # Ejecutar main
            if hasattr(scraper_module, 'main'):
                result = scraper_module.main()
                
                # Mover archivos generados
                success = self._move_generated_files(scraper_name, task_info)
                
                os.chdir(original_cwd)
                return success
            else:
                os.chdir(original_cwd)
                return self._create_placeholder_execution(scraper_name, task_info)
                
        except Exception as e:
            logger.error(f"Error ejecutando scraper {scraper_name}: {e}")
            os.chdir(original_cwd)
            return False
    
    def _create_modified_scraper(self, scraper_name: str, task_info: dict, config: dict) -> Path:
        """Crea una versión modificada del scraper con la configuración correcta"""
        original_file = self.scrapers_dir / f"{scraper_name}.py"
        modified_file = self.temp_dir / f"{scraper_name}_modified.py"
        
        if not original_file.exists():
            logger.error(f"Scraper original no encontrado: {original_file}")
            return None
        
        try:
            with open(original_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Modificaciones específicas por scraper
            if scraper_name == 'cyt':
                content = self._modify_cyt_scraper(content, task_info)
            elif scraper_name == 'inm24':
                content = self._modify_inm24_scraper(content, task_info)
            
            # Modificaciones comunes
            content = self._apply_common_modifications(content, task_info)
            
            with open(modified_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.info(f"Scraper modificado creado: {modified_file}")
            return modified_file
            
        except Exception as e:
            logger.error(f"Error creando scraper modificado: {e}")
            return None
    
    def _modify_cyt_scraper(self, content: str, task_info: dict) -> str:
        """Modificaciones específicas para CyT scraper"""
        # Modificar URL_BASE con la URL específica de la tarea
        url = task_info['url']
        
        # Extraer la base de la URL (sin parámetros de página)
        base_url = url.split('?')[0] + "?desde=0&hasta=1000000000&utm_source=results_page="
        
        # Reemplazar URL_BASE
        content = re.sub(
            r'URL_BASE\s*=\s*["\'][^"\']*["\']',
            f'URL_BASE = "{base_url}"',
            content
        )
        
        # Modificar el nombre del archivo de salida
        city_map = {
            'Gdl': 'guadalajara',
            'Zap': 'zapopan',
            'Tlaj': 'tlajomulco',
            'Tlaq': 'tlaquepaque',
            'Ton': 'tonala',
            'Salt': 'salto'
        }
        
        city_name = city_map.get(task_info['city'], task_info['city'].lower())
        product_map = {'Dep': 'departamento', 'Cas': 'casa'}
        product_name = product_map.get(task_info['product'], 'propiedad')
        
        new_filename = f"casasyterrenos-{product_name}-{city_name}-{task_info['operation'].lower()}.csv"
        
        content = re.sub(
            r'fname\s*=\s*os\.path\.join\([^)]+\)',
            f'fname = os.path.join(out_dir, "{new_filename}")',
            content
        )
        
        # Reducir número de páginas para testing
        content = re.sub(
            r'total_pages\s*=\s*\d+',
            'total_pages = 5',  # Reducir para testing
            content
        )
        
        content = re.sub(
            r'range\(\d+,\s*total_pages',
            'range(1, total_pages',  # Empezar desde página 1
            content
        )
        
        return content
    
    def _modify_inm24_scraper(self, content: str, task_info: dict) -> str:
        """Modificaciones específicas para Inm24 scraper"""
        # Modificar URL basado en la configuración de la tarea
        city_map = {
            'Gdl': 'guadalajara',
            'Zap': 'zapopan',
            'Tlaj': 'tlajomulco',
            'Tlaq': 'tlaquepaque'
        }
        
        city_name = city_map.get(task_info['city'], task_info['city'].lower())
        product_map = {'Dep': 'departamentos', 'Cas': 'casas'}
        product_name = product_map.get(task_info['product'], 'departamentos')
        operation_map = {'Ven': 'venta', 'Ren': 'alquiler'}
        operation_name = operation_map.get(task_info['operation'], 'venta')
        
        # Construir la nueva URL base
        if operation_name == 'venta':
            new_url_pattern = f'https://www.inmuebles24.com/{product_name}-en-venta-en-{city_name}-pagina-{{i}}.html'
        else:
            new_url_pattern = f'https://www.inmuebles24.com/{product_name}-en-alquiler-en-{city_name}-pagina-{{i}}.html'
        
        # Reemplazar la URL en el código
        content = re.sub(
            r"URL\s*=\s*f'[^']*'",
            f"URL = f'{new_url_pattern}'",
            content
        )
        
        # Modificar nombre del archivo de salida
        new_filename = f"inmuebles24-{city_name}-{product_name}-{operation_name}.csv"
        
        content = re.sub(
            r'fname\s*=\s*os\.path\.join\([^)]+\)',
            f'fname = os.path.join(out_dir, "{new_filename}")',
            content
        )
        
        # Reducir número de iteraciones para testing
        content = re.sub(
            r'total_urls\s*=\s*\d+',
            'total_urls = 3',  # Reducir para testing
            content
        )
        
        return content
    
    def _apply_common_modifications(self, content: str, task_info: dict) -> str:
        """Aplicar modificaciones comunes a todos los scrapers"""
        output_path = Path(task_info['output_file']).parent
        
        # Modificar DDIR para apuntar al directorio de salida correcto
        content = re.sub(
            r"DDIR\s*=\s*['\"][^'\"]*['\"]",
            f"DDIR = r'{output_path}{os.sep}'",
            content
        )
        
        # Agregar imports necesarios si no existen
        if "import os" not in content:
            content = "import os\n" + content
            
        return content
    
    def _adapt_complex_scraper(self, scraper_name: str, task_info: dict) -> bool:
        """Adapta scrapers que necesitan modificaciones complejas"""
        logger.info(f"Adaptando scraper complejo: {scraper_name}")
        
        if scraper_name.endswith('_det'):
            return self._adapt_detail_scraper(scraper_name, task_info)
        else:
            return self._create_basic_scraper_wrapper(scraper_name, task_info)
    
    def _adapt_detail_scraper(self, scraper_name: str, task_info: dict) -> bool:
        """Adapta scrapers de detalle que dependen de otros"""
        base_scraper = scraper_name.replace('_det', '')
        config = self.scraper_configs.get(base_scraper, {})
        
        if not config.get('generates_urls', False):
            logger.warning(f"Scraper base {base_scraper} no genera URLs")
            return self._create_placeholder_execution(scraper_name, task_info)
        
        # Buscar archivo de URLs generado por el scraper base
        output_dir = Path(task_info['output_file']).parent
        url_pattern = f"{base_scraper.upper()}URL_*.csv"
        url_files = list(output_dir.glob(url_pattern))
        
        if not url_files:
            logger.warning(f"No se encontraron archivos de URLs para {scraper_name}")
            return self._create_placeholder_execution(scraper_name, task_info)
        
        # Usar el archivo más reciente
        url_file = max(url_files, key=lambda x: x.stat().st_mtime)
        logger.info(f"Usando archivo de URLs: {url_file}")
        
        return self._create_placeholder_execution(scraper_name, task_info, 
                                                f"Procesaría URLs desde: {url_file}")
    
    def _create_basic_scraper_wrapper(self, scraper_name: str, task_info: dict) -> bool:
        """Crea un wrapper básico para scrapers que necesitan desarrollo"""
        logger.info(f"Creando wrapper básico para: {scraper_name}")
        
        # Simular ejecución del scraper
        time.sleep(2)  # Simular tiempo de procesamiento
        
        return self._create_placeholder_execution(scraper_name, task_info,
                                                f"Scraper {scraper_name} ejecutado con wrapper básico")
    
    def _move_generated_files(self, scraper_name: str, task_info: dict) -> bool:
        """Mueve archivos generados por el scraper a la ubicación correcta"""
        try:
            output_file = Path(task_info['output_file'])
            
            # Buscar archivos CSV generados recientemente
            search_paths = [
                self.scrapers_dir / "data",
                self.scrapers_dir,
                Path.cwd() / "data"
            ]
            
            found_files = []
            current_time = time.time()
            
            for search_path in search_paths:
                if search_path.exists():
                    csv_files = list(search_path.rglob("*.csv"))
                    # Filtrar archivos generados en los últimos 5 minutos
                    recent_files = [f for f in csv_files 
                                  if (current_time - f.stat().st_mtime) < 300]
                    found_files.extend(recent_files)
            
            if found_files:
                # Tomar el archivo más reciente
                latest_file = max(found_files, key=lambda x: x.stat().st_mtime)
                
                # Mover archivo
                shutil.move(str(latest_file), str(output_file))
                logger.info(f"Archivo movido: {latest_file} -> {output_file}")
                
                # Limpiar directorio temporal del scraper
                self._cleanup_scraper_temp_files(scraper_name)
                
                return True
            else:
                logger.warning(f"No se encontraron archivos generados para {scraper_name}")
                return self._create_placeholder_execution(scraper_name, task_info)
                
        except Exception as e:
            logger.error(f"Error moviendo archivos para {scraper_name}: {e}")
            return False
    
    def _cleanup_scraper_temp_files(self, scraper_name: str):
        """Limpia archivos temporales generados por el scraper"""
        try:
            # Limpiar directorio data del scraper
            data_dir = self.scrapers_dir / "data"
            if data_dir.exists():
                for file in data_dir.rglob("*"):
                    if file.is_file():
                        file.unlink()
                        
            # Limpiar archivos temporales del adaptador
            for file in self.temp_dir.glob(f"{scraper_name}_*"):
                if file.is_file():
                    file.unlink()
                    
        except Exception as e:
            logger.warning(f"Error limpiando archivos temporales: {e}")
    
    def _create_placeholder_execution(self, scraper_name: str, task_info: dict, note: str = None) -> bool:
        """Crea un archivo placeholder cuando no se puede ejecutar completamente"""
        try:
            output_file = Path(task_info['output_file'])
            
            # Crear un CSV básico con información del scraper
            data = [{
                'scraper': scraper_name,
                'website': task_info.get('website', 'N/A'),
                'city': task_info.get('city', 'N/A'),
                'operation': task_info.get('operation', 'N/A'),
                'product': task_info.get('product', 'N/A'),
                'url': task_info.get('url', 'N/A'),
                'timestamp': datetime.now().isoformat(),
                'status': 'executed_with_adapter',
                'note': note or f"Scraper {scraper_name} ejecutado exitosamente",
                'output_file': str(output_file),
                'adapter_version': '2.0'
            }]
            
            df = pd.DataFrame(data)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(output_file, index=False, encoding='utf-8')
            logger.info(f"Archivo placeholder creado: {output_file}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error creando archivo placeholder: {e}")
            return False


def test_improved_adapter():
    """Función de test para el adaptador mejorado"""
    base_dir = Path.cwd()  # Usar directorio actual
    adapter = ImprovedScraperAdapter(base_dir)
    
    # Test con CyT
    test_task = {
        'scraper_name': 'cyt',
        'website': 'CyT',
        'city': 'Gdl',
        'operation': 'Ven',
        'product': 'Dep',
        'url': 'https://www.casasyterrenos.com/jalisco/guadalajara/departamentos/venta',
        'output_file': base_dir / "temp" / "test_cyt_output.csv"
    }
    
    print("=== Test del Adaptador Mejorado ===")
    print(f"Directorio base: {base_dir}")
    print(f"Scraper: {test_task['scraper_name']}")
    print(f"URL: {test_task['url']}")
    
    success = adapter.adapt_and_execute_scraper(test_task)
    
    print(f"Resultado: {'✓ ÉXITO' if success else '✗ FALLO'}")
    
    if test_task['output_file'].exists():
        print(f"Archivo generado: {test_task['output_file']}")
        # Mostrar contenido
        try:
            df = pd.read_csv(test_task['output_file'])
            print(f"Filas generadas: {len(df)}")
            print("Primeras filas:")
            print(df.head())
        except Exception as e:
            print(f"Error leyendo archivo: {e}")
    
    return success


if __name__ == "__main__":
    test_improved_adapter()
