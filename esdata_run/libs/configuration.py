"""Gestión centralizada de configuración."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

import yaml

logger = logging.getLogger(__name__)


class ConfigError(RuntimeError):
    """Error al cargar o interpretar la configuración."""


class ConfigManager:
    """
    Encargado de cargar el archivo config.yaml y proporcionar acceso
    a los parámetros de configuración de una manera sencilla y segura.
    """

    def __init__(self, config_path: Path):
        if not config_path.exists():
            raise ConfigError(f"El archivo de configuración no se encontró en: {config_path}")
        
        self.config_path = config_path
        self.base_dir = config_path.parent.parent # Sube dos niveles (de 'config' a 'esdata_run')
        self._config: dict[str, Any] = {}
        self.reload()

    def reload(self) -> None:
        """Recarga la configuración desde el archivo YAML."""
        try:
            with self.config_path.open("r", encoding="utf-8") as handle:
                self._config = yaml.safe_load(handle) or {}
            logger.info("Configuración cargada exitosamente desde %s", self.config_path)
        except Exception as e:
            logger.error("Error fatal al cargar el archivo de configuración: %s", e)
            raise ConfigError(f"No se pudo cargar o parsear {self.config_path}: {e}") from e

    def get(self, key: str, default: Any = None) -> Any:
        """
        Obtiene un valor de la configuración usando notación de puntos.
        Ejemplo: get('database.path')
        """
        keys = key.split('.')
        value = self._config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    def enabled_scrapers(self) -> list[str]:
        """
        Devuelve la lista de scrapers habilitados para la ejecución,
        basado en el mapeo de sitios web en la configuración.
        """
        website_mapping = self.get('website_mapping', {})
        # Los scrapers habilitados son los valores del mapeo (ej. ["Inm24", "CyT", ...])
        return list(website_mapping.values())

    def get_website_code(self, raw_website_name: str) -> Optional[str]:
        """
        Traduce un nombre de sitio web del CSV (ej. 'Inmuebles24')
        a su código interno (ej. 'Inm24') usando el mapeo.
        """
        mapping = self.get('website_mapping', {})
        return mapping.get(raw_website_name)
