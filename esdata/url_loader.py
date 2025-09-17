"""Carga y normalización de URLs de scraping desde los CSV de entrada."""
from __future__ import annotations

import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import List

from .configuration import ConfigManager
from .models import ScrapingTask, TaskStatus


class UrlLoader:
    """Lee los CSV de la carpeta urls/ y los convierte en tareas normalizadas."""

    REQUIRED_COLUMNS = ["PaginaWeb", "Ciudad", "Operacion", "ProductoPaginaWeb", "URL"]

    def __init__(self, config: ConfigManager):
        self.config = config
        self.urls_dir = config.urls_path()

    def available_scrapers(self) -> List[str]:
        files = sorted(self.urls_dir.glob("*_urls.csv"))
        return [f.stem.lower() for f in files]

    def load(self, scraper_name: str) -> List[ScrapingTask]:
        csv_path = self.urls_dir / f"{scraper_name.lower()}_urls.csv"
        if not csv_path.exists():
            return []
        df = pd.read_csv(csv_path, encoding="utf-8")
        if not set(self.REQUIRED_COLUMNS).issubset(df.columns):
            missing = set(self.REQUIRED_COLUMNS) - set(df.columns)
            raise ValueError(f"CSV {csv_path} no contiene columnas requeridas: {missing}")

        max_attempts = int(self.config.execution_settings().get("max_retry_attempts", 3))
        tasks: List[ScrapingTask] = []

        for index, row in df.iterrows():
            website_code, website_value = self.config.normalize("websites", row.get("PaginaWeb"))
            city_code, city_value = self.config.normalize("cities", row.get("Ciudad"))
            operation_code, operation_value = self.config.normalize("operations", row.get("Operacion"))
            product_code, product_value = self.config.normalize("products", row.get("ProductoPaginaWeb"))
            url_value = str(row.get("URL") or "").strip()

            task = ScrapingTask(
                scraper_name=scraper_name.lower(),
                website=website_value,
                city=city_value,
                operation=operation_value,
                product=product_value,
                url=url_value,
                order=index + 1,
                status=TaskStatus.PENDING,
                max_attempts=max_attempts,
                created_at=datetime.utcnow(),
                website_code=website_code,
                city_code=city_code,
                operation_code=operation_code,
                product_code=product_code,
            )
            tasks.append(task)

            detail_name = self.config.detail_scraper_for(website_code)
            if detail_name:
                detail_task = ScrapingTask(
                    scraper_name=detail_name.lower(),
                    website=website_value,
                    city=city_value,
                    operation=operation_value,
                    product=product_value,
                    url=url_value,
                    order=index + 1,
                    status=TaskStatus.BLOCKED,
                    max_attempts=max_attempts,
                    created_at=datetime.utcnow(),
                    website_code=website_code,
                    city_code=city_code,
                    operation_code=operation_code,
                    product_code=product_code,
                    is_detail=True,
                    depends_on=task.task_key(),
                )
                tasks.append(detail_task)

        return tasks
