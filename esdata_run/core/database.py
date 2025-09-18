"""Módulo de persistencia y utilidades de acceso a SQLite."""
from __future__ import annotations

import sqlite3
import logging
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator, List, Optional, Sequence

from ..models.main import ExecutionBatch, ScrapingTask, TaskStatus

logger = logging.getLogger(__name__)


class TaskRepository:
    """
    Gestor de la base de datos SQLite. Se encarga de crear el esquema,
    y de todas las operaciones de lectura/escritura para lotes y tareas.
    """

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()
        logger.info("Repositorio de tareas inicializado en: %s", self.db_path)

    @contextmanager
    def get_connection(self) -> Iterator[sqlite3.Connection]:
        """Proporciona una conexión a la base de datos con una configuración óptima."""
        try:
            conn = sqlite3.connect(self.db_path, timeout=15)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            yield conn
        except sqlite3.Error as e:
            logger.error("Error de base de datos: %s", e)
            raise
        finally:
            if 'conn' in locals():
                conn.close()

    def _ensure_schema(self) -> None:
        """Crea las tablas y los índices necesarios si no existen."""
        schema_sql = """
        CREATE TABLE IF NOT EXISTS execution_batches (
            batch_id TEXT PRIMARY KEY,
            month_year TEXT NOT NULL,
            execution_number INTEGER NOT NULL,
            status TEXT NOT NULL,
            started_at TEXT NOT NULL,
            completed_at TEXT,
            total_tasks INTEGER NOT NULL,
            completed_tasks INTEGER DEFAULT 0,
            failed_tasks INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS scraping_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id TEXT NOT NULL,
            scraper_name TEXT NOT NULL,
            url TEXT NOT NULL,
            "order" INTEGER NOT NULL,
            website_code TEXT NOT NULL,
            city_code TEXT NOT NULL,
            operation_code TEXT NOT NULL,
            product_code TEXT NOT NULL,
            status TEXT NOT NULL,
            attempts INTEGER NOT NULL,
            max_attempts INTEGER NOT NULL,
            is_detail INTEGER NOT NULL,
            depends_on TEXT,
            created_at TEXT NOT NULL,
            started_at TEXT,
            completed_at TEXT,
            error_message TEXT,
            output_path TEXT,
            FOREIGN KEY (batch_id) REFERENCES execution_batches (batch_id)
        );

        CREATE INDEX IF NOT EXISTS idx_tasks_batch_status ON scraping_tasks(batch_id, status);
        CREATE INDEX IF NOT EXISTS idx_tasks_depends_on ON scraping_tasks(depends_on);
        """
        with self.get_connection() as conn:
            conn.executescript(schema_sql)
            conn.commit()

    # --- Operaciones con Lotes (ExecutionBatch) ---

    def create_batch(self, batch_id: str, month_year: str, exec_num: int, total_tasks: int) -> ExecutionBatch:
        batch = ExecutionBatch(
            batch_id=batch_id,
            month_year=month_year,
            execution_number=exec_num,
            status="running",
            started_at=datetime.utcnow(),
            total_tasks=total_tasks,
        )
        with self.get_connection() as conn:
            conn.execute(
                "INSERT INTO execution_batches (batch_id, month_year, execution_number, status, started_at, total_tasks) VALUES (?, ?, ?, ?, ?, ?)",
                (batch.batch_id, batch.month_year, batch.execution_number, batch.status, batch.started_at.isoformat(), batch.total_tasks),
            )
            conn.commit()
        return batch

    def find_open_batch(self) -> Optional[ExecutionBatch]:
        """Encuentra el último lote que no esté completado o fallido."""
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM execution_batches WHERE status NOT IN ('completed', 'failed') ORDER BY started_at DESC LIMIT 1"
            ).fetchone()
        return ExecutionBatch.from_db_row(dict(row)) if row else None

    def next_execution_number(self, month_year: str, desired_quincena: int) -> int:
        """Calcula el siguiente número de ejecución para una quincena, evitando colisiones."""
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT execution_number FROM execution_batches WHERE month_year = ?", (month_year,)
            ).fetchall()
        
        existing_numbers = {row['execution_number'] for row in rows}
        if desired_quincena not in existing_numbers:
            return desired_quincena
        
        # Si la quincena deseada ya existe (ej. por una ejecución manual), busca el siguiente número libre
        candidate = max(existing_numbers, default=0) + 1
        return candidate

    def update_batch_progress(self, batch_id: str, completed_delta: int = 0, failed_delta: int = 0):
        with self.get_connection() as conn:
            conn.execute(
                "UPDATE execution_batches SET completed_tasks = completed_tasks + ?, failed_tasks = failed_tasks + ? WHERE batch_id = ?",
                (completed_delta, failed_delta, batch_id),
            )
            conn.commit()

    def mark_batch_completed(self, batch_id: str):
        with self.get_connection() as conn:
            conn.execute(
                "UPDATE execution_batches SET status = 'completed', completed_at = ? WHERE batch_id = ?",
                (datetime.utcnow().isoformat(), batch_id),
            )
            conn.commit()

    # --- Operaciones con Tareas (ScrapingTask) ---

    def insert_tasks(self, tasks: Sequence[ScrapingTask]):
        if not tasks:
            return
        task_dicts = [task.to_db_dict() for task in tasks]
        with self.get_connection() as conn:
            # Usamos un diccionario para el INSERT para que coincida con los nombres de columna
            # y sea más robusto a cambios en el modelo.
            sample = task_dicts[0]
            cols = ", ".join(f'"{k}"' for k in sample.keys())
            placeholders = ", ".join("?" for _ in sample)
            
            values_to_insert = [tuple(d.values()) for d in task_dicts]

            conn.executemany(f"INSERT INTO scraping_tasks ({cols}) VALUES ({placeholders})", values_to_insert)
            conn.commit()

    def get_tasks_for_batch(self, batch_id: str) -> List[ScrapingTask]:
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM scraping_tasks WHERE batch_id = ?", (batch_id,)).fetchall()
        return [ScrapingTask.from_db_row(dict(row)) for row in rows]

    def reset_running_tasks(self):
        """Al iniciar, resetea a 'pending' las tareas que se quedaron como 'running'."""
        with self.get_connection() as conn:
            conn.execute("UPDATE scraping_tasks SET status = 'pending' WHERE status = 'running'")
            conn.commit()

    def mark_task_running(self, task: ScrapingTask):
        with self.get_connection() as conn:
            conn.execute(
                "UPDATE scraping_tasks SET status = 'running', started_at = ? WHERE id = ?",
                (datetime.utcnow().isoformat(), task.id),
            )
            conn.commit()

    def mark_task_completed(self, task: ScrapingTask, output_path: Optional[Path]):
        path_str = str(output_path) if output_path else None
        with self.get_connection() as conn:
            conn.execute(
                "UPDATE scraping_tasks SET status = 'completed', completed_at = ?, output_path = ? WHERE id = ?",
                (datetime.utcnow().isoformat(), path_str, task.id),
            )
            conn.commit()

    def mark_task_failed(self, task: ScrapingTask, error: str, will_retry: bool):
        new_status = TaskStatus.RETRYING if will_retry else TaskStatus.FAILED
        completed_at = datetime.utcnow().isoformat() if not will_retry else None
        with self.get_connection() as conn:
            conn.execute(
                "UPDATE scraping_tasks SET status = ?, error_message = ?, attempts = ?, completed_at = ? WHERE id = ?",
                (new_status.value, error, task.attempts, completed_at, task.id),
            )
            conn.commit()

    def release_detail_tasks_for(self, main_task_key: str, dependency_path: Path) -> List[ScrapingTask]:
        """Desbloquea tareas de detalle que dependen de una tarea principal completada."""
        with self.get_connection() as conn:
            # Primero, encontramos las tareas a desbloquear
            rows = conn.execute(
                "SELECT * FROM scraping_tasks WHERE depends_on = ? AND status = 'blocked'",
                (main_task_key,)
            ).fetchall()
            
            if not rows:
                return []

            # Luego, las actualizamos
            task_ids_to_release = [row['id'] for row in rows]
            placeholders = ",".join("?" for _ in task_ids_to_release)
            conn.execute(
                f"UPDATE scraping_tasks SET status = 'pending', output_path = ? WHERE id IN ({placeholders})",
                (str(dependency_path), *task_ids_to_release)
            )
            conn.commit()
        
        # Devolvemos los objetos de tarea completos
        return [ScrapingTask.from_db_row(dict(row)) for row in rows]

    def get_dependency_path(self, main_task_key: str) -> Optional[Path]:
        """Obtiene la ruta de salida de una tarea principal para su tarea de detalle dependiente."""
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT output_path FROM scraping_tasks WHERE status = 'completed' AND depends_on = ?",
                (main_task_key,)
            ).fetchone()
        
        if row and row['output_path']:
            return Path(row['output_path'])
        
        # Fallback por si la lógica del scheduler se desfasa
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT output_path FROM scraping_tasks WHERE status = 'completed' AND task_key = ?",
                (main_task_key,)
            ).fetchone()

        return Path(row['output_path']) if row and row['output_path'] else None
