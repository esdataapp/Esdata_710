"""Ejecución y coordinación de tareas de scraping."""
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
from .models import ExecutionBatch, ScrapingTask, TaskStatus
from .resource_monitor import ResourceLimiter

logger = logging.getLogger(__name__)


@dataclass
class TaskExecutionResult:
    task: ScrapingTask
    success: bool
    output_path: Optional[Path]
    error: Optional[str] = None


class OrchestratorRunner:
    """Gestiona la ejecución concurrente de tareas respetando prioridades."""

    def __init__(self, config: ConfigManager, repository: TaskRepository, adapter):
        self.config = config
        self.repository = repository
        self.adapter = adapter
        self.resource_limiter = ResourceLimiter(cpu_target=0.8, memory_target=0.8)
        self.retry_delay = max(self.config.retry_delay_minutes(), 1)
        self.max_parallel = self.config.max_parallel_scrapers()

    # ------------------------------------------------------------------
    # Preparación del lote
    # ------------------------------------------------------------------
    def prepare_batch(self, tasks: List[ScrapingTask]) -> ExecutionBatch:
        if not tasks:
            raise ValueError("No se recibieron tareas para preparar el lote")
        now = datetime.now()
        month_year = now.strftime("%b%y")
        desired_execution = 1 if now.day <= 15 else 2
        execution_number = self.repository.next_execution_number(month_year, desired_execution)
        batch_id = f"{month_year}_{execution_number:02d}"
        for task in tasks:
            task.batch_id = batch_id
        self.repository.insert_tasks(batch_id, tasks)
        self.repository.reset_running_tasks(batch_id)
        batch = self.repository.create_batch(batch_id, month_year, execution_number, total_tasks=len(tasks))
        logger.info("Lote preparado %s con %d tareas", batch.batch_id, len(tasks))
        return batch

    # ------------------------------------------------------------------
    async def run_batch(self, batch: ExecutionBatch) -> None:
        pending_main: Dict[str, Deque[ScrapingTask]] = defaultdict(deque)
        detail_queue: Deque[ScrapingTask] = deque()
        active_sites: set[str] = set()
        retry_heap: List[tuple[float, ScrapingTask]] = []
        running: Dict[str, asyncio.Task[TaskExecutionResult]] = {}

        tasks = self.repository.all_tasks(batch.batch_id)
        for task in tasks:
            if task.status == TaskStatus.COMPLETED or task.status == TaskStatus.FAILED:
                continue
            if task.status == TaskStatus.BLOCKED:
                continue
            if task.status in (TaskStatus.PENDING, TaskStatus.RETRYING):
                if task.is_detail:
                    detail_queue.append(task)
                else:
                    pending_main[task.website_code or task.website].append(task)

        priority_sites = self.config.websites_priority()
        primary_site = priority_sites[0] if priority_sites else None
        rotation_sites = [site for site in priority_sites if site != primary_site]
        rotation_iter = itertools.cycle(rotation_sites) if rotation_sites else None

        async def schedule_next_task() -> bool:
            self._requeue_ready_retries(retry_heap, pending_main, detail_queue)
            if len(running) >= self.max_parallel:
                return False
            if not self.resource_limiter.allows_new_task():
                return False
            # Prioridad: tareas de detalle listas
            for _ in range(len(detail_queue)):
                task = detail_queue.popleft()
                site_code = task.website_code or task.website
                if site_code not in active_sites:
                    await self._launch_task(task, batch, running, active_sites)
                    return True
                detail_queue.append(task)
            # Principal prioritario
            if primary_site and primary_site not in active_sites:
                queue = pending_main.get(primary_site)
                if queue:
                    task = queue.popleft()
                    await self._launch_task(task, batch, running, active_sites)
                    return True
            # Rotación del resto
            if rotation_iter:
                tried = 0
                total_candidates = len(rotation_sites)
                while total_candidates and tried < total_candidates:
                    site = next(rotation_iter)
                    tried += 1
                    queue = pending_main.get(site)
                    if not queue:
                        continue
                    if site in active_sites:
                        continue
                    task = queue.popleft()
                    await self._launch_task(task, batch, running, active_sites)
                    return True
            return False

        while True:
            made_progress = True
            while made_progress:
                made_progress = await schedule_next_task()
            if not running:
                self._requeue_ready_retries(retry_heap, pending_main, detail_queue)
                if not running and not any(pending_main.values()) and not detail_queue and not retry_heap:
                    break
                await asyncio.sleep(1)
                continue
            done, _ = await asyncio.wait(running.values(), return_when=asyncio.FIRST_COMPLETED)
            for finished in done:
                result = finished.result()
                task = result.task
                key = task.task_key()
                running.pop(key, None)
                site_code = task.website_code or task.website
                active_sites.discard(site_code)
                if result.success:
                    self.repository.mark_task_completed(task, result.output_path)
                    self.repository.update_batch_progress(batch.batch_id, completed_delta=1)
                    logger.info("Tarea completada %s", key)
                    if not task.is_detail and result.output_path:
                        released = self.repository.release_detail_tasks(task, result.output_path)
                        for detail_task in released:
                            detail_queue.append(detail_task)
                else:
                    logger.error("Tarea falló %s: %s", key, result.error)
                    will_retry = task.attempts + 1 < task.max_attempts
                    self.repository.mark_task_failed(task, result.error or "Error desconocido", will_retry)
                    if will_retry:
                        task.attempts += 1
                        due_time = monotonic() + self.retry_delay * 60
                        heapq.heappush(retry_heap, (due_time, task))
                    else:
                        self.repository.update_batch_progress(batch.batch_id, failed_delta=1)
            # loop to schedule new tasks after completions
        self.repository.mark_batch_completed(batch.batch_id)
        logger.info("Lote %s completado", batch.batch_id)

    # ------------------------------------------------------------------
    async def _launch_task(self, task: ScrapingTask, batch: ExecutionBatch, running: Dict[str, asyncio.Task], active_sites: set[str]) -> None:
        task.batch_id = batch.batch_id
        site_code = task.website_code or task.website
        active_sites.add(site_code)
        self.repository.mark_task_running(task)
        loop = asyncio.get_running_loop()
        future = loop.create_task(self._execute_task(task, batch))
        running[task.task_key()] = future

    async def _execute_task(self, task: ScrapingTask, batch: ExecutionBatch) -> TaskExecutionResult:
        output_dir = self._build_output_dir(task, batch)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / task.expected_filename(batch.month_year, batch.execution_number)
        dependency = task.dependency_path
        try:
            loop = asyncio.get_running_loop()
            result_path = await loop.run_in_executor(
                None,
                self.adapter.run,
                task,
                output_file,
                dependency,
                batch,
            )
            final_path = Path(result_path) if result_path else output_file
            return TaskExecutionResult(task=task, success=True, output_path=final_path)
        except Exception as exc:  # pragma: no cover - errores de scraping
            return TaskExecutionResult(task=task, success=False, output_path=None, error=str(exc))

    def _build_output_dir(self, task: ScrapingTask, batch: ExecutionBatch) -> Path:
        base = self.config.data_path()
        website = task.website_code or task.website
        city = task.city_code or task.city
        operation = task.operation_code or task.operation
        product = task.product_code or task.product
        return base / website / city / operation / product / batch.month_year / f"{batch.execution_number:02d}"

    def _requeue_ready_retries(self, retry_heap: List[tuple[float, ScrapingTask]], pending_main: Dict[str, Deque[ScrapingTask]], detail_queue: Deque[ScrapingTask]) -> None:
        now = monotonic()
        while retry_heap and retry_heap[0][0] <= now:
            _, task = heapq.heappop(retry_heap)
            task.status = TaskStatus.PENDING
            if task.is_detail:
                detail_queue.append(task)
            else:
                pending_main[task.website_code or task.website].append(task)
