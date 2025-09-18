"""
Módulo de contexto para pasar información a los scrapers.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .configuration import ConfigManager
from ..models.main import ExecutionBatch, ScrapingTask


@dataclass
class ScraperContext:
    """
    Contenedor de datos para la información que un scraper necesita para ejecutarse.
    Se puede instanciar desde variables de entorno o desde una tarea de la base de datos.
    """
    scraper_name: str
    requires_gui: bool
    url: Optional[str]
    output_path: Path
    dependency_path: Optional[Path]
    base_dir: Path
    batch_id: str
    website_code: str
    city_code: str
    operation_code: str
    product_code: str

    @classmethod
    def from_env(cls) -> ScraperContext:
        """Crea el contexto a partir de variables de entorno (para ejecución manual)."""
        base_dir = Path(os.environ["SCRAPER_BASE_DIR"])
        dependency_path_str = os.environ.get("SCRAPER_DEPENDENCY_PATH")
        return cls(
            scraper_name=os.environ["SCRAPER_NAME"],
            requires_gui=os.environ.get("SCRAPER_REQUIRES_GUI", "False").lower() == "true",
            url=os.environ.get("SCRAPER_URL"),
            output_path=Path(os.environ["SCRAPER_OUTPUT_PATH"]),
            dependency_path=Path(dependency_path_str) if dependency_path_str else None,
            base_dir=base_dir,
            batch_id=os.environ["SCRAPER_BATCH_ID"],
            website_code=os.environ["SCRAPER_WEBSITE_CODE"],
            city_code=os.environ["SCRAPER_CITY_CODE"],
            operation_code=os.environ["SCRAPER_OPERATION_CODE"],
            product_code=os.environ["SCRAPER_PRODUCT_CODE"],
        )

    @classmethod
    def from_task(cls, task: ScrapingTask, batch: ExecutionBatch, config: ConfigManager) -> ScraperContext:
        """Crea el contexto a partir de una tarea y la configuración."""
        base_dir = config.base_dir
        base_data_path = base_dir / config.get("data.base_path")
        
        output_filename = task.expected_filename(batch.month_year, batch.execution_number)
        output_path = base_data_path / task.website_code / task.city_code / task.operation_code / task.product_code / batch.month_year / f"{batch.execution_number:02d}" / output_filename
        output_path.parent.mkdir(parents=True, exist_ok=True)

        scraper_settings = config.get(f"scraper_settings.{task.scraper_name}", {})
        requires_gui = scraper_settings.get("requires_gui", False)

        dependency_path = None
        if task.is_detail:
            dependency_scraper_name = config.get_dependency_scraper_name(task.scraper_name)
            if not dependency_scraper_name:
                raise ValueError(f"No se pudo determinar el scraper de dependencia para '{task.scraper_name}'")
            
            dependency_output_filename = ScraperContext.generate_output_filename(
                batch_id=batch.batch_id,
                scraper_name=dependency_scraper_name,
                task=task,
                is_detail=False
            )
            dependency_path = base_data_path / dependency_output_filename
        
        return cls(
            scraper_name=task.scraper_name,
            requires_gui=requires_gui,
            url=task.url,
            output_path=output_path,
            dependency_path=dependency_path,
            base_dir=base_dir,
            batch_id=batch.batch_id,
            website_code=task.website_code,
            city_code=task.city_code,
            operation_code=task.operation_code,
            product_code=task.product_code
        )

    def to_env_vars(self) -> dict[str, str]:
        """Convierte los atributos del contexto en un diccionario de variables de entorno."""
        env = {
            "SCRAPER_NAME": self.scraper_name,
            "SCRAPER_REQUIRES_GUI": str(self.requires_gui),
            "SCRAPER_URL": self.url,
            "SCRAPER_OUTPUT_PATH": str(self.output_path),
            "SCRAPER_DEPENDENCY_PATH": str(self.dependency_path) if self.dependency_path else "",
            "SCRAPER_BASE_DIR": str(self.base_dir),
            "SCRAPER_BATCH_ID": self.batch_id,
            "SCRAPER_WEBSITE_CODE": self.website_code,
            "SCRAPER_CITY_CODE": self.city_code,
            "SCRAPER_OPERATION_CODE": self.operation_code,
            "SCRAPER_PRODUCT_CODE": self.product_code,
        }
        return {k: v for k, v in env.items() if v is not None}

    @staticmethod
    def generate_output_filename(batch_id: str, scraper_name: str, task: ScrapingTask, is_detail: bool) -> str:
        """Genera un nombre de archivo de salida consistente."""
        suffix = "det" if is_detail else "url"
        return f"{batch_id}_{scraper_name}_{task.city_code}_{task.operation_code}_{task.product_code}_{suffix}.csv"
