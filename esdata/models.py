"""Modelos de datos utilizados por el sistema de orquestación."""
from __future__ import annotations

from dataclasses import dataclass
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
        return {cls.COMPLETED, cls.FAILED}


@dataclass(slots=True)
class ScrapingTask:
    """Representa un trabajo individual de scraping."""

    scraper_name: str
    website: str
    city: str
    operation: str
    product: str
    url: str
    order: int
    batch_id: Optional[str] = None
    id: Optional[int] = None
    status: TaskStatus = TaskStatus.PENDING
    attempts: int = 0
    max_attempts: int = 3
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    website_code: Optional[str] = None
    city_code: Optional[str] = None
    operation_code: Optional[str] = None
    product_code: Optional[str] = None
    is_detail: bool = False
    depends_on: Optional[str] = None
    dependency_path: Optional[Path] = None
    output_path: Optional[Path] = None

    def task_key(self) -> str:
        """Cadena única para identificar el trabajo dentro del lote."""

        tokens = [
            self.scraper_name,
            self.website_code or self.website,
            self.city_code or self.city,
            self.operation_code or self.operation,
            self.product_code or self.product,
            str(self.order),
            "detail" if self.is_detail else "main",
        ]
        return "::".join(tokens)

    def expected_filename(self, month_year: str, execution_number: int) -> str:
        prefix = self.website_code or self.website
        city = self.city_code or self.city
        operation = self.operation_code or self.operation
        product = self.product_code or self.product
        suffix = f"{month_year}_{execution_number:02d}.csv"
        if self.is_detail:
            return f"{prefix}_{city}_{operation}_{product}_{suffix}"
        return f"{prefix}URL_{city}_{operation}_{product}_{suffix}"

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "batch_id": self.batch_id,
            "scraper_name": self.scraper_name,
            "website": self.website,
            "city": self.city,
            "operation": self.operation,
            "product": self.product,
            "url": self.url,
            "order": self.order,
            "status": self.status.value,
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
            "website_code": self.website_code,
            "city_code": self.city_code,
            "operation_code": self.operation_code,
            "product_code": self.product_code,
            "is_detail": int(self.is_detail),
            "depends_on": self.depends_on,
            "dependency_path": str(self.dependency_path) if self.dependency_path else None,
            "output_path": str(self.output_path) if self.output_path else None,
        }


@dataclass(slots=True)
class ExecutionBatch:
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
        return self.status == "completed"
