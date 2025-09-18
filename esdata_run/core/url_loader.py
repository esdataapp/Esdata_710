"""Carga y normalización de URLs de scraping desde los CSV de entrada."""
from __future__ import annotations

import pandas as pd
from datetime import datetime
from typing import List
import logging
from pathlib import Path

from .configuration import ConfigManager
from ..models.main import ScrapingTask, TaskStatus

logger = logging.getLogger(__name__)


class UrlLoader:
    """Lee los CSV de la carpeta urls/ y los convierte en tareas normalizadas."""

    REQUIRED_COLUMNS = ["PaginaWeb", "Ciudad", "Operacion", "ProductoPaginaWeb", "URL"]

    def __init__(self, config: ConfigManager):
        self.config = config
        # Construir la ruta absoluta al directorio 'urls' desde la raíz del proyecto.
        # __file__ es esdata_run/core/url_loader.py
        # .parent.parent.parent es la raíz del proyecto.
        project_root = Path(__file__).resolve().parent.parent.parent
        self.urls_dir = project_root / config.get("data.urls_path")
        self.urls_dir = self.urls_dir.resolve()

    def available_scrapers(self) -> List[str]:
        """Devuelve los códigos de scraper basados en los archivos CSV de URLs."""
        if not self.urls_dir.exists():
            logger.error("El directorio de URLs no existe: %s", self.urls_dir)
            return []
            
        files = sorted(self.urls_dir.glob("*_urls.csv"))
        # Extrae el código, ej. "inm24" de "inm24_urls.csv"
        return [f.stem.replace("_urls", "") for f in files]

    def load(self, csv_name: str) -> List[ScrapingTask]:
        """
        Carga tareas desde un archivo CSV específico.
        'csv_name' es el nombre base del archivo, normalizado a minúsculas (ej. 'inmuebles24').
        """
        # El nombre del archivo CSV es el nombre base + "_urls.csv".
        csv_path = self.urls_dir / f"{csv_name.lower()}_urls.csv"
        
        if not csv_path.exists():
            logger.error("No se encontró el archivo CSV de URLs: %s", csv_path)
            return []
        
        try:
            df = pd.read_csv(csv_path, encoding="utf-8")
        except Exception as e:
            logger.error("Error al leer el archivo CSV %s: %s", csv_path, e)
            return []

        if not set(self.REQUIRED_COLUMNS).issubset(df.columns):
            missing = set(self.REQUIRED_COLUMNS) - set(df.columns)
            logger.error("El CSV %s no contiene las columnas requeridas: %s", csv_path, missing)
            return []

        max_attempts = int(self.config.get("execution.max_retry_attempts", 3))
        tasks: List[ScrapingTask] = []

        for index, row in df.iterrows():
            if row.isnull().all():
                continue

            # El scraper_name se asignará en el orquestador, aquí solo preparamos la tarea.
            url_value = row.get("URL")
            if not url_value or not isinstance(url_value, str):
                logger.warning("URL inválida o ausente en la fila %d del archivo %s. Saltando.", index, csv_path)
                continue

            task = ScrapingTask(
                # scraper_name se asignará más tarde
                url=url_value,
                order=index + 1,
                status=TaskStatus.PENDING,
                created_at=datetime.utcnow(),
                # Guardamos los datos originales para referencia
                context={
                    "PaginaWeb": row.get("PaginaWeb"),
                    "Ciudad": row.get("Ciudad"),
                    "Operacion": row.get("Operacion"),
                    "ProductoPaginaWeb": row.get("ProductoPaginaWeb"),
                },
                is_detail=False,
                max_attempts=max_attempts,
            )
            tasks.append(task)

        return tasks
