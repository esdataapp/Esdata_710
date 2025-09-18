"""Ejecución yfrom .configuration import ConfigManager
from .database import TaskRepository
from ..models.main import ExecutionBatch, ScrapingTask, TaskStatus
from .resource_monitor import ResourceLimiter
from .scraper_adapter import ScraperAdapterdinación de tareas de scraping."""
from __future__ import annotations

import asyncio
import logging
import heapq
import itertools
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import monotonic
from typing import Deque, Dict, List, Optional

from .configuration import ConfigManager
from .database import TaskRepository
from ..models.main import ExecutionBatch, ScrapingTask, TaskStatus
from .resource_monitor import ResourceLimiter
from .scraper_adapter import ScraperAdapter # Corregido

logger = logging.getLogger(__name__)


@dataclass
class TaskExecutionResult:
    task: ScrapingTask
    success: bool
    output_path: Optional[Path]
    error: Optional[str] = None


class OrchestratorRunner:
    """Gestiona la ejecución concurrente de tareas respetando prioridades."""

    def __init__(self, config: ConfigManager, repository: TaskRepository, adapter: ScraperAdapter):
        self.config = config
        self.repository = repository
        self.adapter = adapter
        self.resource_limiter = ResourceLimiter(
            cpu_target=self.config.get("resource_monitor.cpu_target", 0.8),
            memory_target=self.config.get("resource_monitor.memory_target", 0.8)
        )
        self.retry_delay = max(self.config.get("execution.retry_delay_minutes", 30), 1)
        self.max_parallel = self.config.get("execution.max_parallel_scrapers", 4)

    # ------------------------------------------------------------------
    # Preparación del lote
    # ------------------------------------------------------------------
    def prepare_batch(self, tasks: List[ScrapingTask]) -> ExecutionBatch:
        if not tasks:
            raise ValueError("No se recibieron tareas para preparar el lote")
        now = datetime.now()
        month_year = now.strftime("%b%y").lower() # ej. sep25
        
        # Determina si es la 1ra o 2da quincena
        desired_execution = 1 if now.day <= 15 else 2
        
        # El repo nos da el número correcto para esta quincena
        execution_number = self.repository.next_execution_number(month_year, desired_execution)
        
        batch_id = f"{month_year}_{execution_number:02d}"
        
        for task in tasks:
            task.batch_id = batch_id
            
        self.repository.insert_tasks(tasks)
        self.repository.reset_running_tasks() # Resetea cualquier tarea 'running' de lotes anteriores
        
        batch = self.repository.create_batch(batch_id, month_year, execution_number, total_tasks=len(tasks))
        logger.info("Lote preparado %s con %d tareas", batch.batch_id, len(tasks))
        return batch

    # ------------------------------------------------------------------
    async def run_batch(self, batch: ExecutionBatch) -> None:
        # Colas para organizar las tareas
        pending_main: Dict[str, Deque[ScrapingTask]] = defaultdict(deque)
        pending_detail: Deque[ScrapingTask] = deque()
        retry_heap: List[tuple[float, ScrapingTask]] = []
        
        # Estado de la ejecución
        running_tasks: Dict[str, asyncio.Task[TaskExecutionResult]] = {}
        active_sites: set[str] = set()

        # Cargar tareas del lote actual desde la BD
        tasks = self.repository.get_tasks_for_batch(batch.batch_id)
        for task in tasks:
            if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                continue
            if task.status == TaskStatus.BLOCKED:
                # Las tareas de detalle bloqueadas esperan su turno
                continue
            
            # Tareas pendientes o para reintentar se encolan
            if task.is_detail:
                pending_detail.append(task)
            else:
                pending_main[task.website_code].append(task)

        # Lógica de prioridades y rotación
        priority_sites = self.config.get("execution.priority_sites", [])
        primary_site = priority_sites[0] if priority_sites else None
        
        # Rotación de scrapers no prioritarios
        all_scrapers = self.config.enabled_scrapers()
        rotation_sites = [s for s in all_scrapers if s != primary_site]
        rotation_iter = itertools.cycle(rotation_sites)

        async def schedule_next_task() -> bool:
            self._requeue_ready_retries(retry_heap, pending_main, pending_detail)
            
            if len(running_tasks) >= self.max_parallel:
                return False
            if not self.resource_limiter.allows_new_task():
                await asyncio.sleep(5) # Esperar si los recursos están altos
                return False

            # 1. Prioridad Máxima: Tareas de detalle listas
            if pending_detail:
                task = pending_detail.popleft()
                await self._launch_task(task, batch, running_tasks, active_sites)
                return True

            # 2. Scraper Principal (siempre activo si tiene tareas)
            if primary_site and primary_site not in active_sites and pending_main.get(primary_site):
                task = pending_main[primary_site].popleft()
                await self._launch_task(task, batch, running_tasks, active_sites)
                return True

            # 3. Rotación del resto de scrapers
            for _ in range(len(rotation_sites)):
                site = next(rotation_iter)
                if site not in active_sites and pending_main.get(site):
                    task = pending_main[site].popleft()
                    await self._launch_task(task, batch, running_tasks, active_sites)
                    return True
            
            return False

        # Bucle principal de ejecución
        while True:
            # Intenta llenar la cola de ejecución
            while await schedule_next_task():
                pass

            # Si no hay nada corriendo ni pendiente, hemos terminado
            if not running_tasks and not any(pending_main.values()) and not pending_detail and not retry_heap:
                break

            # Esperar a que termine al menos una tarea
            done, _ = await asyncio.wait(running_tasks.values(), return_when=asyncio.FIRST_COMPLETED)
            
            for finished_future in done:
                result = finished_future.result()
                task = result.task
                
                # Liberar recursos
                running_tasks.pop(task.task_key())
                active_sites.discard(task.website_code)

                if result.success:
                    logger.info("Tarea completada: %s", task.task_key())
                    self.repository.mark_task_completed(task, result.output_path)
                    self.repository.update_batch_progress(batch.batch_id, completed_delta=1)
                    
                    # Si era una tarea principal, desbloquear la de detalle
                    if not task.is_detail:
                        released_tasks = self.repository.release_detail_tasks_for(task.task_key(), result.output_path)
                        for released_task in released_tasks:
                            logger.info("Desbloqueando tarea de detalle: %s", released_task.task_key())
                            pending_detail.append(released_task)
                else:
                    logger.error("Tarea falló: %s. Error: %s", task.task_key(), result.error)
                    task.attempts += 1
                    will_retry = task.attempts < task.max_attempts
                    
                    self.repository.mark_task_failed(task, result.error or "Error desconocido", will_retry)
                    
                    if will_retry:
                        due_time = monotonic() + self.retry_delay * 60
                        heapq.heappush(retry_heap, (due_time, task))
                        logger.info("La tarea %s se reintentará en %d minutos.", task.task_key(), self.retry_delay)
                    else:
                        logger.error("La tarea %s ha fallado permanentemente.", task.task_key())
                        self.repository.update_batch_progress(batch.batch_id, failed_delta=1)

        self.repository.mark_batch_completed(batch.batch_id)
        logger.info("Lote %s completado.", batch.batch_id)

    # ------------------------------------------------------------------
    async def _launch_task(self, task: ScrapingTask, batch: ExecutionBatch, running: Dict[str, asyncio.Task], active_sites: set[str]) -> None:
        task.batch_id = batch.batch_id
        active_sites.add(task.website_code)
        self.repository.mark_task_running(task)
        
        logger.info("Lanzando tarea: %s", task.task_key())
        
        loop = asyncio.get_running_loop()
        future = loop.create_task(self._execute_task(task, batch))
        running[task.task_key()] = future

    async def _execute_task(self, task: ScrapingTask, batch: ExecutionBatch) -> TaskExecutionResult:
        try:
            loop = asyncio.get_running_loop()
            # Ejecutar el adapter en un executor para no bloquear el loop de asyncio
            success, message = await loop.run_in_executor(
                None,
                self.adapter.run,
                task,
                batch,
            )
            
            # El path de salida se obtiene del contexto que el adapter construye
            context = self.adapter.get_last_context()
            output_path = context.output_path if context else None

            if success:
                return TaskExecutionResult(task=task, success=True, output_path=output_path)
            else:
                return TaskExecutionResult(task=task, success=False, output_path=None, error=message)

        except Exception as exc:
            logger.exception("Excepción no controlada durante la ejecución de la tarea %s.", task.task_key())
            return TaskExecutionResult(task=task, success=False, output_path=None, error=str(exc))

    def _build_output_dir(self, task: ScrapingTask, batch: ExecutionBatch) -> Path:
        """Construye la ruta de salida según la especificación: data/Web/Ciu/Op/Prod/mesaño/quincena/"""
        base_path_str = self.config.get("data.base_path", "data")
        base = self.config.base_dir.parent / base_path_str

        return (
            base /
            task.website_code /
            task.city_code /
            task.operation_code /
            task.product_code /
            batch.month_year /
            f"{batch.execution_number:02d}"
        )

    def _requeue_ready_retries(self, retry_heap: List[tuple[float, ScrapingTask]], pending_main: Dict[str, Deque[ScrapingTask]], detail_queue: Deque[ScrapingTask]) -> None:
        now = monotonic()
        while retry_heap and retry_heap[0][0] <= now:
            _, task = heapq.heappop(retry_heap)
            task.status = TaskStatus.PENDING
            if task.is_detail:
                detail_queue.append(task)
            else:
                pending_main[task.website_code].append(task)
            logger.info("Re-encolando tarea para reintento: %s", task.task_key())
