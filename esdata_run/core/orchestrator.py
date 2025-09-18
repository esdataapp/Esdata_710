#!/usr/bin/env python3
"""Punto de entrada del sistema de orquestación de scraping."""
from __future__ import annotations

import argparse
import asyncio
import logging
from collections import Counter
from pathlib import Path
from typing import Iterable, List

# Rutas relativas a la nueva estructura
from .configuration import ConfigManager
from .database import TaskRepository
from ..models.main import ScrapingTask
from .scheduler import OrchestratorRunner
from .url_loader import UrlLoader
from .scraper_adapter import ScraperAdapter

# El directorio base del proyecto es el padre de 'esdata_run'
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "orchestrator.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("orchestrator")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Orquestador de scrapers inmobiliarios")
    sub = parser.add_subparsers(dest="command", required=True)

    plan_cmd = sub.add_parser("plan", help="Muestra el plan de ejecución a partir de los CSV")
    plan_cmd.add_argument("--scrapers", nargs="*", help="Limita la carga a scrapers específicos (ej. Inm24, CyT)")

    run_cmd = sub.add_parser("run", help="Ejecuta los scrapers")
    run_cmd.add_argument("--scrapers", nargs="*", help="Limita la ejecución a scrapers específicos (ej. Inm24, CyT)")
    run_cmd.add_argument("--resume", action="store_true", help="Reanuda el lote en ejecución si existe")
    run_cmd.add_argument("--dry-run", action="store_true", help="Solo muestra la planeación sin ejecutar")
    run_cmd.add_argument("--test-mode", action="store_true", help="Activa el modo de prueba definido en config.yaml")

    sub.add_parser("status", help="Muestra el estado del último lote")
    sub.add_parser("resume", help="Atajo para reanudar el último lote en ejecución")

    return parser.parse_args()


def load_tasks(config: ConfigManager, scrapers: Iterable[str]) -> List[ScrapingTask]:
    """Carga tareas desde archivos CSV, usando el código de scraper como nombre de archivo."""
    loader = UrlLoader(config)
    tasks: List[ScrapingTask] = []

    for scraper_code in scrapers:
        scraper_code_lower = scraper_code.lower()
        
        # El nombre del archivo CSV se deriva directamente del código del scraper (ej. "inm24")
        loaded = loader.load(scraper_code_lower)
        if not loaded:
            logger.warning("No se encontraron URLs para %s (archivo: %s_urls.csv)", scraper_code, scraper_code_lower)
            continue
        
        # Asignar el código interno del scraper a cada tarea
        for task in loaded:
            task.scraper_name = scraper_code_lower
        
        tasks.extend(loaded)
        
    return tasks


def print_plan(tasks: List[ScrapingTask]) -> None:
    if not tasks:
        logger.info("No hay tareas registradas")
        return
    counter = Counter(task.scraper_name for task in tasks)
    detail = Counter("detalle" if task.is_detail else "principal" for task in tasks)
    logger.info("Tareas totales: %d", len(tasks))
    for scraper, count in counter.items():
        logger.info("  %-12s %4d", scraper, count)
    logger.info("  Principales: %d | Detalle: %d", detail.get("principal", 0), detail.get("detalle", 0))


def cmd_plan(config: ConfigManager, args: argparse.Namespace) -> None:
    scrapers = args.scrapers or config.enabled_scrapers()
    tasks = load_tasks(config, scrapers)
    print_plan(tasks)


def cmd_status(repo: TaskRepository) -> None:
    batch = repo.find_open_batch()
    if not batch:
        logger.info("No hay lotes en ejecución. Revisando último completado...")
        with repo.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM execution_batches ORDER BY started_at DESC LIMIT 1"
            ).fetchone()
        if not row:
            logger.info("Sin historial de ejecuciones")
            return
        batch = repo.batch_by_id(row["batch_id"])
    assert batch
    logger.info("Lote %s - estado: %s", batch.batch_id, batch.status)
    with repo.get_connection() as conn:
        rows = conn.execute(
            """
            SELECT status, COUNT(*) as total
            FROM scraping_tasks
            WHERE batch_id = ?
            GROUP BY status
            ORDER BY status
            """,
            (batch.batch_id,),
        ).fetchall()
    for row in rows:
        logger.info("  %-10s %4d", row["status"], row["total"])


def cmd_run(config: ConfigManager, repo: TaskRepository, args: argparse.Namespace) -> None:
    # Normalizar todos los nombres de scraper a minúsculas
    if args.scrapers:
        args.scrapers = [s.lower() for s in args.scrapers]

    # Aplicar modo de prueba si está activado
    if args.test_mode and config.get('test_mode.enabled', False):
        scraper_to_test = config.get('test_mode.scraper_to_test')
        if not scraper_to_test:
            logger.error("El modo de prueba está activado pero 'scraper_to_test' no está definido en config.yaml")
            return
        
        scraper_to_test_lower = scraper_to_test.lower()
        logger.warning("--- MODO DE PRUEBA ACTIVADO ---")
        logger.warning("Ejecutando únicamente el scraper: %s", scraper_to_test_lower)
        scrapers = [scraper_to_test_lower]
    else:
        # Usar scrapers de los argumentos o todos los habilitados, ya normalizados
        scrapers = args.scrapers or [s.lower() for s in config.enabled_scrapers()]

    adapter = ScraperAdapter(PROJECT_ROOT, config)
    runner = OrchestratorRunner(config, repo, adapter)

    if args.resume:
        batch = repo.find_open_batch()
        if not batch:
            logger.error("No existe lote en ejecución para reanudar")
            return
        logger.info("Reanudando lote %s", batch.batch_id)
    else:
        existing = repo.find_open_batch()
        if existing and existing.status != 'completed':
            logger.error('Existe un lote en ejecución (%s). Use --resume para continuarlo o finalícelo.', existing.batch_id)
            return
            
        logger.info("Cargando tareas para los scrapers: %s", ", ".join(scrapers))
        tasks = load_tasks(config, scrapers)
        if not tasks:
            logger.error("No hay tareas para ejecutar con los filtros seleccionados.")
            return
        print_plan(tasks)
        if args.dry_run:
            logger.info("Ejecución en modo dry-run, finalizando")
            return
        batch = runner.prepare_batch(tasks)

    try:
        asyncio.run(runner.run_batch(batch))
    except KeyboardInterrupt:
        logger.warning("Ejecución interrumpida por el usuario")


def main() -> None:
    args = parse_args()
    
    # La configuración se busca desde la raíz del proyecto
    config_path = PROJECT_ROOT / "esdata_run" / "config" / "config.yaml"
    config = ConfigManager(config_path)
    
    db_path = PROJECT_ROOT / config.get("database.path")
    repo = TaskRepository(db_path)

    if args.command == "plan":
        cmd_plan(config, args)
    elif args.command == "status":
        cmd_status(repo)
    elif args.command == "resume":
        # El comando resume ya no necesita su propia lógica, se maneja en run
        args.resume = True
        cmd_run(config, repo, args)
    elif args.command == "run":
        cmd_run(config, repo, args)
    else:
        raise SystemExit(f"Comando no soportado: {args.command}")


if __name__ == "__main__":
    main()
