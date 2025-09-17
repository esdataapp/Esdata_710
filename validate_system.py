#!/usr/bin/env python3
"""
Script de Validación del Sistema de Orquestación
Verifica que todos los componentes estén configurados correctamente
"""

import os
import sys
from pathlib import Path
import pandas as pd
import yaml
import sqlite3
import importlib.util
import subprocess
from datetime import datetime
import logging
from typing import Optional

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SystemValidator:
    """Validador del sistema de orquestación"""
    def __init__(self, base_dir: Optional[Path] = None):
        if base_dir is None:
            base_dir = Path.cwd()  # Usar directorio actual
        
        self.base_dir = base_dir
        self.config_path = base_dir / "config" / "config.yaml"
        self.validation_results = []
        self.validation_results = []
        
    def validate_all(self) -> bool:
        """Ejecuta todas las validaciones"""
        print("=" * 60)
        print("      VALIDACIÓN DEL SISTEMA DE ORQUESTACIÓN")
        print("=" * 60)
        print()
        
        validations = [
            ("Estructura de directorios", self.validate_directory_structure),
            ("Archivo de configuración", self.validate_configuration),
            ("Dependencias de Python", self.validate_python_dependencies),
            ("Archivos de scrapers", self.validate_scrapers),
            ("Archivos de URLs", self.validate_url_files),
            ("Base de datos", self.validate_database),
            ("Permisos de archivos", self.validate_file_permissions),
            ("Funcionalidad básica", self.validate_basic_functionality)
        ]
        
        all_passed = True
        
        for name, validation_func in validations:
            print(f"🔍 Validando: {name}")
            try:
                result = validation_func()
                if result:
                    print(f"   ✅ {name}: PASS")
                else:
                    print(f"   ❌ {name}: FAIL")
                    all_passed = False
            except Exception as e:
                print(f"   ❌ {name}: ERROR - {e}")
                all_passed = False
            print()
        
        print("=" * 60)
        if all_passed:
            print("🎉 VALIDACIÓN COMPLETADA: Todos los componentes están correctos")
        else:
            print("⚠️  VALIDACIÓN COMPLETADA: Se encontraron problemas")
        print("=" * 60)
        
        return all_passed
    
    def validate_directory_structure(self) -> bool:
        """Valida la estructura de directorios"""
        required_dirs = [
            "Scrapers",
            "config",
            "urls",
            "data",
            "logs",
            "temp",
            "backups"
        ]
        
        missing_dirs = []
        for dir_name in required_dirs:
            dir_path = self.base_dir / dir_name
            if not dir_path.exists():
                missing_dirs.append(dir_name)
                # Crear directorio faltante
                dir_path.mkdir(parents=True, exist_ok=True)
                print(f"   📁 Creado directorio: {dir_name}")
        
        if missing_dirs:
            print(f"   ⚠️  Directorios creados: {', '.join(missing_dirs)}")
        
        return True
    
    def validate_configuration(self) -> bool:
        """Valida el archivo de configuración"""
        if not self.config_path.exists():
            print(f"   ❌ Archivo de configuración no encontrado: {self.config_path}")
            return False
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            required_sections = [
                'database', 'data', 'scrapers', 'execution', 
                'websites', 'cities', 'operations', 'products'
            ]
            
            missing_sections = [section for section in required_sections 
                              if section not in config]
            
            if missing_sections:
                print(f"   ❌ Secciones faltantes en configuración: {missing_sections}")
                return False
            
            # Validar configuración de websites
            websites = config.get('websites', {})
            expected_websites = ['Inm24', 'CyT', 'Lam', 'Mit', 'Prop', 'Tro']
            
            missing_websites = [ws for ws in expected_websites if ws not in websites]
            if missing_websites:
                print(f"   ⚠️  Websites faltantes en configuración: {missing_websites}")
            
            print(f"   ℹ️  Configuración cargada correctamente")
            print(f"   ℹ️  Websites configurados: {len(websites)}")
            print(f"   ℹ️  Ciudades configuradas: {len(config.get('cities', []))}")
            
            return True
            
        except Exception as e:
            print(f"   ❌ Error cargando configuración: {e}")
            return False
    
    def validate_python_dependencies(self) -> bool:
        """Valida las dependencias de Python"""
        required_packages = [
            'pandas', 'yaml', 'bs4', 'selenium', 
            'seleniumbase', 'requests', 'lxml', 'tabulate'
        ]
        
        missing_packages = []
        
        for package in required_packages:
            try:
                __import__(package.replace('-', '_'))
            except ImportError:
                missing_packages.append(package)
        
        if missing_packages:
            print(f"   ❌ Paquetes faltantes: {', '.join(missing_packages)}")
            print(f"   💡 Ejecuta: pip install {' '.join(missing_packages)}")
            return False
        
        print(f"   ✅ Todas las dependencias están instaladas")
        return True
    
    def validate_scrapers(self) -> bool:
        """Valida los archivos de scrapers"""
        scrapers_dir = self.base_dir / "Scrapers"
        
        if not scrapers_dir.exists():
            print(f"   ❌ Directorio de scrapers no encontrado: {scrapers_dir}")
            return False
        
        expected_scrapers = [
            'cyt.py', 'inm24.py', 'inm24_det.py', 
            'lam.py', 'lam_det.py', 'mit.py', 'prop.py', 'tro.py'
        ]
        
        found_scrapers = []
        missing_scrapers = []
        
        for scraper in expected_scrapers:
            scraper_path = scrapers_dir / scraper
            if scraper_path.exists():
                found_scrapers.append(scraper)
                # Validar que el archivo no esté vacío
                if scraper_path.stat().st_size == 0:
                    print(f"   ⚠️  Scraper vacío: {scraper}")
            else:
                missing_scrapers.append(scraper)
        
        print(f"   ℹ️  Scrapers encontrados: {len(found_scrapers)}")
        print(f"   ℹ️  Lista: {', '.join(found_scrapers)}")
        
        if missing_scrapers:
            print(f"   ⚠️  Scrapers faltantes: {', '.join(missing_scrapers)}")
        
        # Validar que al menos los scrapers principales existan
        critical_scrapers = ['cyt.py', 'inm24.py']
        missing_critical = [s for s in critical_scrapers if s in missing_scrapers]
        
        if missing_critical:
            print(f"   ❌ Scrapers críticos faltantes: {missing_critical}")
            return False
        
        return True
    
    def validate_url_files(self) -> bool:
        """Valida los archivos de URLs"""
        urls_dir = self.base_dir / "urls"
        
        if not urls_dir.exists():
            print(f"   ❌ Directorio de URLs no encontrado: {urls_dir}")
            return False
        
        expected_url_files = [
            'cyt_urls.csv', 'inm24_urls.csv', 'lam_urls.csv',
            'mit_urls.csv', 'prop_urls.csv', 'tro_urls.csv'
        ]
        
        found_files = []
        missing_files = []
        invalid_files = []
        
        for url_file in expected_url_files:
            file_path = urls_dir / url_file
            if file_path.exists():
                found_files.append(url_file)
                
                # Validar estructura del CSV
                try:
                    df = pd.read_csv(file_path)
                    required_columns = ['PaginaWeb', 'Ciudad', 'Operacion', 'ProductoPaginaWeb', 'URL']
                    
                    missing_columns = [col for col in required_columns if col not in df.columns]
                    if missing_columns:
                        print(f"   ⚠️  {url_file}: Columnas faltantes: {missing_columns}")
                        invalid_files.append(url_file)
                    elif len(df) == 0:
                        print(f"   ⚠️  {url_file}: Archivo vacío")
                        invalid_files.append(url_file)
                    else:
                        print(f"   ✅ {url_file}: {len(df)} URLs válidas")
                        
                except Exception as e:
                    print(f"   ❌ {url_file}: Error leyendo archivo - {e}")
                    invalid_files.append(url_file)
            else:
                missing_files.append(url_file)
        
        if missing_files:
            print(f"   ⚠️  Archivos de URLs faltantes: {', '.join(missing_files)}")
        
        if invalid_files:
            print(f"   ❌ Archivos de URLs inválidos: {', '.join(invalid_files)}")
            return False
        
        return len(found_files) > 0
    
    def validate_database(self) -> bool:
        """Valida la configuración de la base de datos"""
        try:
            # Cargar configuración para obtener path de DB
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            db_path = Path(config['database']['path'])
            
            # Si la DB no existe, intentar crearla ejecutando el orchestrator
            if not db_path.exists():
                print(f"   ℹ️  Base de datos no existe, será creada en primera ejecución")
                return True
            
            # Validar estructura de la DB
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Verificar tablas
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            
            required_tables = ['scraping_tasks', 'execution_batches']
            missing_tables = [table for table in required_tables if table not in tables]
            
            if missing_tables:
                print(f"   ⚠️  Tablas faltantes en DB: {missing_tables}")
            else:
                print(f"   ✅ Base de datos con estructura correcta")
            
            # Obtener estadísticas básicas
            cursor.execute("SELECT COUNT(*) FROM scraping_tasks")
            task_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM execution_batches")
            batch_count = cursor.fetchone()[0]
            
            print(f"   ℹ️  Tareas en DB: {task_count}")
            print(f"   ℹ️  Lotes en DB: {batch_count}")
            
            conn.close()
            return True
            
        except Exception as e:
            print(f"   ⚠️  Error validando base de datos: {e}")
            return True  # No es crítico si la DB no existe aún
    
    def validate_file_permissions(self) -> bool:
        """Valida permisos de archivos y directorios"""
        try:
            # Verificar que se puede escribir en directorios importantes
            test_dirs = ['data', 'logs', 'temp', 'backups']
            
            for test_dir in test_dirs:
                dir_path = self.base_dir / test_dir
                if dir_path.exists():
                    # Intentar crear un archivo de prueba
                    test_file = dir_path / "permission_test.tmp"
                    try:
                        test_file.write_text("test")
                        test_file.unlink()  # Eliminar archivo de prueba
                    except Exception as e:
                        print(f"   ❌ Sin permisos de escritura en {test_dir}: {e}")
                        return False
            
            print(f"   ✅ Permisos de escritura correctos")
            return True
            
        except Exception as e:
            print(f"   ⚠️  Error validando permisos: {e}")
            return True
    
    def validate_basic_functionality(self) -> bool:
        """Valida funcionalidad básica del sistema"""
        try:
            # Intentar importar el orchestrator
            orchestrator_path = self.base_dir / "orchestrator.py"
            if not orchestrator_path.exists():
                print(f"   ❌ orchestrator.py no encontrado")
                return False
            
            # Cambiar al directorio del proyecto para imports
            original_cwd = os.getcwd()
            os.chdir(self.base_dir)
            
            # Agregar el directorio al path de Python
            if str(self.base_dir) not in sys.path:
                sys.path.insert(0, str(self.base_dir))
            
            try:
                # Importar módulos principales
                spec = importlib.util.spec_from_file_location("orchestrator", orchestrator_path)
                if spec is None or spec.loader is None:
                    print(f"   ❌ No se pudo cargar orchestrator.py")
                    return False
                orchestrator_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(orchestrator_module)
                
                print(f"   ✅ Orchestrator se puede importar correctamente")
                
                # Intentar crear instancia del orchestrator (detección dinámica de clase)
                orchestrator_cls = None
                for candidate in ["LinuxScrapingOrchestrator", "WindowsScrapingOrchestrator", "ScrapingOrchestrator"]:
                    if hasattr(orchestrator_module, candidate):
                        orchestrator_cls = getattr(orchestrator_module, candidate)
                        break
                if orchestrator_cls is None:
                    print("   ❌ No se encontró clase de orquestador reconocida en orchestrator.py")
                    os.chdir(original_cwd)
                    return False
                orchestrator = orchestrator_cls()
                print(f"   ✅ Orchestrator ({orchestrator_cls.__name__}) se puede instanciar")

                # Verificar configuración
                if hasattr(orchestrator, 'config') and orchestrator.config:
                    print(f"   ✅ Configuración cargada en orchestrator")
                # Verificar columnas de contadores en la base de datos
                try:
                    if hasattr(orchestrator, 'db_path') and orchestrator.db_path.exists():
                        conn = sqlite3.connect(orchestrator.db_path)
                        cur = conn.execute("PRAGMA table_info(execution_batches)")
                        cols = [r[1] for r in cur.fetchall()]
                        for needed in ["completed_tasks", "failed_tasks"]:
                            if needed not in cols:
                                print(f"   ⚠️ Columna '{needed}' ausente en execution_batches (revisar migración)")
                        conn.close()
                except Exception as ie:
                    print(f"   ⚠️ No se pudo verificar columnas de batch: {ie}")
                
                os.chdir(original_cwd)
                return True
                
            except Exception as e:
                print(f"   ❌ Error importando orchestrator: {e}")
                os.chdir(original_cwd)
                return False
                
        except Exception as e:
            print(f"   ❌ Error en validación de funcionalidad: {e}")
            return False
    
    def generate_report(self) -> str:
        """Genera un reporte de validación"""
        report = []
        report.append("=" * 60)
        report.append("    REPORTE DE VALIDACIÓN DEL SISTEMA")
        report.append("=" * 60)
        report.append(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Directorio base: {self.base_dir}")
        report.append("")
        
        # Información del sistema
        report.append("INFORMACIÓN DEL SISTEMA:")
        report.append(f"  Python: {sys.version}")
        report.append(f"  SO: {os.name}")
        report.append("")
        
        # Información del proyecto
        if self.config_path.exists():
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            report.append("CONFIGURACIÓN DEL PROYECTO:")
            report.append(f"  Websites configurados: {len(config.get('websites', {}))}")
            report.append(f"  Ciudades configuradas: {len(config.get('cities', []))}")
            report.append(f"  Max scrapers paralelos: {config.get('execution', {}).get('max_parallel_scrapers', 'N/A')}")
            report.append("")
        
        # Archivos del proyecto
        scrapers_dir = self.base_dir / "Scrapers"
        if scrapers_dir.exists():
            scrapers = list(scrapers_dir.glob("*.py"))
            report.append(f"SCRAPERS ENCONTRADOS ({len(scrapers)}):")
            for scraper in scrapers:
                size_kb = scraper.stat().st_size / 1024
                report.append(f"  • {scraper.name} ({size_kb:.1f} KB)")
            report.append("")
        
        urls_dir = self.base_dir / "urls"
        if urls_dir.exists():
            url_files = list(urls_dir.glob("*.csv"))
            report.append(f"ARCHIVOS DE URLS ({len(url_files)}):")
            for url_file in url_files:
                try:
                    df = pd.read_csv(url_file)
                    report.append(f"  • {url_file.name}: {len(df)} URLs")
                except:
                    report.append(f"  • {url_file.name}: Error leyendo")
            report.append("")
        
        report.append("=" * 60)
        
        return "\\n".join(report)


def main():
    """Función principal de validación"""
    base_dir = Path.cwd()  # Usar directorio actual
    
    if not base_dir.exists():
        print(f"❌ Directorio del proyecto no encontrado: {base_dir}")
        return False
    
    validator = SystemValidator(base_dir)
    result = validator.validate_all()
    
    # Generar reporte
    report = validator.generate_report()
    
    # Guardar reporte
    report_file = base_dir / "validation_report.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\\n📄 Reporte guardado en: {report_file}")
    
    if result:
        print("\\n🚀 El sistema está listo para usar!")
        print("   Ejecuta: python orchestrator.py run")
    else:
        print("\\n🔧 Por favor corrige los problemas encontrados antes de continuar.")
    
    return result


if __name__ == "__main__":
    main()
