"""Módulo de persistencia y utilidades de acceso a SQLite."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterable, Iterator, List, Optional, Sequence

from .models import ExecutionBatch, ScrapingTask, TaskStatus


def _row_to_batch(row: sqlite3.Row) -> ExecutionBatch:
    return ExecutionBatch(
        batch_id=row["batch_id"],
        month_year=row["month_year"],
        execution_number=row["execution_number"],
        status=row["status"],
        started_at=datetime.fromisoformat(row["started_at"]),
        completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
        total_tasks=row["total_tasks"] or 0,
        completed_tasks=row["completed_tasks"] or 0,
        failed_tasks=row["failed_tasks"] or 0,
    )


class TaskRepository:
    """Gestor de base de datos para tareas de scraping."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        if not self.db_path.is_absolute():
            self.db_path = self.db_path.resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    # ------------------------------------------------------------------
    # Conexiones
    # ------------------------------------------------------------------
    @contextmanager
    def get_connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=30000")
        try:
            yield conn
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------
    def _ensure_schema(self) -> None:
        with self.get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS execution_batches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    batch_id TEXT UNIQUE NOT NULL,
                    month_year TEXT NOT NULL,
                    execution_number INTEGER NOT NULL,
                    started_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    completed_at TEXT,
                    total_tasks INTEGER,
                    completed_tasks INTEGER DEFAULT 0,
                    failed_tasks INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'running'
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS scraping_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    batch_id TEXT NOT NULL,
                    execution_batch TEXT NOT NULL,
                    scraper_name TEXT NOT NULL,
                    website TEXT NOT NULL,
                    city TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    product TEXT NOT NULL,
                    website_code TEXT,
                    city_code TEXT,
                    operation_code TEXT,
                    product_code TEXT,
                    url TEXT NOT NULL,
                    order_num INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    attempts INTEGER DEFAULT 0,
                    max_attempts INTEGER DEFAULT 3,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    started_at TEXT,
                    completed_at TEXT,
                    error_message TEXT,
                    output_path TEXT,
                    is_detail INTEGER DEFAULT 0,
                    depends_on TEXT,
                    dependency_path TEXT,
                    task_key TEXT
                )
                """
            )
            self._ensure_column(conn, "scraping_tasks", "batch_id", "TEXT")
            self._ensure_column(conn, "scraping_tasks", "website_code", "TEXT")
            self._ensure_column(conn, "scraping_tasks", "city_code", "TEXT")
            self._ensure_column(conn, "scraping_tasks", "operation_code", "TEXT")
            self._ensure_column(conn, "scraping_tasks", "product_code", "TEXT")
            self._ensure_column(conn, "scraping_tasks", "is_detail", "INTEGER DEFAULT 0")
            self._ensure_column(conn, "scraping_tasks", "depends_on", "TEXT")
            self._ensure_column(conn, "scraping_tasks", "dependency_path", "TEXT")
            self._ensure_column(conn, "scraping_tasks", "task_key", "TEXT")
            self._ensure_column(conn, "scraping_tasks", "output_path", "TEXT")
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_tasks_batch_status
                ON scraping_tasks(batch_id, status)
                """
            )
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_tasks_unique
                ON scraping_tasks(batch_id, task_key)
                """
            )
            conn.commit()

    def _ensure_column(self, conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
        info = conn.execute(f"PRAGMA table_info({table})").fetchall()
        columns = {row[1] for row in info}
        if column not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

    # ------------------------------------------------------------------
    # Batches
    # ------------------------------------------------------------------
    def find_open_batch(self) -> Optional[ExecutionBatch]:
        with self.get_connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM execution_batches
                WHERE status IN ('running', 'created')
                ORDER BY started_at DESC LIMIT 1
                """
            ).fetchone()
            if row:
                return _row_to_batch(row)
        return None

    def batch_by_id(self, batch_id: str) -> Optional[ExecutionBatch]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM execution_batches WHERE batch_id = ?", (batch_id,)).fetchone()
        return _row_to_batch(row) if row else None

    def next_execution_number(self, month_year: str, desired: int) -> int:
        with self.get_connection() as conn:
            rows = conn.execute("SELECT execution_number FROM execution_batches WHERE month_year = ?", (month_year,)).fetchall()
        taken = {row["execution_number"] for row in rows}
        candidate = desired
        while candidate in taken:
            candidate += 1
        return candidate

    def create_batch(self, batch_id: str, month_year: str, execution_number: int, total_tasks: int) -> ExecutionBatch:
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO execution_batches
                    (batch_id, month_year, execution_number, started_at, total_tasks, status)
                VALUES (?, ?, ?, COALESCE((SELECT started_at FROM execution_batches WHERE batch_id = ?), CURRENT_TIMESTAMP), ?, 'running')
                """
                ,
                (batch_id, month_year, execution_number, batch_id, total_tasks, total_tasks),
            )
            conn.commit()
        batch = self.batch_by_id(batch_id)
        if batch is None:
            raise RuntimeError(f"No se pudo crear el lote {batch_id}")
        return batch

    def update_batch_progress(self, batch_id: str, completed_delta: int = 0, failed_delta: int = 0) -> None:
        with self.get_connection() as conn:
            conn.execute(
                """
                UPDATE execution_batches
                SET completed_tasks = COALESCE(completed_tasks, 0) + ?,
                    failed_tasks = COALESCE(failed_tasks, 0) + ?
                WHERE batch_id = ?
                """,
                (completed_delta, failed_delta, batch_id),
            )
            conn.commit()

    def mark_batch_completed(self, batch_id: str) -> None:
        with self.get_connection() as conn:
            conn.execute(
                """
                UPDATE execution_batches
                SET status = 'completed', completed_at = CURRENT_TIMESTAMP
                WHERE batch_id = ?
                """,
                (batch_id,),
            )
            conn.commit()

    # ------------------------------------------------------------------
    # Tareas
    # ------------------------------------------------------------------
    def insert_tasks(self, batch_id: str, tasks: Sequence[ScrapingTask]) -> None:
        if not tasks:
            return
        with self.get_connection() as conn:
            for task in tasks:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO scraping_tasks (
                        batch_id, execution_batch, scraper_name, website, city, operation,
                        product, website_code, city_code, operation_code, product_code, url, order_num, status, attempts, max_attempts,
                        created_at, is_detail, depends_on, task_key
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?)
                    """,
                    (
                        batch_id,
                        batch_id,
                        task.scraper_name,
                        task.website,
                        task.city,
                        task.operation,
                        task.product,
                        task.website_code,
                        task.city_code,
                        task.operation_code,
                        task.product_code,
                        task.url,
                        task.order,
                        task.status.value,
                        task.attempts,
                        task.max_attempts,
                        1 if task.is_detail else 0,
                        task.depends_on,
                        task.task_key(),
                    ),
                )
            conn.commit()

    def reset_running_tasks(self, batch_id: str) -> None:
        with self.get_connection() as conn:
            conn.execute(
                """
                UPDATE scraping_tasks
                SET status = 'pending', started_at = NULL
                WHERE batch_id = ? AND status = 'running'
                """,
                (batch_id,),
            )
            conn.commit()

    def tasks_by_status(self, batch_id: str, statuses: Sequence[TaskStatus]) -> list[ScrapingTask]:
        status_values = [status.value for status in statuses]
        placeholders = ",".join("?" for _ in status_values)
        query = f"""
            SELECT * FROM scraping_tasks
            WHERE batch_id = ? AND status IN ({placeholders})
            ORDER BY order_num ASC
        """
        with self.get_connection() as conn:
            rows = conn.execute(query, (batch_id, *status_values)).fetchall()
        return [self._row_to_task(row) for row in rows]

    def all_tasks(self, batch_id: str) -> list[ScrapingTask]:
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM scraping_tasks WHERE batch_id = ? ORDER BY order_num ASC",
                (batch_id,),
            ).fetchall()
        return [self._row_to_task(row) for row in rows]

    def pending_counts(self, batch_id: str) -> dict[str, int]:
        with self.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT scraper_name, COUNT(*) as total
                FROM scraping_tasks
                WHERE batch_id = ? AND status IN ('pending', 'retrying', 'blocked')
                GROUP BY scraper_name
                """,
                (batch_id,),
            ).fetchall()
        return {row["scraper_name"]: row["total"] for row in rows}

    def next_task_for_site(self, batch_id: str, scraper_name: str) -> Optional[ScrapingTask]:
        with self.get_connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM scraping_tasks
                WHERE batch_id = ? AND scraper_name = ?
                  AND status IN ('pending', 'retrying')
                ORDER BY order_num ASC
                LIMIT 1
                """,
                (batch_id, scraper_name),
            ).fetchone()
        if row:
            return self._row_to_task(row)
        return None

    def detail_tasks_ready(self, batch_id: str) -> list[ScrapingTask]:
        with self.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM scraping_tasks
                WHERE batch_id = ? AND is_detail = 1 AND status = 'pending'
                ORDER BY order_num ASC
                """,
                (batch_id,),
            ).fetchall()
        return [self._row_to_task(row) for row in rows]

    def mark_task_running(self, task: ScrapingTask) -> None:
        with self.get_connection() as conn:
            conn.execute(
                """
                UPDATE scraping_tasks
                SET status = 'running', started_at = CURRENT_TIMESTAMP, attempts = COALESCE(attempts, 0)
                WHERE batch_id = ? AND task_key = ?
                """,
                (task.batch_id, task.task_key()),
            )
            conn.commit()

    def mark_task_completed(self, task: ScrapingTask, output_path: Optional[Path]) -> None:
        with self.get_connection() as conn:
            conn.execute(
                """
                UPDATE scraping_tasks
                SET status = 'completed', completed_at = CURRENT_TIMESTAMP, output_path = ?
                WHERE batch_id = ? AND task_key = ?
                """,
                (str(output_path) if output_path else None, task.batch_id, task.task_key()),
            )
            conn.commit()

    def mark_task_failed(self, task: ScrapingTask, error: str, will_retry: bool) -> None:
        status = 'retrying' if will_retry else 'failed'
        with self.get_connection() as conn:
            conn.execute(
                """
                UPDATE scraping_tasks
                SET status = ?, error_message = ?, attempts = attempts + 1,
                    completed_at = CASE WHEN ? = 'failed' THEN CURRENT_TIMESTAMP ELSE completed_at END
                WHERE batch_id = ? AND task_key = ?
                """,
                (status, error, status, task.batch_id, task.task_key()),
            )
            conn.commit()

    def release_detail_tasks(self, main_task: ScrapingTask, dependency_path: Path) -> list[ScrapingTask]:
        with self.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM scraping_tasks
                WHERE batch_id = ? AND depends_on = ? AND is_detail = 1 AND status = 'blocked'
                """,
                (main_task.batch_id, main_task.task_key()),
            ).fetchall()
            if not rows:
                return []
            conn.execute(
                """
                UPDATE scraping_tasks
                SET status = 'pending', dependency_path = ?
                WHERE batch_id = ? AND depends_on = ? AND is_detail = 1 AND status = 'blocked'
                """,
                (str(dependency_path), main_task.batch_id, main_task.task_key()),
            )
            conn.commit()
        return [self._row_to_task(row) for row in rows]

    def blocked_detail_tasks(self, batch_id: str) -> list[ScrapingTask]:
        with self.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM scraping_tasks
                WHERE batch_id = ? AND is_detail = 1 AND status = 'blocked'
                """,
                (batch_id,),
            ).fetchall()
        return [self._row_to_task(row) for row in rows]

    def remaining_task_count(self, batch_id: str) -> int:
        with self.get_connection() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) as remaining
                FROM scraping_tasks
                WHERE batch_id = ? AND status NOT IN ('completed', 'failed')
                """,
                (batch_id,),
            ).fetchone()
        return row["remaining"] if row else 0

    def task_exists(self, batch_id: str, task_key: str) -> bool:
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM scraping_tasks WHERE batch_id = ? AND task_key = ?",
                (batch_id, task_key),
            ).fetchone()
        return bool(row)

    def fetch_task(self, batch_id: str, task_key: str) -> Optional[ScrapingTask]:
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM scraping_tasks WHERE batch_id = ? AND task_key = ?",
                (batch_id, task_key),
            ).fetchone()
        if row:
            return self._row_to_task(row)
        return None

    # ------------------------------------------------------------------
    def _row_to_task(self, row: sqlite3.Row) -> ScrapingTask:
        task = ScrapingTask(
            scraper_name=row["scraper_name"],
            website=row["website"],
            city=row["city"],
            operation=row["operation"],
            product=row["product"],
            url=row["url"],
            order=row["order_num"],
            batch_id=row["batch_id"],
            id=row["id"],
            status=TaskStatus(row["status"]),
            attempts=row["attempts"],
            max_attempts=row["max_attempts"],
            website_code=row["website_code"] if "website_code" in row.keys() else None,
            city_code=row["city_code"] if "city_code" in row.keys() else None,
            operation_code=row["operation_code"] if "operation_code" in row.keys() else None,
            product_code=row["product_code"] if "product_code" in row.keys() else None,
            is_detail=bool(row["is_detail"]),
            depends_on=row["depends_on"],
        )
        if row["dependency_path"]:
            task.dependency_path = Path(row["dependency_path"])
        if row["output_path"]:
            task.output_path = Path(row["output_path"])
        return task
