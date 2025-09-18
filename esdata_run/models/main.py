"""Modelos de datos utilizados por el sistema de orquestación."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional


class TaskStatus(str, Enum):
    """Estados de ejecución soportados por la plataforma."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    BLOCKED = "blocked"

    @classmethod
    def terminal_states(cls) -> set["TaskStatus"]:
        """Estados que se consideran finales y no volverán a ejecutarse."""
        return {cls.COMPLETED, cls.FAILED}


@dataclass(slots=True)
class ScrapingTask:
    """Representa un trabajo individual de scraping, mapeado a la tabla de la BD."""

    # --- Campos Requeridos (sin valor por defecto) ---
    scraper_name: str
    url: str
    order: int
    website_code: str
    city_code: str
    operation_code: str
    product_code: str
    created_at: datetime

    # --- Campos Opcionales (con valor por defecto) ---
    status: TaskStatus = TaskStatus.PENDING
    attempts: int = 0
    max_attempts: int = 3
    batch_id: Optional[str] = None
    is_detail: bool = False
    depends_on: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    output_path: Optional[str] = None
    id: Optional[int] = None

    def task_key(self) -> str:
        """
        Cadena única para identificar la tarea dentro del lote.
        Es fundamental para la lógica de dependencias.
        """
        suffix = "detail" if self.is_detail else "main"
        return f"{self.batch_id}::{self.website_code}::{self.city_code}::{self.operation_code}::{self.product_code}::{self.order}::{suffix}"

    def expected_filename(self, month_year: str, execution_number: int) -> str:
        """
        Genera el nombre de archivo CSV esperado según las especificaciones.
        Ej: Inm24URL_Gdl_Ven_Dep_sep25_01.csv (principal)
        Ej: Inm24_Gdl_Ven_Dep_sep25_01.csv (detalle)
        """
        base_name = f"{self.website_code}_{self.city_code}_{self.operation_code}_{self.product_code}"
        suffix = f"{month_year}_{execution_number:02d}.csv"
        
        if self.is_detail:
            return f"{base_name}_{suffix}"
        
        # Para las tareas principales, se añade "URL"
        return f"{self.website_code}URL_{self.city_code}_{self.operation_code}_{self.product_code}_{suffix}"

    def to_db_dict(self) -> dict[str, object]:
        """Convierte el objeto a un diccionario para inserción/actualización en la BD."""
        data = asdict(self)
        # Convierte tipos no nativos de SQLite a strings o ints
        data['status'] = self.status.value
        data['is_detail'] = int(self.is_detail)
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()
            elif isinstance(value, Path):
                data[key] = str(value)
        return data

    @classmethod
    def from_db_row(cls, row: dict) -> "ScrapingTask":
        """Crea una instancia de ScrapingTask desde una fila de la base de datos."""
        # Convierte valores de la BD a los tipos correctos del dataclass
        for key, value in row.items():
            if key in ('created_at', 'started_at', 'completed_at') and value:
                row[key] = datetime.fromisoformat(value)
        
        row['status'] = TaskStatus(row['status'])
        row['is_detail'] = bool(row['is_detail'])
        
        # El modelo original tenía más campos, nos aseguramos de no pasar extras
        field_names = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_row = {k: v for k, v in row.items() if k in field_names}

        return cls(**filtered_row)


@dataclass(slots=True)
class ExecutionBatch:
    """Representa un lote de ejecución (ej. la primera quincena de sep25)."""
    batch_id: str
    month_year: str
    execution_number: int
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0

    def is_finished(self) -> bool:
        return self.status in ("completed", "failed")

    @classmethod
    def from_db_row(cls, row: dict) -> "ExecutionBatch":
        """Crea una instancia desde una fila de la base de datos."""
        for key, value in row.items():
            if key in ('started_at', 'completed_at') and value:
                row[key] = datetime.fromisoformat(value)
        return cls(**row)
