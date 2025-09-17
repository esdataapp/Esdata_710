"""Gestión centralizada de configuración y normalización de variables."""
from __future__ import annotations

from collections.abc import Mapping
import csv
from pathlib import Path
from typing import Any, Optional

import yaml


class ConfigError(RuntimeError):
    """Error al cargar o interpretar la configuración."""


class ConfigManager:
    """Encargado de cargar la configuración y exponer utilidades de normalización."""

    def __init__(self, base_dir: Optional[Path] = None, config_path: Optional[Path] = None):
        self.base_dir = Path(base_dir or Path.cwd())
        self.config_path = config_path or (self.base_dir / "config" / "config.yaml")
        self._config: dict[str, Any] = {}
        self._aliases: dict[str, dict[str, str]] = {}
        self.reload()

    # ------------------------------------------------------------------
    # Carga y normalización
    # ------------------------------------------------------------------
    def reload(self) -> None:
        data = self._default_config()
        if self.config_path.exists():
            with self.config_path.open("r", encoding="utf-8") as handle:
                user_config = yaml.safe_load(handle) or {}
            data = self._deep_merge_dicts(data, user_config)
        self._config = data
        self._aliases = self._build_aliases()

    @property
    def raw(self) -> dict[str, Any]:
        return self._config

    # ------------------------------------------------------------------
    # Resolución de rutas
    # ------------------------------------------------------------------
    def resolve_path(self, *parts: str, create: bool = False) -> Path:
        path = self.base_dir.joinpath(*parts)
        if create:
            path.mkdir(parents=True, exist_ok=True)
        return path

    def data_path(self) -> Path:
        path = self.resolve_path(self._config["data"]["base_path"])
        path.mkdir(parents=True, exist_ok=True)
        return path

    def urls_path(self) -> Path:
        configured = self.resolve_path(self._config["data"]["urls_path"])
        legacy = self.base_dir / "Urls"
        if not configured.exists() and legacy.exists():
            return legacy
        configured.mkdir(parents=True, exist_ok=True)
        return configured

    def logs_path(self) -> Path:
        return self.resolve_path(self._config["data"].get("logs_path", "logs"), create=True)

    # ------------------------------------------------------------------
    # Alias y normalización
    # ------------------------------------------------------------------
    def normalize(self, dimension: str, value: Optional[str]) -> tuple[str, str]:
        value = (value or "").strip()
        if not value:
            return ("Unknown", "")
        key = self._standardize_key(value)
        alias_map = self._aliases.get(dimension.lower(), {})
        canonical = alias_map.get(key, value)
        return canonical, value

    def website_config(self, website_code: str) -> dict[str, Any]:
        sites = self._config.get("websites", {})
        if website_code not in sites:
            raise ConfigError(f"Sitio no configurado: {website_code}")
        return sites[website_code]

    def websites_priority(self) -> list[str]:
        sites = self._config.get("websites", {})
        ordered = sorted(
            ((site, cfg.get("priority", 100)) for site, cfg in sites.items()),
            key=lambda item: item[1],
        )
        return [site for site, _ in ordered]

    def enabled_scrapers(self) -> list[str]:
        execution_cfg = self._config.get("execution", {})
        explicit = execution_cfg.get("include_scrapers")
        if explicit:
            return [name.lower() for name in explicit]
        urls_dir = self.urls_path()
        return [p.stem.lower() for p in urls_dir.glob("*_urls.csv")]

    def detail_scraper_for(self, website_code: str) -> Optional[str]:
        info = self._config.get("websites", {}).get(website_code)
        if not info:
            return None
        if not info.get("has_detail_scraper"):
            return None
        detail_name = info.get("detail_scraper")
        if detail_name:
            return detail_name
        return f"{website_code.lower()}_det"

    def execution_settings(self) -> dict[str, Any]:
        return self._config.get("execution", {})

    def retry_delay_minutes(self) -> int:
        return int(self.execution_settings().get("retry_delay_minutes", 30))

    def max_parallel_scrapers(self) -> int:
        return int(self.execution_settings().get("max_parallel_scrapers", 4))

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------
    def _default_config(self) -> dict[str, Any]:
        return {
            "database": {"path": "orchestrator.db", "backup_path": "backups"},
            "data": {
                "base_path": "data",
                "urls_path": "urls",
                "logs_path": "logs",
                "temp_path": "temp",
            },
            "scrapers": {
                "path": "Scrapers",
                "python_executable": "python3",
                "timeout_minutes": 45,
                "memory_limit_mb": 1024,
            },
            "execution": {
                "max_parallel_scrapers": 8,
                "retry_delay_minutes": 30,
                "execution_interval_days": 15,
                "rate_limit_delay_seconds": 2,
                "max_retry_attempts": 3,
                "enable_auto_recovery": True,
                "include_scrapers": ["inm24", "lam", "cyt", "mit", "prop", "tro"],
            },
            "websites": {
                "Inm24": {"priority": 1, "has_detail_scraper": True},
                "CyT": {"priority": 2, "has_detail_scraper": False},
                "Lam": {"priority": 3, "has_detail_scraper": True},
                "Mit": {"priority": 4, "has_detail_scraper": False},
                "Prop": {"priority": 5, "has_detail_scraper": False},
                "Tro": {"priority": 6, "has_detail_scraper": False},
            },
            "aliases": {
                "websites": {
                    "inmuebles24": "Inm24",
                    "casasyterrenos": "CyT",
                    "casas_y_terrenos": "CyT",
                    "lamudi": "Lam",
                    "mitula": "Mit",
                    "propiedades.com": "Prop",
                    "trovit": "Tro",
                }
            },
        }

    def _deep_merge_dicts(self, base: dict[str, Any], extra: Mapping[str, Any]) -> dict[str, Any]:
        result = dict(base)
        for key, value in extra.items():
            if isinstance(value, Mapping) and isinstance(result.get(key), Mapping):
                result[key] = self._deep_merge_dicts(result[key], value)  # type: ignore[arg-type]
            else:
                result[key] = value
        return result

    def _standardize_key(self, value: str) -> str:
        import re
        import unicodedata

        normalized = unicodedata.normalize("NFKD", value)
        normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
        normalized = normalized.lower()
        normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
        normalized = re.sub(r"_+", "_", normalized)
        return normalized.strip("_")

    def _build_aliases(self) -> dict[str, dict[str, str]]:
        aliases: dict[str, dict[str, str]] = {"websites": {}, "cities": {}, "operations": {}, "products": {}}
        # Inyectar alias definidos en config
        config_aliases: Mapping[str, Any] = self._config.get("aliases", {}) or {}
        for dimension, mapping in config_aliases.items():
            if isinstance(mapping, Mapping):
                for raw, canonical in mapping.items():
                    key = self._standardize_key(str(raw))
                    aliases.setdefault(dimension, {})[key] = str(canonical)

        # Alias derivados de listas declaradas en config
        for dimension, list_key in (
            ("cities", "cities"),
            ("operations", "operations"),
            ("products", "products"),
        ):
            for item in self._config.get(list_key, []) or []:
                if not isinstance(item, Mapping):
                    continue
                code = item.get("code")
                name = item.get("name")
                if code:
                    aliases[dimension][self._standardize_key(str(code))] = str(code)
                if name:
                    aliases[dimension][self._standardize_key(str(name))] = str(code or name)

        # Sitios: códigos directos
        for site_code in self._config.get("websites", {}):
            aliases["websites"][self._standardize_key(site_code)] = site_code

        # Alias del CSV de variables
        csv_aliases = self._load_aliases_from_csv()
        for dimension, mapping in csv_aliases.items():
            dest = aliases.setdefault(dimension, {})
            for raw, canonical in mapping.items():
                dest[self._standardize_key(raw)] = canonical

        return aliases

    def _load_aliases_from_csv(self) -> dict[str, dict[str, str]]:
        csv_path = self.base_dir / "Lista de Variables" / "Lista de Variables Orquestacion.csv"
        if not csv_path.exists():
            return {}
        aliases: dict[str, dict[str, str]] = {"websites": {}, "cities": {}, "operations": {}, "products": {}}
        current: Optional[str] = None
        try:
            with csv_path.open("r", encoding="utf-8-sig") as handle:
                reader = csv.reader(handle)
                for row in reader:
                    if not row:
                        continue
                    header = row[0].strip()
                    if not header:
                        continue
                    lower = header.lower()
                    if lower.startswith("1. paginaweb"):
                        current = "websites"
                        continue
                    if lower.startswith("2. ciudad"):
                        current = "cities"
                        continue
                    if lower.startswith("3. operacion"):
                        current = "operations"
                        continue
                    if lower.startswith("4. producto"):
                        current = "products"
                        continue
                    if current and len(row) >= 2:
                        raw_value = row[0].strip()
                        canonical = row[1].strip() or raw_value
                        aliases[current][raw_value] = canonical
        except Exception as exc:  # pragma: no cover - diagnóstico opcional
            raise ConfigError(f"No se pudieron leer las variables desde {csv_path}: {exc}") from exc
        return aliases
