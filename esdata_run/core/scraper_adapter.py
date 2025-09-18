"""Adaptador responsable de ejecutar los scrapers dentro del orquestador."""
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from .configuration import ConfigManager
from .context import ScraperContext
from ..models.main import ExecutionBatch, ScrapingTask

logger = logging.getLogger(__name__)


class ScraperExecutionError(RuntimeError):
    """Error lanzado cuando un scraper no genera la salida esperada."""


class ScraperAdapter:
    """Carga dinámica de scrapers y preparación de variables de entorno."""

    def __init__(self, base_dir: Path, config: ConfigManager):
        self.base_dir = base_dir
        self.config = config
        self._last_context: Optional[ScraperContext] = None

    def get_last_context(self) -> Optional[ScraperContext]:
        """Devuelve el último contexto de scraper utilizado."""
        return self._last_context

    def run(
        self,
        task: ScrapingTask,
        batch: ExecutionBatch
    ) -> tuple[bool, str]:
        """
        Prepara y ejecuta un scraper como un subproceso, manejando su entorno,
        salida y posibles errores.
        """
        config = self.config
        try:
            context = ScraperContext.from_task(task, batch, config)
            self._last_context = context
        except ValueError as e:
            logger.error(f"No se pudo crear el contexto para la tarea {task.id}: {e}")
            return False, str(e)

        # Construir el comando de ejecución
        python_executable = sys.executable
        scraper_script_path = config.get_scraper_script_path(task.scraper_name)

        if not scraper_script_path or not scraper_script_path.exists():
            logger.error(f"No se encontró el script para el scraper '{task.scraper_name}' en la ruta esperada: {scraper_script_path}")
            return False, "Script no encontrado"

        # Preparar el entorno para el subproceso
        env = os.environ.copy()
        env.update(context.to_env_vars())
        
        command = [python_executable, str(scraper_script_path)]

        # Decidir si usar xvfb basado en la configuración
        if context.requires_gui:
            logger.info(f"El scraper '{task.scraper_name}' requiere GUI. Usando xvfb-run.")
            command.insert(0, "xvfb-run")

        logger.info(f"Ejecutando comando: {' '.join(command)}")

        try:
            # Usamos Popen para un mejor control del proceso y logs en tiempo real
            process = subprocess.Popen(
                command,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8'
            )

            # Log en tiempo real
            if process.stdout:
                for line in iter(process.stdout.readline, ''):
                    logger.info(f"[{task.scraper_name}] {line.strip()}")
            
            process.wait() # Esperar a que el proceso termine

            if process.returncode == 0:
                # Verificar que el archivo de salida se haya creado y no esté vacío
                if not context.output_path.exists() or context.output_path.stat().st_size == 0:
                    error_msg = f"El scraper '{task.scraper_name}' se ejecutó pero no generó un archivo de salida válido en {context.output_path}."
                    logger.error(error_msg)
                    return False, error_msg
                
                logger.info(f"El scraper '{task.scraper_name}' se ejecutó exitosamente.")
                return True, "Ejecución exitosa"
            else:
                error_msg = f"El scraper '{task.scraper_name}' finalizó con código de error {process.returncode}."
                logger.error(error_msg)
                return False, error_msg

        except FileNotFoundError:
            error_msg = "Comando 'xvfb-run' no encontrado. Asegúrate de que esté instalado (sudo apt-get install xvfb)."
            logger.critical(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Fallo catastrófico al ejecutar el scraper '{task.scraper_name}': {e}"
            logger.critical(error_msg, exc_info=True)
            return False, error_msg
