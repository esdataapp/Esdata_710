"""Adaptador responsable de ejecutar los scrapers dentro del orquestador."""
from __future__ import annotations

import importlib.util
import logging
import os
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType
from typing import Optional

from esdata.configuration import ConfigManager
from esdata.models import ExecutionBatch, ScrapingTask

logger = logging.getLogger(__name__)


class ScraperExecutionError(RuntimeError):
    """Error lanzado cuando un scraper no genera la salida esperada."""


class ScraperAdapter:
    """Carga dinámica de scrapers y preparación de variables de entorno."""

    def __init__(self, base_dir: Path, config: ConfigManager):
        self.base_dir = Path(base_dir)
        self.config = config
        self.scrapers_dir = self.base_dir / self.config.raw["scrapers"]["path"]
        self.scrapers_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    def run(
        self,
        task: ScrapingTask,
        output_file: Path,
        dependency_path: Optional[Path] = None,
        batch: Optional[ExecutionBatch] = None,
    ) -> Path:
        """Ejecuta el scraper indicado y devuelve la ruta final generada."""

        script_path = self.scrapers_dir / f"{task.scraper_name}.py"
        if not script_path.exists():
            raise ScraperExecutionError(f"Scraper no encontrado: {script_path}")
        if task.is_detail and dependency_path and not dependency_path.exists():
            raise ScraperExecutionError(
                f"Archivo de dependencia no disponible: {dependency_path}"
            )

        module = self._load_module(script_path)
        with self._temporary_workdir(self.scrapers_dir):
            with self._patched_environment(task, output_file, dependency_path, batch):
                self._invoke_scraper(module, output_file)
        return self._ensure_output_file(task, output_file)

    # ------------------------------------------------------------------
    def _load_module(self, script_path: Path) -> ModuleType:
        spec = importlib.util.spec_from_file_location(script_path.stem, script_path)
        if spec is None or spec.loader is None:
            raise ScraperExecutionError(
                f"No se pudo cargar el módulo del scraper: {script_path}"
            )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore[assignment]
        return module

    @contextmanager
    def _temporary_workdir(self, path: Path):
        original = Path.cwd()
        os.chdir(path)
        try:
            yield
        finally:
            os.chdir(original)

    @contextmanager
    def _patched_environment(
        self,
        task: ScrapingTask,
        output_file: Path,
        dependency_path: Optional[Path],
        batch: Optional[ExecutionBatch],
    ):
        updates = {
            "SCRAPER_MODE": "detail" if task.is_detail else "url",
            "SCRAPER_OUTPUT_FILE": str(output_file),
            "SCRAPER_BASE_DIR": str(self.base_dir),
            "SCRAPER_BATCH_ID": batch.batch_id if batch else "",
            "SCRAPER_WEBSITE": task.website,
            "SCRAPER_WEBSITE_CODE": task.website_code or task.website,
            "SCRAPER_CITY": task.city,
            "SCRAPER_CITY_CODE": task.city_code or task.city,
            "SCRAPER_OPERATION": task.operation,
            "SCRAPER_OPERATION_CODE": task.operation_code or task.operation,
            "SCRAPER_PRODUCT": task.product,
            "SCRAPER_PRODUCT_CODE": task.product_code or task.product,
            "SCRAPER_INPUT_URL": task.url or "",
        }
        if dependency_path:
            updates["SCRAPER_URL_LIST_FILE"] = str(dependency_path)
        try:
            website_code = task.website_code or task.website
            site_cfg = self.config.website_config(website_code)
            if "max_pages_per_session" in site_cfg:
                updates["SCRAPER_MAX_PAGES"] = str(
                    site_cfg.get("max_pages_per_session")
                )
            if "rate_limit_seconds" in site_cfg:
                updates["SCRAPER_RATE_LIMIT"] = str(site_cfg.get("rate_limit_seconds"))
        except Exception:
            pass

        previous_values = {key: os.environ.get(key) for key in updates}
        os.environ.update({k: v for k, v in updates.items() if v is not None})

        try:
            yield
        finally:
            for key, value in previous_values.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def _invoke_scraper(self, module: ModuleType, output_file: Path) -> None:
        if hasattr(module, "DDIR"):
            setattr(module, "DDIR", str(output_file.parent) + os.sep)  # type: ignore[attr-defined]
        if hasattr(module, "main") and callable(module.main):  # type: ignore[attr-defined]
            module.main()  # type: ignore[attr-defined]
        else:
            raise ScraperExecutionError(
                "El scraper no expone una función main() ejecutable"
            )

    def _ensure_output_file(self, task: ScrapingTask, output_file: Path) -> Path:
        if output_file.exists():
            return output_file
        raise ScraperExecutionError(
            f"El scraper {task.scraper_name} no generó la salida esperada en {output_file}"
        )
