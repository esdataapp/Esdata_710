"""Herramientas utilitarias para tareas de mantenimiento del proyecto."""
from __future__ import annotations

from pathlib import Path

from esdata.configuration import ConfigManager


def ensure_project_structure(base_dir: Path | None = None) -> None:
    """Crea las carpetas base declaradas en la configuración."""
    config = ConfigManager(base_dir)
    config.data_path()
    config.urls_path()
    config.logs_path()
    (config.base_dir / "Scrapers").mkdir(parents=True, exist_ok=True)


def list_scrapers(base_dir: Path | None = None) -> list[str]:
    """Devuelve los scrapers habilitados según la configuración."""
    config = ConfigManager(base_dir)
    return config.enabled_scrapers()
