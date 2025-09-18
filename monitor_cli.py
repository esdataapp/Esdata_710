#!/usr/bin/env python3
"""Monitor CLI para revisar el estado de la orquestación en Linux."""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from tabulate import tabulate

from esdata.configuration import ConfigManager
from esdata.database import TaskRepository
from esdata.models import TaskStatus

BASE_DIR = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Monitor del sistema de scraping")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("overview", help="Muestra el estado general del último lote")

    batches_cmd = sub.add_parser("batches", help="Lista el historial de lotes")
    batches_cmd.add_argument("--limit", type=int, default=10)

    tasks_cmd = sub.add_parser("tasks", help="Lista tareas filtradas por estado")
    tasks_cmd.add_argument("--status", choices=[s.value for s in TaskStatus], nargs="*")
    tasks_cmd.add_argument("--batch", help="Identificador del lote a consultar")

    return parser.parse_args()


def get_repository() -> TaskRepository:
    config = ConfigManager(BASE_DIR)
    return TaskRepository(BASE_DIR / config.raw["database"]["path"])


def cmd_overview(repo: TaskRepository) -> None:
    batch = repo.find_open_batch()
    if not batch:
        with repo.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM execution_batches ORDER BY started_at DESC LIMIT 1"
            ).fetchone()
        if not row:
            print("Sin ejecuciones registradas")
            return
        batch = repo.batch_by_id(row["batch_id"])
    assert batch
    print(f"Lote: {batch.batch_id} | Estado: {batch.status}")
    print(f"Iniciado: {batch.started_at}")
    if batch.completed_at:
        print(f"Finalizado: {batch.completed_at}")
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
    table = [(row["status"], row["total"]) for row in rows]
    print(tabulate(table, headers=["Estado", "Cantidad"], tablefmt="github"))


def cmd_batches(repo: TaskRepository, limit: int) -> None:
    with repo.get_connection() as conn:
        rows = conn.execute(
            """
            SELECT batch_id, month_year, execution_number, status, started_at, completed_at,
                   total_tasks, completed_tasks, failed_tasks
            FROM execution_batches
            ORDER BY started_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    if not rows:
        print("Sin historial disponible")
        return
    table = []
    for row in rows:
        started = datetime.fromisoformat(row["started_at"]) if row["started_at"] else None
        finished = datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None
        duration = (finished - started) if started and finished else "-"
        table.append(
            [
                row["batch_id"],
                row["status"],
                row["total_tasks"] or 0,
                row["completed_tasks"] or 0,
                row["failed_tasks"] or 0,
                duration,
            ]
        )
    print(tabulate(table, headers=["Lote", "Estado", "Total", "Completadas", "Fallidas", "Duración"], tablefmt="github"))


def cmd_tasks(repo: TaskRepository, statuses: Optional[Iterable[str]], batch_id: Optional[str]) -> None:
    if not batch_id:
        batch = repo.find_open_batch()
        if not batch:
            print("No hay lote activo, especifique --batch")
            return
        batch_id = batch.batch_id
    with repo.get_connection() as conn:
        if statuses:
            placeholders = ",".join("?" for _ in statuses)
            query = f"SELECT scraper_name, website_code, city_code, operation_code, product_code, status, attempts FROM scraping_tasks WHERE batch_id = ? AND status IN ({placeholders}) ORDER BY scraper_name, order_num"
            rows = conn.execute(query, (batch_id, *statuses)).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT scraper_name, website_code, city_code, operation_code, product_code, status, attempts
                FROM scraping_tasks
                WHERE batch_id = ?
                ORDER BY scraper_name, order_num
                """,
                (batch_id,),
            ).fetchall()
    if not rows:
        print("Sin tareas que coincidan con el filtro")
        return
    table = [
        [
            row["scraper_name"],
            row["website_code"],
            row["city_code"],
            row["operation_code"],
            row["product_code"],
            row["status"],
            row["attempts"],
        ]
        for row in rows
    ]
    print(tabulate(table, headers=["Scraper", "Sitio", "Ciudad", "Operación", "Producto", "Estado", "Intentos"], tablefmt="github"))


def main() -> None:
    args = parse_args()
    repo = get_repository()
    if args.command == "overview":
        cmd_overview(repo)
    elif args.command == "batches":
        cmd_batches(repo, args.limit)
    elif args.command == "tasks":
        cmd_tasks(repo, args.status, args.batch)
    else:
        raise SystemExit("Comando no soportado")


if __name__ == "__main__":
    main()
