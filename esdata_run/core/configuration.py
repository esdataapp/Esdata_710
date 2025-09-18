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
        a su código interno (ej. 'Inm24') usando el mapeo (case-insensitive).
        """
        mapping = self.get('website_mapping', {})
        # Búsqueda case-insensitive
        for key, value in mapping.items():
            if key.lower() == raw_website_name.lower():
                return value
        return None

    def get_scraper_config(self, scraper_name: str) -> Optional[dict[str, Any]]:
        """Obtiene la configuración para un scraper específico, case-insensitive."""
        scraper_name_lower = scraper_name.lower()
        websites_config = self.get('websites', {})
        for key, config_value in websites_config.items():
            if key.lower() == scraper_name_lower:
                return config_value
        return None

    def get_scraper_script_path(self, scraper_name: str) -> Optional[Path]:
        """
        Construye la ruta completa al script de un scraper (case-insensitive).
        """
        scraper_name_lower = scraper_name.lower()
        scrapers_config = self.get('scrapers', {})
        scripts_mapping = scrapers_config.get('scripts', {})
        
        # Búsqueda case-insensitive en el mapeo de scripts
        script_filename = None
        for key, value in scripts_mapping.items():
            if key.lower() == scraper_name_lower:
                script_filename = value
                break

        if not script_filename:
            logger.error("No se encontró el nombre del script para el scraper '%s' en la configuración.", scraper_name)
            return None

        # La ruta base de los scrapers se define en el config, relativa a la raíz del proyecto.
        # La base_dir de ConfigManager es 'esdata_run', así que subimos un nivel.
        project_root = self.base_dir.parent
        scrapers_base_path_str = scrapers_config.get('base_path', 'esdata_run/scrapers')
        scrapers_base_path = project_root / scrapers_base_path_str
        
        script_path = scrapers_base_path / script_filename
        
        if not script_path.exists():
            logger.error("El archivo de script para '%s' no se encontró en la ruta: %s", scraper_name, script_path)
            return None
            
        return script_path
