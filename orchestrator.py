#!/usr/bin/env python3
"""
Sistema de Orquestación de Scraping Inmobiliario - Ubuntu Linux Edition
Versión optimizada para Ubuntu 24.04 LTS con ejecución paralela
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
import threading
from collections import defaultdict

# Integración del adaptador de scrapers
from scraper_adapter import ScraperAdapter
from abbreviation_utils import AbbreviationResolver

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

class LinuxScrapingOrchestrator:
    """Orquestador principal optimizado para Ubuntu Linux"""

    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            config_path = str(CONFIG_PATH)
        
        self.config = self._load_config(config_path)
        self.base_dir = BASE_DIR
        self.db_path = Path(self.config['database']['path'])
        self.data_path = Path(self.config['data']['base_path'])
        # Soporte dual para 'urls' y 'Urls' (advertencia si existe variante capitalizada)
        configured_urls = Path(self.config['data']['urls_path'])
        alt_cap = self.base_dir / 'Urls'
        if not configured_urls.exists() and alt_cap.exists():
            logger.warning("Se encontró carpeta 'Urls/' en lugar de 'urls/'. Usando 'Urls/' temporalmente. Se recomienda renombrar a 'urls'.")
            self.urls_path = alt_cap
        else:
            self.urls_path = configured_urls
        self.scrapers_path = self.base_dir / Path(self.config['scrapers']['path'])
        self.adapter = ScraperAdapter(self.base_dir)
        self.abbreviation_resolver = AbbreviationResolver(
            self.base_dir / "Lista de Variables" / "Lista de Variables Orquestacion.csv",
            strict=True,
        )
        self.scraper_expected_sites = {
            'inm24': 'Inm24',
            'lam': 'Lam',
            'cyt': 'CyT',
            'mit': 'Mit',
            'prop': 'Prop',
            'tro': 'Tro',
        }
        self._website_override_notified = set()
        
        # Crear directorios necesarios
        self._ensure_directories()
        
        # Inicializar base de datos
        self._init_database()
        
        # Control de ejecución
        self.running = False
        self.shutdown_requested = False
        
        # Pool de trabajadores (optimizado para Ubuntu Linux)
        self.max_workers = self.config['execution']['max_parallel_scrapers']

        # Locks por sitio para evitar 2 scrapers simultáneos del mismo dominio
        # Nota: evitamos anotación inline para compatibilidad con algunos analizadores
        self._site_locks = defaultdict(threading.Lock)

        logger.info(f"Orquestador inicializado en: {self.base_dir}")

    @staticmethod
    def _clean_csv_value(value) -> str:
        """Normaliza valores provenientes de CSV manejando NaN y espacios."""
        if pd.isna(value):
            return ""
        return str(value).strip()

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
        """Configuración por defecto optimizada para Ubuntu Linux"""
        return {
            'database': {'path': str(BASE_DIR / 'orchestrator.db')},
            'data': {
                'base_path': str(BASE_DIR / 'data'),
                'urls_path': str(BASE_DIR / 'urls')
            },
            'scrapers': {'path': str(BASE_DIR / 'Scrapers')},
            'execution': {
                'max_parallel_scrapers': 8,  # Optimizado para Linux
                'retry_delay_minutes': 15,   # Reducido para Ubuntu
                'execution_interval_days': 15,
                'rate_limit_delay_seconds': 2,  # Reducido para mejor rendimiento
                'chain_detail_immediately': True
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

            # Tabla para rastrear archivos CSV ingeridos y evitar duplicados
            conn.execute('''
                CREATE TABLE IF NOT EXISTS ingested_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scraper_name TEXT NOT NULL,
                    website TEXT,
                    source_file TEXT NOT NULL,
                    table_name TEXT NOT NULL,
                    rows_ingested INTEGER,
                    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    batch_id TEXT,
                    UNIQUE(scraper_name, source_file)
                )
            ''')

            # Tabla de metadata de columnas por scraper (JSON schema simple)
            conn.execute('''
                CREATE TABLE IF NOT EXISTS scraper_metadata (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scraper_name TEXT NOT NULL UNIQUE,
                    table_name TEXT NOT NULL,
                    columns_json TEXT NOT NULL,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
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
        """Genera un ID de lote basado en quincena:
        01 = días 1-15, 02 = días 16-fin.
        Si ya existiera ese execution_number para el mes, se incrementa versión adicional (03, 04...)"""
        now = datetime.now()
        month_year = now.strftime("%b%y")  # Ej: Sep25
        quin = 1 if now.day <= 15 else 2
        desired_execution_number = quin  # 1 ó 2

        with self.get_db_connection() as conn:
            # Verificar si ya existe ese execution_number para este mes
            cursor = conn.execute(
                "SELECT execution_number FROM execution_batches WHERE month_year = ? ORDER BY execution_number",
                (month_year,)
            )
            existing = {row[0] for row in cursor.fetchall()}
            execution_number = desired_execution_number
            # Si ya existe (por re-ejecución manual), avanzar al siguiente libre
            while execution_number in existing:
                execution_number += 1

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

            limit_one = bool(self.config.get('execution', {}).get('single_url_task_per_scraper', False))
            for i, (_, row) in enumerate(df.iterrows()):
                website = self.abbreviation_resolver.to_abbreviation(
                    self._clean_csv_value(row.get('PaginaWeb', '')),
                    context='PaginaWeb'
                )
                city = self.abbreviation_resolver.to_abbreviation(
                    self._clean_csv_value(row.get('Ciudad', '')),
                    context='Ciudad'
                )
                operation = self.abbreviation_resolver.to_abbreviation(
                    self._clean_csv_value(row.get('Operacion', '')),
                    context='Operacion'
                )
                product = self.abbreviation_resolver.to_abbreviation(
                    self._clean_csv_value(row.get('ProductoPaginaWeb', '')),
                    context='ProductoPaginaWeb'
                )
                expected_site = self.scraper_expected_sites.get(scraper_name.lower())
                if expected_site and website != expected_site:
                    notify_key = (scraper_name, website)
                    if notify_key not in self._website_override_notified:
                        logger.warning(
                            "Sobrescribiendo PaginaWeb '%s' por abreviatura esperada '%s' para scraper %s",
                            website,
                            expected_site,
                            scraper_name,
                        )
                        self._website_override_notified.add(notify_key)
                    website = expected_site
                task = ScrapingTask(
                    scraper_name=scraper_name,
                    website=website,
                    city=city,
                    operation=operation,
                    product=product,
                    url=row['URL'],
                    order=i + 1,
                    created_at=datetime.now()
                )
                tasks.append(task)
                if limit_one:
                    # Solo tomar la primera coincidencia por scraper para que el scraper pagine internamente
                    break
                
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
            return False  # No intentar actualizar DB si no hay tabla
        
        # Asegurar que la base de datos está inicializada antes de cualquier operación
        try:
            with self.get_db_connection() as conn:
                # Test de conexión y existencia de tabla
                conn.execute("SELECT 1 FROM scraping_tasks LIMIT 1")
        except sqlite3.OperationalError as e:
            if "no such table" in str(e):
                logger.error("La tabla scraping_tasks no existe. Reinicializando base de datos...")
                self._init_database()
            else:
                logger.error(f"Error de base de datos: {e}")
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

        # Validar precondición para scrapers de detalle: debe existir archivo *_URL_* correspondiente
        if is_detail_scraper:
            parent_url_filename = self.get_output_filename(task, month_year, execution_number, is_url_file=True)
            parent_url_path = output_path / parent_url_filename
            if not parent_url_path.exists():
                self.update_task_status_sync(task, ScrapingStatus.FAILED, f"Archivo base de URLs no encontrado: {parent_url_filename}")
                logger.error(f"Detalle abortado. Falta archivo URL: {parent_url_path}")
                return False
        
        # Guardar el directorio actual antes de cualquier operación
        original_cwd = os.getcwd()
        try:
            # Ejecutar scraper usando el adaptador (mejor control de outputs)
            env_info = {
                'website': task.website,
                'city': task.city,
                'operation': task.operation,
                'product': task.product,
                'batch_id': batch_id,
                'order': task.order,
                'is_detail': is_detail_scraper,
                'url_from_task': task.url
            }

            # El adaptador aún no inyecta URL en scrapers legacy, pero dejamos registro
            logger.info(f"[Adapter] Ejecutando {task.scraper_name} (order={task.order}) -> {output_file.name}")
            # Determinar max_pages por sitio si est1 configurado
            site_cfg = self.config.get('websites', {}).get(task.website, {})
            site_max_pages = site_cfg.get('max_pages_per_session')
            success = self.adapter.adapt_scraper(
                task.scraper_name,
                task.url,
                output_file,
                max_pages=site_max_pages,
                **env_info
            )

            if success:
                self.update_task_status_sync(task, ScrapingStatus.COMPLETED, None, output_path=str(output_file))
                logger.info(f"Scraper {task.scraper_name} completado exitosamente (adapter)")
                # Ingestión SQL heterogénea (si habilitada)
                try:
                    self.store_scraper_output(task, output_file, batch_id)
                except Exception as ing_e:
                    logger.error(f"Error en ingestión SQL para {task.scraper_name}: {ing_e}")
                return True
            else:
                self.update_task_status_sync(task, ScrapingStatus.FAILED, "Ejecución fallida (adapter)")
                return False

        except Exception as e:
            error_msg = f"Error ejecutando scraper (adapter): {str(e)}"
            logger.error(error_msg)
            self.update_task_status_sync(task, ScrapingStatus.FAILED, error_msg)
            return False
    
    def run_existing_scraper(self, task: ScrapingTask, scraper_path: Path, output_file: Path, 
                           is_detail_scraper: bool, output_path: Path, month_year: str, execution_number: int) -> bool:
        """Ejecuta los scrapers originales directamente"""
        try:
            # Ejecutar el scraper original directamente
            original_cwd = os.getcwd()
            os.chdir(self.scrapers_path)
            
            result = subprocess.run([
                sys.executable, str(scraper_path.name)
            ], capture_output=True, text=True, timeout=300)  # 5 minutos timeout
            
            os.chdir(original_cwd)
            
            if result.returncode == 0:
                logger.info(f"Scraper {task.scraper_name} ejecutado correctamente")
                return True
            else:
                logger.error(f"Scraper {task.scraper_name} falló: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout ejecutando scraper {task.scraper_name}")
            return False
        except Exception as e:
            logger.error(f"Error ejecutando scraper {task.scraper_name}: {e}")
            return False
    
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
    
    def update_task_status_sync(self, task: ScrapingTask, status: ScrapingStatus, error_message: Optional[str] = None, output_path: Optional[str] = None):
        """Actualiza el estado de una tarea en la base de datos (versión síncrona)"""
        try:
            with self.get_db_connection() as conn:
                # Verificar que la tabla existe
                conn.execute("SELECT 1 FROM scraping_tasks LIMIT 1")
                
                update_fields = ["status = ?"]
                params = [status.value]
                
                if status == ScrapingStatus.RUNNING:
                    update_fields.append("started_at = CURRENT_TIMESTAMP")
                elif status in [ScrapingStatus.COMPLETED, ScrapingStatus.FAILED]:
                    update_fields.append("completed_at = CURRENT_TIMESTAMP")
                
                if error_message:
                    update_fields.append("error_message = ?")
                    params.append(error_message)
                if output_path:
                    update_fields.append("output_path = ?")
                    params.append(output_path)
                
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

                # Actualizar contadores de batch si es estado terminal
                if status in (ScrapingStatus.COMPLETED, ScrapingStatus.FAILED):
                    delta_completed = 1 if status == ScrapingStatus.COMPLETED else 0
                    delta_failed = 1 if status == ScrapingStatus.FAILED else 0
                    conn.execute(
                        """
                        UPDATE execution_batches
                        SET completed_tasks = completed_tasks + ?,
                            failed_tasks = failed_tasks + ?
                        WHERE batch_id = (
                            SELECT execution_batch FROM scraping_tasks
                            WHERE scraper_name = ? AND website = ? AND city = ? AND operation = ? AND product = ? AND url = ?
                            LIMIT 1
                        )
                        """,
                        (delta_completed, delta_failed, task.scraper_name, task.website, task.city, task.operation, task.product, task.url)
                    )
                conn.commit()
                
        except sqlite3.OperationalError as e:
            if "no such table" in str(e):
                logger.warning(f"Tabla no existe al actualizar estado de {task.scraper_name}, omitiendo actualización")
            else:
                logger.error(f"Error actualizando estado de tarea: {e}")
        except Exception as e:
            logger.error(f"Error inesperado actualizando estado: {e}")

    # ------------------------ Ingestión Heterogénea ------------------------
    def store_scraper_output(self, task: ScrapingTask, output_file: Path, batch_id: str):
        """Ingresa un archivo CSV generado por un scraper a una tabla específica.
        Estrategia heterogénea: una tabla por scraper (prefijo configurable).
        - Normaliza nombres de columnas si está activado en config.
        - Crea/Actualiza esquema agregando columnas nuevas.
        - Inserta filas en chunks.
        - Registra metadata y archivo ingerido.
        """
        cfg = self.config.get('data_storage', {})
        if not cfg.get('enable_sql_ingest', False):
            return
        if not output_file.exists():
            logger.warning(f"Archivo de salida no existe para ingestión: {output_file}")
            return
        try:
            df = pd.read_csv(output_file, encoding='utf-8')
        except Exception as e:
            logger.error(f"No se pudo leer CSV para ingestión ({output_file}): {e}")
            return
        if df.empty:
            logger.info(f"CSV vacío, se omite ingestión: {output_file}")
            return

        table_prefix = cfg.get('table_prefix', 'data_')
        table_name = f"{table_prefix}{task.scraper_name.lower()}"
        normalize = cfg.get('normalize_column_names', True)

        # Normalizar columnas
        original_columns = list(df.columns)
        col_map = {}
        new_columns = []
        for c in original_columns:
            nc = c
            if normalize:
                nc = c.strip().lower().replace(' ', '_').replace('-', '_').replace('__', '_')
            # Evitar nombres vacíos
            if not nc:
                nc = 'col'
            # Evitar colisiones
            base_nc = nc
            idx = 1
            while nc in new_columns:
                nc = f"{base_nc}_{idx}"
                idx += 1
            new_columns.append(nc)
            col_map[c] = nc
        df.rename(columns=col_map, inplace=True)

        # Tipos básicos (todos TEXT inicialmente para heterogeneidad)
        column_types = {c: 'TEXT' for c in df.columns}

        with self.get_db_connection() as conn:
            cur = conn.cursor()
            # Asegurar tablas auxiliares existen (por robustez)
            cur.execute('''
                CREATE TABLE IF NOT EXISTS ingested_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scraper_name TEXT NOT NULL,
                    website TEXT,
                    source_file TEXT NOT NULL,
                    table_name TEXT NOT NULL,
                    rows_ingested INTEGER,
                    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    batch_id TEXT,
                    UNIQUE(scraper_name, source_file)
                )
            ''')
            cur.execute('''
                CREATE TABLE IF NOT EXISTS scraper_metadata (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scraper_name TEXT NOT NULL UNIQUE,
                    table_name TEXT NOT NULL,
                    columns_json TEXT NOT NULL,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # Crear tabla si no existe
            cols_def = ', '.join([f'"{c}" {t}' for c, t in column_types.items()])
            cur.execute(f'CREATE TABLE IF NOT EXISTS {table_name} (id INTEGER PRIMARY KEY AUTOINCREMENT, {cols_def})')

            # Detectar columnas faltantes y agregarlas
            cur.execute(f'PRAGMA table_info({table_name})')
            existing_cols = {row[1] for row in cur.fetchall()}
            to_add = [c for c in df.columns if c not in existing_cols]
            if to_add and cfg.get('add_missing_columns', True):
                for c in to_add:
                    cur.execute(f'ALTER TABLE {table_name} ADD COLUMN "{c}" TEXT')
                    logger.info(f"Columna añadida a {table_name}: {c}")

            # Evitar reinserción si ya existe (tracking)
            rel_path = os.path.relpath(output_file, self.base_dir)
            if cfg.get('track_ingested_files', True):
                if cfg.get('skip_if_exists', True):
                    cur.execute('SELECT 1 FROM ingested_files WHERE scraper_name=? AND source_file=?', (task.scraper_name, rel_path))
                    if cur.fetchone():
                        logger.info(f"Archivo ya ingerido, se omite: {rel_path}")
                        return

            # Insertar en chunks
            chunk_size = int(cfg.get('chunk_size', 1000))
            total_rows = 0
            cols = df.columns.tolist()
            placeholders = ','.join(['?'] * len(cols))
            insert_sql = f'INSERT INTO {table_name} ({",".join([f'"{c}"' for c in cols])}) VALUES ({placeholders})'
            for start in range(0, len(df), chunk_size):
                subset = df.iloc[start:start+chunk_size]
                cur.executemany(insert_sql, subset.values.tolist())
                total_rows += len(subset)
            logger.info(f"Ingeridas {total_rows} filas en {table_name} desde {output_file.name}")

            # Actualizar metadata
            if cfg.get('store_metadata', True):
                import json as _json
                cur.execute('''
                    INSERT INTO scraper_metadata(scraper_name, table_name, columns_json, last_updated)
                    VALUES(?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(scraper_name) DO UPDATE SET
                        columns_json=excluded.columns_json,
                        last_updated=CURRENT_TIMESTAMP
                ''', (task.scraper_name, table_name, _json.dumps({'columns': df.columns.tolist()})))

            # Registrar archivo ingresado
            if cfg.get('track_ingested_files', True):
                cur.execute('''
                    INSERT OR IGNORE INTO ingested_files(scraper_name, website, source_file, table_name, rows_ingested, batch_id)
                    VALUES(?, ?, ?, ?, ?, ?)
                ''', (task.scraper_name, task.website, rel_path, table_name, total_rows, batch_id))

            conn.commit()
        
        logger.info(f"Ingestión completada para {task.scraper_name}: {output_file}")
    
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
            configured = self.config.get('execution', {}).get('include_scrapers')
            if configured and isinstance(configured, list) and configured:
                scrapers = configured
            else:
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
            
            # Fase 1: Ejecutar solo scrapers principales (ignoramos *_det del CSV si existieran)
            main_tasks = [t for t in all_tasks if not t.scraper_name.endswith('_det')]
            self.execute_tasks_parallel(main_tasks, batch_id, month_year, execution_number)
            
            # Fase 2 (opcional): generar tareas de detalle UNA SOLA VEZ si no se encadenan inmediatamente
            if not self.config['execution'].get('chain_detail_immediately', True):
                detail_tasks: List[ScrapingTask] = []
                for base_task in main_tasks:
                    site_cfg = self.config['websites'].get(base_task.website, {})
                    if site_cfg.get('has_detail_scraper'):
                        det_scraper_name = base_task.scraper_name + '_det'
                        det_task = ScrapingTask(
                            scraper_name=det_scraper_name,
                            website=base_task.website,
                            city=base_task.city,
                            operation=base_task.operation,
                            product=base_task.product,
                            url=f"DETAIL_FROM:{base_task.scraper_name}",
                            order=base_task.order,
                            created_at=datetime.now()
                        )
                        detail_tasks.append(det_task)

                if detail_tasks:
                    with self.get_db_connection() as conn:
                        for det in detail_tasks:
                            conn.execute(
                                """INSERT INTO scraping_tasks (scraper_name, website, city, operation, product, url, order_num, status, max_attempts, execution_batch)
                                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                                (det.scraper_name, det.website, det.city, det.operation, det.product, det.url, det.order, det.status.value, det.max_attempts, batch_id)
                            )
                        conn.execute("UPDATE execution_batches SET total_tasks = total_tasks + ? WHERE batch_id = ?", (len(detail_tasks), batch_id))
                        conn.commit()

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
        
        def guarded_execute(task: ScrapingTask):
            lock = self._site_locks[task.website]
            acquired = lock.acquire(timeout=3600)  # hasta 1h por seguridad
            if not acquired:
                logger.error(f"No se pudo adquirir lock para sitio {task.website} en tarea {task.scraper_name}")
                return False
            try:
                logger.info(f"[LOCK ACQUIRED] {task.website} -> {task.scraper_name}")
                success = self.execute_scraper_sync(task, batch_id, month_year, execution_number)
                # Si el scraper base completó y el sitio tiene scraper de detalle, ejecutar inmediatamente su *_det
                try:
                    site_cfg = self.config['websites'].get(task.website, {})
                    has_detail = site_cfg.get('has_detail_scraper', False)
                    is_detail = task.scraper_name.endswith('_det')
                    if success and has_detail and not is_detail:
                        det_task = ScrapingTask(
                            scraper_name=task.scraper_name + '_det',
                            website=task.website,
                            city=task.city,
                            operation=task.operation,
                            product=task.product,
                            url=f"DETAIL_FROM:{task.scraper_name}",
                            order=task.order,
                            created_at=datetime.now()
                        )
                        logger.info(f"[CHAIN] Ejecutando detalle inmediatamente: {det_task.scraper_name} para {task.website}")
                        # Ejecutar detalle respetando el mismo lock del sitio
                        self.execute_scraper_sync(det_task, batch_id, month_year, execution_number)
                except Exception as chain_e:
                    logger.error(f"Error encadenando scraper de detalle para {task.scraper_name}: {chain_e}")
                return success
            finally:
                lock.release()
                logger.info(f"[LOCK RELEASED] {task.website} -> {task.scraper_name}")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Enviar todas las tareas para ejecución con protección por sitio
            future_to_task = {
                executor.submit(guarded_execute, task): task
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

        # Reintentos básicos: seleccionar fallidas con attempts < max_attempts
        retry_candidates: List[ScrapingTask] = []
        with self.get_db_connection() as conn:
            cursor = conn.execute("""
                SELECT scraper_name, website, city, operation, product, url, attempts, max_attempts
                FROM scraping_tasks
                WHERE status='failed' AND execution_batch=?
            """, (batch_id,))
            for row in cursor.fetchall():
                if row['attempts'] < row['max_attempts']:
                    retry_candidates.append(ScrapingTask(
                        scraper_name=row['scraper_name'],
                        website=row['website'],
                        city=row['city'],
                        operation=row['operation'],
                        product=row['product'],
                        url=row['url'],
                        order=0,  # orden no crítico en reintento
                        attempts=row['attempts'],
                        max_attempts=row['max_attempts']
                    ))

        if retry_candidates:
            logger.info(f"Reintentos: {len(retry_candidates)} tareas serán reejecutadas")
            for t in retry_candidates:
                self.update_task_status_sync(t, ScrapingStatus.RETRYING, None)
                # Pequeña espera para no saturar
                time.sleep(1)
                success = self.execute_scraper_sync(t, batch_id, month_year, execution_number)
                if success:
                    logger.info(f"✓ Reintento exitoso: {t.scraper_name}")
                else:
                    logger.error(f"✗ Reintento fallido: {t.scraper_name}")
    
    def execute_tasks_sequential(self, tasks: List[ScrapingTask], batch_id: str, month_year: str, execution_number: int):
        """Ejecuta tareas secuencialmente (fallback para casos específicos)"""
        for i, task in enumerate(tasks, 1):
            logger.info(f"Ejecutando tarea {i}/{len(tasks)}: {task.scraper_name} - {task.website}")
            
            # Rate limiting
            time.sleep(self.config['execution']['rate_limit_delay_seconds'])
            # Asegurar exclusión por sitio también en modo secuencial (por si otros hilos existen)
            lock = self._site_locks[task.website]
            acquired = lock.acquire(timeout=3600)
            if not acquired:
                logger.error(f"(Seq) No se pudo adquirir lock para {task.website} -> {task.scraper_name}")
                self.update_task_status_sync(task, ScrapingStatus.FAILED, "Lock no adquirido en modo secuencial")
                continue
            try:
                logger.info(f"(Seq)[LOCK ACQUIRED] {task.website} -> {task.scraper_name}")
                success = self.execute_scraper_sync(task, batch_id, month_year, execution_number)
            finally:
                lock.release()
                logger.info(f"(Seq)[LOCK RELEASED] {task.website} -> {task.scraper_name}")
            
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
    print("=== Sistema de Orquestación de Scraping - Ubuntu Linux Edition ===")
    print(f"Directorio base: {BASE_DIR}")
    
    orchestrator = LinuxScrapingOrchestrator()
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "run":
            print("Ejecutando lote de scraping...")
            orchestrator.run_execution_batch()
            print("Ejecución completada.")
        
        elif command == "ingest-existing":
            print("Ingeriendo archivos CSV existentes a la base de datos...")
            cfg = orchestrator.config.get('data_storage', {})
            if not cfg.get('enable_sql_ingest', False):
                print("Ingestión deshabilitada (data_storage.enable_sql_ingest=false)")
                sys.exit(1)
            count_files = 0
            for csv_path in orchestrator.data_path.rglob('*.csv'):
                # Heurística para identificar scraper_name: primer token antes de '_' o 'URL_'
                name_part = csv_path.name.split('_')[0]
                scraper_name_guess = name_part.lower()
                # Construir tarea ficticia mínima
                fake_task = ScrapingTask(
                    scraper_name=scraper_name_guess,
                    website=name_part,  # asumimos coincide en mayúsculas/minúsculas
                    city="",
                    operation="",
                    product="",
                    url=f"INGEST_ONLY:{csv_path.name}",
                    order=0
                )
                try:
                    orchestrator.store_scraper_output(fake_task, csv_path, batch_id="MANUAL")
                    count_files += 1
                except Exception as e:
                    logger.error(f"Error ingiriendo {csv_path}: {e}")
            print(f"Ingestión completada. Archivos procesados: {count_files}")
            
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
        print("  ingest-existing - Ingerir todos los CSV existentes en data/ a tablas SQL")
        print("  status  - Mostrar estado actual del sistema")
        print("  setup   - Crear archivos CSV de ejemplo")
        print("  test    - Ejecutar test básico del sistema")


if __name__ == "__main__":
    main()
