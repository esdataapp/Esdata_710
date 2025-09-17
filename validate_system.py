#!/usr/bin/env python3
"""Validador integral del sistema de orquestación."""
from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import List

import pandas as pd
import yaml

from esdata.configuration import ConfigManager
from esdata.database import TaskRepository
from esdata.url_loader import UrlLoader

BASE_DIR = Path(__file__).resolve().parent


@dataclass
class ValidationResult:
    name: str
    passed: bool
    details: str = ""


class SystemValidator:
    def __init__(self, base_dir: Path | None = None):
        self.base_dir = base_dir or BASE_DIR
        self.config = ConfigManager(self.base_dir)
        self.repo = TaskRepository(self.base_dir / self.config.raw["database"]["path"])
        self.loader = UrlLoader(self.config)

    # ------------------------------------------------------------------
    def validate(self) -> List[ValidationResult]:
        checks = [
            ("Estructura de directorios", self._check_directories),
            ("Archivo de configuración", self._check_config),
            ("Archivos de URLs", self._check_url_files),
            ("Scrapers", self._check_scrapers),
            ("Base de datos", self._check_database),
        ]
        results: List[ValidationResult] = []
        for name, func in checks:
            try:
                passed, details = func()
            except Exception as exc:
                results.append(ValidationResult(name, False, f"Error: {exc}"))
            else:
                results.append(ValidationResult(name, passed, details))
        return results

    # ------------------------------------------------------------------
    def _check_directories(self) -> tuple[bool, str]:
        required = [
            self.config.data_path(),
            self.config.urls_path(),
            self.config.logs_path(),
            self.base_dir / "Scrapers",
        ]
        missing = [str(path) for path in required if not path.exists()]
        if missing:
            return False, "Faltan directorios: " + ", ".join(missing)
        return True, "OK"

    def _check_config(self) -> tuple[bool, str]:
        config_path = self.base_dir / "config" / "config.yaml"
        if not config_path.exists():
            return False, f"No se encontró {config_path}"
        with config_path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        required_sections = {"database", "data", "scrapers", "execution", "websites"}
        missing = required_sections - set(data)
        if missing:
            return False, "Secciones faltantes: " + ", ".join(sorted(missing))
        return True, "OK"

    def _check_url_files(self) -> tuple[bool, str]:
        scrapers = self.config.enabled_scrapers()
        issues: List[str] = []
        for scraper in scrapers:
            csv_path = self.config.urls_path() / f"{scraper}_urls.csv"
            if not csv_path.exists():
                issues.append(f"{csv_path} no encontrado")
                continue
            df = pd.read_csv(csv_path, encoding="utf-8")
            if not set(self.loader.REQUIRED_COLUMNS).issubset(df.columns):
                issues.append(f"{csv_path} columnas incompletas")
        return (False, "; ".join(issues)) if issues else (True, "OK")

    def _check_scrapers(self) -> tuple[bool, str]:
        scrapers_dir = self.base_dir / "Scrapers"
        expected = {f"{name}.py" for name in self.config.enabled_scrapers()}
        issues: List[str] = []
        for scraper_file in expected:
            path = scrapers_dir / scraper_file
            if not path.exists():
                issues.append(f"Falta {scraper_file}")
                continue
            spec = importlib.util.spec_from_file_location(path.stem, path)
            if spec is None or spec.loader is None:
                issues.append(f"No se puede cargar {scraper_file}")
        return (False, "; ".join(issues)) if issues else (True, "OK")

    def _check_database(self) -> tuple[bool, str]:
        with self.repo.get_connection() as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('scraping_tasks', 'execution_batches')"
            ).fetchall()
        if len(tables) < 2:
            return False, "La base de datos no tiene el esquema esperado"
        return True, "OK"


def main() -> None:
    validator = SystemValidator()
    results = validator.validate()
    print("=" * 60)
    print("VALIDACIÓN DEL SISTEMA")
    print("=" * 60)
    for result in results:
        status = "✅" if result.passed else "❌"
        print(f"{status} {result.name}: {result.details or 'OK'}")
    print("=" * 60)


if __name__ == "__main__":
    main()
