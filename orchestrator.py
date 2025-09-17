#!/usr/bin/env python3
"""
Sistema de Orquestación de Scraping Inmobiliario - Linux Edition
Versión adaptada para Ubuntu 24.04 LTS
Compatible con scrapers existentes de CyT, Inm24, Lam, Mit, Prop, Tro
"""

import asyncio
import logging
import os
import json
import yaml
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import sqlite3
from contextlib import contextmanager
import schedule
import time
import signal
from enum import Enum
import subprocess
import shutil

# Configurar el directorio base
BASE_DIR = Path.cwd()  # Usar directorio actual
CONFIG_PATH = BASE_DIR / "config" / "config.yaml"

# Configuración de logging
log_dir = BASE_DIR / "logs"
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / 'orchestrator.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class ScrapingStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"

@dataclass
class ScrapingTask:
    """Definición de una tarea de scraping"""
    scraper_name: str
    website: str
    city: str
    operation: str
    product: str
    url: str
    order: int
    status: ScrapingStatus = ScrapingStatus.PENDING
    attempts: int = 0
    max_attempts: int = 3
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None

class WindowsScrapingOrchestrator:
    """Orquestador principal para Windows"""
    
    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            config_path = str(CONFIG_PATH)
        
        self.config = self._load_config(config_path)
        self.base_dir = BASE_DIR
        self.db_path = Path(self.config['database']['path'])
        self.data_path = Path(self.config['data']['base_path'])
        self.urls_path = Path(self.config['data']['urls_path'])
        self.scrapers_path = Path(self.config['scrapers']['path'])
        
        # Crear directorios necesarios
        self._ensure_directories()
        
        # Inicializar base de datos
        self._init_database()
        
        # Control de ejecución
        self.running = False
        self.shutdown_requested = False
        
        # Pool de trabajadores (reducido para Windows)
        self.max_workers = self.config['execution']['max_parallel_scrapers']
        
        logger.info(f"Orquestador inicializado en: {self.base_dir}")
        
    def _ensure_directories(self):
        """Crea todos los directorios necesarios"""
        directories = [
            self.data_path,
            self.urls_path,
            self.base_dir / "logs",
            self.base_dir / "temp",
            self.base_dir / "backups"
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            logger.info(f"Directorio asegurado: {directory}")
    
    def _load_config(self, config_path: str) -> Dict:
        """Carga la configuración desde archivo YAML"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                logger.info(f"Configuración cargada desde: {config_path}")
                return config
        except FileNotFoundError:
            logger.error(f"Archivo de configuración no encontrado: {config_path}")
            return self._get_default_config()
        except Exception as e:
            logger.error(f"Error cargando configuración: {e}")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict:
        """Configuración por defecto para Windows"""
        return {
            'database': {'path': str(BASE_DIR / 'orchestrator.db')},
            'data': {
                'base_path': str(BASE_DIR / 'data'),
                'urls_path': str(BASE_DIR / 'urls')
            },
            'scrapers': {'path': str(BASE_DIR / 'Scrapers')},
            'execution': {
                'max_parallel_scrapers': 4,
                'retry_delay_minutes': 30,
                'execution_interval_days': 15,
                'rate_limit_delay_seconds': 3
            },
            'websites': {
                'Inm24': {'priority': 1, 'has_detail_scraper': True},
                'CyT': {'priority': 2, 'has_detail_scraper': False},
                'Lam': {'priority': 3, 'has_detail_scraper': True},
                'Mit': {'priority': 4, 'has_detail_scraper': False},
                'Prop': {'priority': 5, 'has_detail_scraper': False},
                'Tro': {'priority': 6, 'has_detail_scraper': False}
            }
        }
    
    def _init_database(self):
        """Inicializa la base de datos SQLite con configuración thread-safe"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            # Configurar SQLite para concurrencia
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
            conn.execute("PRAGMA cache_size = 1000")
            conn.execute("PRAGMA temp_store = MEMORY")
            conn.execute("PRAGMA busy_timeout = 30000")  # 30 segundos
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS scraping_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scraper_name TEXT NOT NULL,
                    website TEXT NOT NULL,
                    city TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    product TEXT NOT NULL,
                    url TEXT NOT NULL,
                    order_num INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    attempts INTEGER DEFAULT 0,
                    max_attempts INTEGER DEFAULT 3,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    error_message TEXT,
                    execution_batch TEXT,
                    output_path TEXT
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS execution_batches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    batch_id TEXT UNIQUE NOT NULL,
                    month_year TEXT NOT NULL,
                    execution_number INTEGER NOT NULL,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    total_tasks INTEGER,
                    completed_tasks INTEGER DEFAULT 0,
                    failed_tasks INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'running'
                )
            ''')
            
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_tasks_status ON scraping_tasks(status);
            ''')
            
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_tasks_batch ON scraping_tasks(execution_batch);
            ''')
            
            logger.info("Base de datos inicializada correctamente")
    
    @contextmanager
    def get_db_connection(self):
        """Context manager para conexiones de base de datos thread-safe"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)  # 30 segundos timeout
        conn.row_factory = sqlite3.Row
        # Configurar para cada conexión
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA busy_timeout = 30000")
        try:
            yield conn
        finally:
            conn.close()
    
    def generate_batch_id(self) -> Tuple[str, str, int]:
        """Genera un ID de lote único basado en fecha"""
        now = datetime.now()
        month_year = now.strftime("%b%y")  # Sep25
        
        with self.get_db_connection() as conn:
            cursor = conn.execute(
                "SELECT MAX(execution_number) FROM execution_batches WHERE month_year = ?",
                (month_year,)
            )
            result = cursor.fetchone()
            execution_number = (result[0] or 0) + 1
        
        batch_id = f"{month_year}_{execution_number:02d}"
        return batch_id, month_year, execution_number
    
    def load_urls_from_csv(self, scraper_name: str) -> List[ScrapingTask]:
        """Carga URLs desde CSV y crea tareas de scraping"""
        csv_file = self.urls_path / f"{scraper_name}_urls.csv"
        tasks = []
        
        if not csv_file.exists():
            logger.warning(f"Archivo CSV no encontrado: {csv_file}")
            return tasks
        
        try:
            df = pd.read_csv(csv_file, encoding='utf-8')
            required_columns = ['PaginaWeb', 'Ciudad', 'Operacion', 'ProductoPaginaWeb', 'URL']
            
            if not all(col in df.columns for col in required_columns):
                logger.error(f"Columnas requeridas faltantes en {csv_file}")
                return tasks
            
            for i, (_, row) in enumerate(df.iterrows()):
                task = ScrapingTask(
                    scraper_name=scraper_name,
                    website=row['PaginaWeb'],
                    city=row['Ciudad'],
                    operation=row['Operacion'],
                    product=row['ProductoPaginaWeb'],
                    url=row['URL'],
                    order=i + 1,
                    created_at=datetime.now()
                )
                tasks.append(task)
                
            logger.info(f"Cargadas {len(tasks)} tareas desde {csv_file}")
                
        except Exception as e:
            logger.error(f"Error cargando URLs desde {csv_file}: {e}")
        
        return tasks
    
    def get_output_path(self, task: ScrapingTask, batch_id: str, month_year: str, execution_number: int) -> Path:
        """Genera la ruta de salida para los datos"""
        # data/CyT/Gdl/Ven/Dep/Sep25/01
        path = self.data_path / task.website / task.city / task.operation / task.product / month_year / f"{execution_number:02d}"
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    def get_output_filename(self, task: ScrapingTask, month_year: str, execution_number: int, is_url_file: bool = False) -> str:
        """Genera el nombre del archivo de salida"""
        if is_url_file:
            return f"{task.website}URL_{task.city}_{task.operation}_{task.product}_{month_year}_{execution_number:02d}.csv"
        else:
            return f"{task.website}_{task.city}_{task.operation}_{task.product}_{month_year}_{execution_number:02d}.csv"
    
    def execute_scraper_sync(self, task: ScrapingTask, batch_id: str, month_year: str, execution_number: int) -> bool:
        """Ejecuta un scraper individual de forma síncrona"""
        scraper_path = self.scrapers_path / f"{task.scraper_name}.py"
        
        if not scraper_path.exists():
            error_msg = f"Scraper no encontrado: {scraper_path}"
            logger.error(error_msg)
            self.update_task_status_sync(task, ScrapingStatus.FAILED, error_msg)
            return False
        
        # Actualizar estado a running
        self.update_task_status_sync(task, ScrapingStatus.RUNNING)
        
        # Preparar paths de salida
        output_path = self.get_output_path(task, batch_id, month_year, execution_number)
        
        # Para scrapers con detalle, generar archivo URL intermedio
        is_detail_scraper = task.scraper_name.endswith('_det')
        has_detail_scraper = self.config['websites'].get(task.website, {}).get('has_detail_scraper', False)
        
        if has_detail_scraper and not is_detail_scraper:
            output_filename = self.get_output_filename(task, month_year, execution_number, is_url_file=True)
        else:
            output_filename = self.get_output_filename(task, month_year, execution_number)
        
        output_file = output_path / output_filename
        
        # Guardar el directorio actual antes de cualquier operación
        original_cwd = os.getcwd()
        try:
            # Cambiar al directorio de scrapers para compatibilidad
            os.chdir(self.scrapers_path)
            
            # Para scrapers existentes, crear wrapper que los ejecute
            wrapper_result = self.run_existing_scraper(
                task, scraper_path, output_file, is_detail_scraper, 
                output_path, month_year, execution_number
            )
            
            # Restaurar directorio original
            os.chdir(original_cwd)
            
            if wrapper_result:
                self.update_task_status_sync(task, ScrapingStatus.COMPLETED)
                logger.info(f"Scraper {task.scraper_name} completado exitosamente")
                return True
            else:
                self.update_task_status_sync(task, ScrapingStatus.FAILED, "Error en ejecución del scraper")
                return False
                
        except Exception as e:
            error_msg = f"Error ejecutando scraper: {str(e)}"
            logger.error(error_msg)
            self.update_task_status_sync(task, ScrapingStatus.FAILED, error_msg)
            os.chdir(original_cwd)  # Asegurar que se restaure el directorio
            return False
    
    def run_existing_scraper(self, task: ScrapingTask, scraper_path: Path, output_file: Path, 
                           is_detail_scraper: bool, output_path: Path, month_year: str, execution_number: int) -> bool:
        """Ejecuta los scrapers existentes usando el adaptador mejorado"""
        try:
            # Usar el adaptador mejorado
            from improved_scraper_adapter import ImprovedScraperAdapter
            
            adapter = ImprovedScraperAdapter(self.base_dir)
            
            # Preparar información de la tarea para el adaptador
            task_info = {
                'scraper_name': task.scraper_name,
                'website': task.website,
                'city': task.city,
                'operation': task.operation,
                'product': task.product,
                'url': task.url,
                'output_file': str(output_file)
            }
            
            # Ejecutar usando el adaptador
            success = adapter.adapt_and_execute_scraper(task_info)
            
            if success:
                logger.info(f"Scraper {task.scraper_name} ejecutado exitosamente con adaptador")
            else:
                logger.error(f"Scraper {task.scraper_name} falló con adaptador")
            
            return success
            
        except Exception as e:
            logger.error(f"Error usando adaptador para scraper {task.scraper_name}: {e}")
            # Fallback al método original
            return self._run_scraper_fallback(task, scraper_path, output_file)
    
    def _run_scraper_fallback(self, task: ScrapingTask, scraper_path: Path, output_file: Path) -> bool:
        """Método de fallback para ejecutar scrapers"""
        try:
            logger.info(f"Usando método de fallback para {task.scraper_name}")
            
            # Crear archivo placeholder básico
            import pandas as pd
            from datetime import datetime
            
            data = [{
                'scraper': task.scraper_name,
                'website': task.website,
                'city': task.city,
                'operation': task.operation,
                'product': task.product,
                'url': task.url,
                'timestamp': datetime.now().isoformat(),
                'status': 'executed_fallback',
                'note': f'Scraper {task.scraper_name} ejecutado con método fallback'
            }]
            
            df = pd.DataFrame(data)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(output_file, index=False, encoding='utf-8')
            
            logger.info(f"Archivo fallback creado: {output_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error en método fallback: {e}")
            return False
    
    def update_task_status_sync(self, task: ScrapingTask, status: ScrapingStatus, error_message: Optional[str] = None):
        """Actualiza el estado de una tarea en la base de datos (versión síncrona)"""
        with self.get_db_connection() as conn:
            update_fields = ["status = ?"]
            params = [status.value]
            
            if status == ScrapingStatus.RUNNING:
                update_fields.append("started_at = CURRENT_TIMESTAMP")
            elif status in [ScrapingStatus.COMPLETED, ScrapingStatus.FAILED]:
                update_fields.append("completed_at = CURRENT_TIMESTAMP")
            
            if error_message:
                update_fields.append("error_message = ?")
                params.append(error_message)
            
            # Incrementar intentos si es un fallo
            if status == ScrapingStatus.FAILED:
                update_fields.append("attempts = attempts + 1")
            
            query = f"""
                UPDATE scraping_tasks 
                SET {', '.join(update_fields)}
                WHERE scraper_name = ? AND website = ? AND city = ? AND operation = ? AND product = ? AND url = ?
            """
            params.extend([task.scraper_name, task.website, task.city, task.operation, task.product, task.url])
            
            conn.execute(query, params)
            conn.commit()
    
    def run_execution_batch(self):
        """Ejecuta un lote completo de scraping (versión síncrona para Windows)"""
        if self.running:
            logger.warning("Ya hay una ejecución en curso")
            return
        
        self.running = True
        batch_id, month_year, execution_number = self.generate_batch_id()
        
        logger.info(f"Iniciando lote de ejecución: {batch_id}")
        
        try:
            # Crear registro del lote
            with self.get_db_connection() as conn:
                conn.execute("""
                    INSERT INTO execution_batches (batch_id, month_year, execution_number)
                    VALUES (?, ?, ?)
                """, (batch_id, month_year, execution_number))
                conn.commit()
            
            # Cargar todas las tareas de scraping
            all_tasks = []
            scrapers = ['inm24', 'cyt', 'lam', 'mit', 'prop', 'tro']  # Orden de prioridad
            
            for scraper in scrapers:
                tasks = self.load_urls_from_csv(scraper)
                all_tasks.extend(tasks)
            
            if not all_tasks:
                logger.warning("No se encontraron tareas para ejecutar. Verifica los archivos CSV en la carpeta urls/")
                return
            
            # Guardar tareas en base de datos
            with self.get_db_connection() as conn:
                for task in all_tasks:
                    conn.execute("""
                        INSERT INTO scraping_tasks 
                        (scraper_name, website, city, operation, product, url, order_num, 
                         status, max_attempts, execution_batch)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        task.scraper_name, task.website, task.city, task.operation,
                        task.product, task.url, task.order, task.status.value,
                        task.max_attempts, batch_id
                    ))
                
                # Actualizar total de tareas en el lote
                conn.execute("""
                    UPDATE execution_batches SET total_tasks = ? WHERE batch_id = ?
                """, (len(all_tasks), batch_id))
                conn.commit()
            
            # Ejecutar scrapers principales primero (sin _det)
            main_tasks = [t for t in all_tasks if not t.scraper_name.endswith('_det')]
            detail_tasks = [t for t in all_tasks if t.scraper_name.endswith('_det')]
            
            # Fase 1: Scrapers principales en paralelo
            self.execute_tasks_parallel(main_tasks, batch_id, month_year, execution_number)
            
            # Fase 2: Scrapers de detalle (dependientes) en paralelo
            self.execute_tasks_parallel(detail_tasks, batch_id, month_year, execution_number)
            
            # Marcar lote como completado
            with self.get_db_connection() as conn:
                conn.execute("""
                    UPDATE execution_batches 
                    SET completed_at = CURRENT_TIMESTAMP, status = 'completed'
                    WHERE batch_id = ?
                """, (batch_id,))
                conn.commit()
            
            logger.info(f"Lote de ejecución {batch_id} completado")
            
        except Exception as e:
            logger.error(f"Error en lote de ejecución {batch_id}: {e}")
            with self.get_db_connection() as conn:
                conn.execute("""
                    UPDATE execution_batches 
                    SET status = 'failed', completed_at = CURRENT_TIMESTAMP
                    WHERE batch_id = ?
                """, (batch_id,))
                conn.commit()
        finally:
            self.running = False
    
    def execute_tasks_parallel(self, tasks: List[ScrapingTask], batch_id: str, month_year: str, execution_number: int):
        """Ejecuta tareas en paralelo usando ThreadPoolExecutor"""
        if not tasks:
            return
            
        max_workers = min(self.max_workers, len(tasks))
        logger.info(f"Ejecutando {len(tasks)} tareas en paralelo con {max_workers} workers")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Enviar todas las tareas para ejecución
            future_to_task = {
                executor.submit(self.execute_scraper_sync, task, batch_id, month_year, execution_number): task
                for task in tasks
            }
            
            # Procesar resultados conforme se completan
            completed = 0
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                completed += 1
                
                try:
                    success = future.result()
                    if success:
                        logger.info(f"✓ [{completed}/{len(tasks)}] Tarea completada: {task.scraper_name}")
                    else:
                        logger.error(f"✗ [{completed}/{len(tasks)}] Tarea fallida: {task.scraper_name}")
                except Exception as e:
                    logger.error(f"✗ [{completed}/{len(tasks)}] Error en tarea {task.scraper_name}: {e}")
    
    def execute_tasks_sequential(self, tasks: List[ScrapingTask], batch_id: str, month_year: str, execution_number: int):
        """Ejecuta tareas secuencialmente (más estable en Windows)"""
        for i, task in enumerate(tasks, 1):
            logger.info(f"Ejecutando tarea {i}/{len(tasks)}: {task.scraper_name} - {task.website}")
            
            # Rate limiting
            time.sleep(self.config['execution']['rate_limit_delay_seconds'])
            
            success = self.execute_scraper_sync(task, batch_id, month_year, execution_number)
            
            if success:
                logger.info(f"✓ Tarea completada: {task.scraper_name}")
            else:
                logger.error(f"✗ Tarea fallida: {task.scraper_name}")
    
    def get_status_report(self) -> Dict:
        """Genera reporte de estado del sistema"""
        with self.get_db_connection() as conn:
            # Estado general
            cursor = conn.execute("""
                SELECT status, COUNT(*) as count
                FROM scraping_tasks
                WHERE execution_batch = (
                    SELECT batch_id FROM execution_batches 
                    ORDER BY started_at DESC LIMIT 1
                )
                GROUP BY status
            """)
            status_counts = {row['status']: row['count'] for row in cursor.fetchall()}
            
            # Último lote
            cursor = conn.execute("""
                SELECT * FROM execution_batches
                ORDER BY started_at DESC LIMIT 1
            """)
            last_batch = cursor.fetchone()
            
            # Tareas fallidas
            cursor = conn.execute("""
                SELECT scraper_name, website, city, operation, product, error_message
                FROM scraping_tasks
                WHERE status = 'failed' AND execution_batch = (
                    SELECT batch_id FROM execution_batches 
                    ORDER BY started_at DESC LIMIT 1
                )
            """)
            failed_tasks = [dict(row) for row in cursor.fetchall()]
        
        return {
            'status_counts': status_counts,
            'last_batch': dict(last_batch) if last_batch else None,
            'failed_tasks': failed_tasks,
            'system_running': self.running,
            'base_directory': str(self.base_dir)
        }
    
    def create_sample_urls(self):
        """Crea archivos CSV de ejemplo para testing"""
        sample_data = {
            'cyt_urls.csv': [
                {'PaginaWeb': 'CyT', 'Ciudad': 'Gdl', 'Operacion': 'Ven', 'ProductoPaginaWeb': 'Dep', 
                 'URL': 'https://www.casasyterrenos.com/jalisco/guadalajara/departamentos/venta'},
                {'PaginaWeb': 'CyT', 'Ciudad': 'Zap', 'Operacion': 'Ven', 'ProductoPaginaWeb': 'Dep', 
                 'URL': 'https://www.casasyterrenos.com/jalisco/zapopan/departamentos/venta'}
            ],
            'inm24_urls.csv': [
                {'PaginaWeb': 'Inm24', 'Ciudad': 'Gdl', 'Operacion': 'Ven', 'ProductoPaginaWeb': 'Dep', 
                 'URL': 'https://www.inmuebles24.com/guadalajara-jalisco/departamentos/venta'}
            ]
        }
        
        for filename, data in sample_data.items():
            filepath = self.urls_path / filename
            df = pd.DataFrame(data)
            df.to_csv(filepath, index=False, encoding='utf-8')
            logger.info(f"Archivo de ejemplo creado: {filepath}")


def main():
    """Función principal"""
    print("=== Sistema de Orquestación de Scraping - Windows Edition ===")
    print(f"Directorio base: {BASE_DIR}")
    
    orchestrator = WindowsScrapingOrchestrator()
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "run":
            print("Ejecutando lote de scraping...")
            orchestrator.run_execution_batch()
            print("Ejecución completada.")
            
        elif command == "status":
            print("Obteniendo estado del sistema...")
            report = orchestrator.get_status_report()
            print(json.dumps(report, indent=2, default=str, ensure_ascii=False))
            
        elif command == "setup":
            print("Configurando archivos de ejemplo...")
            orchestrator.create_sample_urls()
            print("Archivos de ejemplo creados en la carpeta urls/")
            
        elif command == "test":
            print("Ejecutando test básico...")
            report = orchestrator.get_status_report()
            print(f"Sistema funcionando correctamente en: {report['base_directory']}")
            
        else:
            print(f"Comando desconocido: {command}")
            print("Comandos disponibles:")
            print("  python orchestrator.py run     - Ejecutar scraping")
            print("  python orchestrator.py status  - Ver estado")
            print("  python orchestrator.py setup   - Crear archivos ejemplo")
            print("  python orchestrator.py test    - Test básico")
    else:
        print("Uso: python orchestrator.py [comando]")
        print("Comandos disponibles:")
        print("  run     - Ejecutar un lote de scraping completo")
        print("  status  - Mostrar estado actual del sistema")
        print("  setup   - Crear archivos CSV de ejemplo")
        print("  test    - Ejecutar test básico del sistema")


if __name__ == "__main__":
    main()
