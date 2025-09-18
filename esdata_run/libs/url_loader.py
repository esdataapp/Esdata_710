"""Carga y normalización de URLs de scraping desde los CSV de entrada."""
from __future__ import annotations

import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import List
import logging

from .configuration import ConfigManager
from .models import ScrapingTask, TaskStatus

logger = logging.getLogger(__name__)


class UrlLoader:
    """Lee los CSV de la carpeta urls/ y los convierte en tareas normalizadas."""

    REQUIRED_COLUMNS = ["PaginaWeb", "Ciudad", "Operacion", "ProductoPaginaWeb", "URL"]

    def __init__(self, config: ConfigManager):
        self.config = config
        # La ruta ahora se construye desde la raíz del proyecto
        self.urls_dir = config.base_dir / config.get("data.urls_path")

    def available_scrapers(self) -> List[str]:
        """Devuelve los nombres de scraper basados en los archivos CSV de URLs."""
        files = sorted(self.urls_dir.glob("*_urls.csv"))
        # Extrae el nombre base, ej. "inmuebles24" de "inmuebles24_urls.csv"
        return [f.stem.replace("_urls", "") for f in files]

    def load(self, csv_name: str) -> List[ScrapingTask]:
        """
        Carga tareas desde un archivo CSV específico.
        'csv_name' es el nombre base del archivo, ej. 'Inmuebles24'.
        """
        csv_path = self.urls_dir / f"{csv_name}_urls.csv"
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
        website_mapping = self.config.get('website_mapping', {})

        for index, row in df.iterrows():
            # Normaliza los valores del CSV a códigos internos
            raw_website = row.get("PaginaWeb")
            
            # Usa el mapeo para obtener el código corto (ej. "Inm24")
            website_code = website_mapping.get(raw_website)
            if not website_code:
                logger.warning("No se encontró mapeo para el sitio web '%s' en la fila %d del archivo %s. Saltando tarea.", raw_website, index + 2, csv_path.name)
                continue

            city_code = row.get("Ciudad")
            operation_code = row.get("Operacion")
            product_code = row.get("ProductoPaginaWeb")
            url_value = str(row.get("URL") or "").strip()

            if not url_value:
                logger.warning("URL vacía en la fila %d del archivo %s. Saltando tarea.", index + 2, csv_path.name)
                continue

            task = ScrapingTask(
                # El nombre del scraper es el código corto, ej. "inm24"
                scraper_name=website_code.lower(),
                website=website_code,
                city=city_code,
                operation=operation_code,
                product=product_code,
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

            # Comprueba si este sitio tiene un scraper de detalle asociado
            website_config = self.config.get(f"websites.{website_code}", {})
            if website_config.get("has_detail_scraper"):
                detail_scraper_name = website_config.get("detail_scraper_name")
                if not detail_scraper_name:
                    logger.error("El scraper '%s' está configurado con 'has_detail_scraper' pero falta 'detail_scraper_name'.", website_code)
                    continue
                
                detail_task = ScrapingTask(
                    scraper_name=detail_scraper_name.lower(),
                    website=website_code,
                    city=city_code,
                    operation=operation_code,
                    product=product_code,
                    url=url_value, # La URL original se pasa como referencia
                    order=index + 1,
                    status=TaskStatus.BLOCKED, # Bloqueada hasta que la principal termine
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
