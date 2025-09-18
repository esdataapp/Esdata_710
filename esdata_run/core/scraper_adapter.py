"""Adaptador responsable de ejecutar los scrapers dentro del orquestador."""
from __future__ import annotations

import importlib.util
import logging
import os
import subprocess
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType
from typing import Optional

from libs.configuration import ConfigManager
from libs.models import ExecutionBatch, ScrapingTask

logger = logging.getLogger(__name__)


class ScraperExecutionError(RuntimeError):
    """Error lanzado cuando un scraper no genera la salida esperada."""


class ScraperAdapter:
    """Carga dinámica de scrapers y preparación de variables de entorno."""

    def __init__(self, base_dir: Path, config: ConfigManager):
        self.base_dir = base_dir
        self.config = config
        self.scrapers_dir = self.base_dir / self.config.get("scrapers.path")
        self.scrapers_dir.mkdir(parents=True, exist_ok=True)

    def run(
        self,
        task: ScrapingTask,
        output_file: Path,
        dependency_path: Optional[Path] = None,
        batch: Optional[ExecutionBatch] = None,
    ) -> Path:
        """Ejecuta el scraper indicado como un subproceso y devuelve la ruta final generada."""
        script_path = self.scrapers_dir / f"{task.scraper_name}.py"
        if not script_path.exists():
            raise ScraperExecutionError(f"Scraper no encontrado: {script_path}")

        if task.is_detail and dependency_path and not dependency_path.exists():
            raise ScraperExecutionError(
                f"Archivo de dependencia para scraper de detalle no disponible: {dependency_path}"
            )

        # Prepara el entorno para el subproceso
        env = self._prepare_environment(task, output_file, dependency_path, batch)
        
        python_executable = self.config.get("scrapers.python_executable", "python3")
        command = [python_executable, str(script_path)]
        
        logger.info("Ejecutando comando: %s", " ".join(command))
        logger.debug("Entorno para el scraper: %s", env)

        try:
            # Usar Popen para capturar stdout y stderr en tiempo real
            process = subprocess.Popen(
                command,
                env=env,
                cwd=self.scrapers_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8'
            )

            # Loggear la salida del scraper en tiempo real
            if process.stdout:
                for line in iter(process.stdout.readline, ''):
                    logger.info("[scraper:%s] %s", task.scraper_name, line.strip())
            
            process.wait() # Esperar a que el proceso termine

            if process.returncode != 0:
                stderr_output = process.stderr.read() if process.stderr else "No stderr output"
                logger.error(
                    "El scraper %s finalizó con código de error %d. Stderr: %s",
                    task.scraper_name, process.returncode, stderr_output.strip()
                )
                raise ScraperExecutionError(
                    f"El scraper {task.scraper_name} falló. Ver logs para más detalles."
                )

        except FileNotFoundError:
            logger.error("No se encontró el ejecutable de Python: %s", python_executable)
            raise ScraperExecutionError(f"Intérprete de Python '{python_executable}' no encontrado.")
        except Exception as e:
            logger.error("Ocurrió una excepción al ejecutar el scraper %s: %s", task.scraper_name, e)
            raise ScraperExecutionError(f"Fallo en la ejecución del scraper {task.scraper_name}.")

        return self._ensure_output_file(task, output_file)

    def _prepare_environment(
        self,
        task: ScrapingTask,
        output_file: Path,
        dependency_path: Optional[Path],
        batch: Optional[ExecutionBatch],
    ) -> dict:
        """Crea un diccionario de entorno para el subproceso del scraper."""
        env = os.environ.copy()
        
        # Asegurarse de que PYTHONPATH incluya el directorio raíz del proyecto
        # para que los scrapers puedan importar módulos de 'libs'
        project_root = self.base_dir.parent
        python_path = env.get("PYTHONPATH", "")
        if str(project_root) not in python_path:
            env["PYTHONPATH"] = f"{project_root}{os.pathsep}{python_path}"

        updates = {
            "SCRAPER_MODE": "detail" if task.is_detail else "url",
            "SCRAPER_OUTPUT_FILE": str(output_file),
            "SCRAPER_BASE_DIR": str(self.base_dir),
            "SCRAPER_BATCH_ID": batch.batch_id if batch else "",
            "SCRAPER_WEBSITE_CODE": task.website_code,
            "SCRAPER_CITY_CODE": task.city_code,
            "SCRAPER_OPERATION_CODE": task.operation_code,
            "SCRAPER_PRODUCT_CODE": task.product_code,
            "SCRAPER_INPUT_URL": task.url or "",
        }
        if dependency_path:
            updates["SCRAPER_URL_LIST_FILE"] = str(dependency_path)

        # Añadir configuraciones específicas del sitio desde config.yaml
        try:
            site_cfg = self.config.get(f"websites.{task.website_code}", {})
            if "max_pages_per_session" in site_cfg:
                updates["SCRAPER_MAX_PAGES"] = str(site_cfg["max_pages_per_session"])
            if "rate_limit_seconds" in site_cfg:
                updates["SCRAPER_RATE_LIMIT"] = str(site_cfg["rate_limit_seconds"])
        except Exception as e:
            logger.warning("No se pudo cargar la configuración específica para el sitio %s: %s", task.website_code, e)

        env.update({k: v for k, v in updates.items() if v is not None})
        return env

    def _ensure_output_file(self, task: ScrapingTask, output_file: Path) -> Path:
        """Verifica que el scraper haya generado el archivo de salida esperado."""
        if output_file.exists() and output_file.stat().st_size > 0:
            logger.info("El scraper %s generó el archivo de salida %s correctamente.", task.scraper_name, output_file)
            return output_file
        
        # Ya no creamos placeholders. Si el archivo no existe o está vacío, es un error.
        logger.error("El scraper %s no generó la salida esperada en %s (archivo no existe o está vacío).", task.scraper_name, output_file)
        raise ScraperExecutionError(
            f"El scraper {task.scraper_name} no generó un archivo de salida válido en {output_file}"
        )
