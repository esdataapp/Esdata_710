"""Utility helpers to normalize and map descriptive values to abbreviations."""
from __future__ import annotations

import csv
import logging
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, Optional

LOGGER = logging.getLogger(__name__)

DEFAULT_CSV_PATH = (
    Path(__file__).resolve().parent
    / "Lista de Variables"
    / "Lista de Variables Orquestacion.csv"
)


def _normalize_key(value: str) -> str:
    """Return a lowercase key suitable for dictionary lookups."""
    text = str(value).strip()
    if not text:
        return ""
    return unicodedata.normalize("NFKC", text).lower()


class AbbreviationResolver:
    """Translate descriptive values into their configured abbreviations."""

    def __init__(self, csv_path: Optional[Path] = None, *, strict: bool = False) -> None:
        self.csv_path = Path(csv_path) if csv_path else DEFAULT_CSV_PATH
        self.strict = strict
        self._mapping, self._abbr_lookup = self._load_mapping(self.csv_path)
        self._reported_missing: set[str] = set()

    @staticmethod
    @lru_cache(maxsize=4)
    def _load_mapping(path: Path) -> tuple[Dict[str, str], Dict[str, str]]:
        if not path.exists():
            raise FileNotFoundError(f"No se encontró el archivo de abreviaturas: {path}")

        mapping: Dict[str, str] = {}
        abbr_lookup: Dict[str, str] = {}

        with path.open(newline="", encoding="utf-8") as csvfile:
            reader = csv.reader(csvfile)
            rows = list(reader)

        if not rows:
            raise ValueError(f"El archivo de abreviaturas está vacío: {path}")

        header = rows[0]
        if len(header) < 2 or header[0].strip().lower() not in {"variable", "valor"}:
            # El archivo no tiene encabezado estándar; procesar todas las filas
            data_rows = rows
        else:
            data_rows = rows[1:]

        for row in data_rows:
            if len(row) < 2:
                continue
            raw_value, raw_abbr = row[0].strip(), row[1].strip()
            if not raw_value or not raw_abbr:
                continue
            key = _normalize_key(raw_value)
            mapping[key] = raw_abbr
            abbr_lookup[_normalize_key(raw_abbr)] = raw_abbr

        if not mapping:
            raise ValueError(
                "No se pudieron cargar abreviaturas desde el archivo proporcionado."
            )

        return mapping, abbr_lookup

    def to_abbreviation(self, value: Optional[str], *, context: str = "") -> str:
        """Return the abbreviation for *value*."""
        if value is None:
            return ""
        text = str(value).strip()
        if not text:
            return ""

        key = _normalize_key(text)
        if key in self._mapping:
            return self._mapping[key]
        if key in self._abbr_lookup:
            return self._abbr_lookup[key]

        if self.strict:
            raise KeyError(f"No se encontró abreviatura para '{value}' ({context})")

        if key not in self._reported_missing:
            LOGGER.warning("No se encontró abreviatura para '%s' (%s)", text, context)
            self._reported_missing.add(key)

        return text

    def ensure_all(self, values: Iterable[str], *, context: str = "") -> Dict[str, str]:
        """Resolve a collection of values and return a mapping original->abbreviation."""
        result: Dict[str, str] = {}
        for value in values:
            result[value] = self.to_abbreviation(value, context=context)
        return result


def get_resolver(csv_path: Optional[Path] = None, *, strict: bool = False) -> AbbreviationResolver:
    """Convenience factory that reuses cached mappings."""
    return AbbreviationResolver(csv_path=csv_path, strict=strict)
