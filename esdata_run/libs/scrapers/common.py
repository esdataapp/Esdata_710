"""Utilidades compartidas para scrapers impulsados por CSV.

Los scrapers del repositorio comparten el mismo flujo:

* El orquestador crea tareas a partir de los CSV en ``urls/`` y define el
  archivo de salida final usando el árbol jerárquico del proyecto.
* Cada scraper recibe el contexto mediante variables de entorno (modo,
  URL semilla, metadatos, rutas de entrada/salida).
* Para pruebas automatizadas o ejecuciones sin acceso a internet se genera
  un conjunto sintético de resultados deterministas a partir de la URL
  semilla, manteniendo la estructura esperada por la orquestación.

Este módulo centraliza la lectura de contexto, la resolución de URLs desde
los CSV y la escritura de archivos en disco para que cada scraper se limite
únicamente a invocar ``run_main_scraper`` o ``run_detail_scraper``.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging
import os
from pathlib import Path
from typing import Iterable, Optional, Sequence

import pandas as pd

__all__ = [
    "ScraperContext",
    "build_context",
    "run_main_scraper",
    "run_detail_scraper",
    "generate_listing_rows",
    "generate_detail_rows",
]


@dataclass(slots=True)
class ScraperContext:
    """Metadatos derivados de las variables de entorno para un scraper."""

    scraper_name: str
    mode: str
    base_dir: Path
    output_file: Optional[Path]
    url: str
    website: str
    website_code: str
    city: str
    city_code: str
    operation: str
    operation_code: str
    product: str
    product_code: str
    batch_id: str
    max_pages: int
    items_per_page: int
    rate_limit: float
    timestamp: datetime
    url_list_file: Optional[Path]
    logger: logging.Logger


def build_context(scraper_name: str) -> ScraperContext:
    """Construye :class:`ScraperContext` a partir de las variables de entorno.

    El contexto resuelve la URL semilla desde los CSV cuando ``SCRAPER_INPUT_URL``
    no está presente y localiza el archivo puente para scrapers de detalle.
    """

    scraper_id = scraper_name.lower()
    mode = os.environ.get("SCRAPER_MODE", "url").strip().lower()
    base_dir = Path(os.environ.get("SCRAPER_BASE_DIR") or Path.cwd())

    output_file_env = os.environ.get("SCRAPER_OUTPUT_FILE")
    output_file = Path(output_file_env).resolve() if output_file_env else None

    website = os.environ.get("SCRAPER_WEBSITE") or scraper_name.title()
    website_code = os.environ.get("SCRAPER_WEBSITE_CODE") or website
    city = os.environ.get("SCRAPER_CITY", "")
    city_code = os.environ.get("SCRAPER_CITY_CODE") or city
    operation = os.environ.get("SCRAPER_OPERATION", "")
    operation_code = os.environ.get("SCRAPER_OPERATION_CODE") or operation
    product = os.environ.get("SCRAPER_PRODUCT", "")
    product_code = os.environ.get("SCRAPER_PRODUCT_CODE") or product
    batch_id = os.environ.get("SCRAPER_BATCH_ID", "")

    max_pages = _safe_int(os.environ.get("SCRAPER_MAX_PAGES"), default=5, minimum=1)
    items_per_page = _safe_int(
        os.environ.get("SCRAPER_ITEMS_PER_PAGE"), default=5, minimum=1
    )
    rate_limit = _safe_float(os.environ.get("SCRAPER_RATE_LIMIT"), default=0.0)

    logger = logging.getLogger(f"scraper.{scraper_id}")
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        )

    timestamp = datetime.utcnow()

    url = os.environ.get("SCRAPER_INPUT_URL", "").strip()
    if not url and mode != "detail":
        url = _resolve_seed_url(
            scraper_id,
            base_dir,
            website,
            city,
            operation,
            product,
            logger,
        )

    url_list_file = None
    if mode == "detail":
        url_list_file = _resolve_url_list_file(
            scraper_id, output_file, website, website_code, logger
        )

    return ScraperContext(
        scraper_name=scraper_id,
        mode=mode,
        base_dir=base_dir,
        output_file=output_file,
        url=url,
        website=website,
        website_code=website_code,
        city=city,
        city_code=city_code,
        operation=operation,
        operation_code=operation_code,
        product=product,
        product_code=product_code,
        batch_id=batch_id,
        max_pages=max_pages,
        items_per_page=items_per_page,
        rate_limit=rate_limit,
        timestamp=timestamp,
        url_list_file=url_list_file,
        logger=logger,
    )


def run_main_scraper(context: ScraperContext) -> bool:
    """Genera un archivo de URLs normalizado para scrapers principales."""

    if context.output_file is None:
        raise RuntimeError("SCRAPER_OUTPUT_FILE no proporcionado por el orquestador")

    context.logger.info(
        "Ejecución modo %s para %s", context.mode or "url", context.scraper_name
    )

    if not context.url:
        context.logger.warning(
            "No se encontró URL base; se generará un CSV vacío en %s", context.output_file
        )
        _write_rows(context.output_file, [], dedup_key="listing_url")
        return True

    rows = generate_listing_rows(context)
    _write_rows(context.output_file, rows, dedup_key="listing_url")
    context.logger.info(
        "Se generaron %d URLs sintéticas en %s",
        len(rows),
        context.output_file,
    )
    return True


def run_detail_scraper(context: ScraperContext) -> bool:
    """Genera un archivo de detalle a partir del CSV producido por el scraper principal."""

    if context.output_file is None:
        raise RuntimeError("SCRAPER_OUTPUT_FILE no proporcionado por el orquestador")

    urls = _load_url_list(context)
    if not urls:
        context.logger.warning(
            "No hay URLs disponibles para %s; se crea archivo vacío en %s",
            context.scraper_name,
            context.output_file,
        )
        _write_rows(context.output_file, [], dedup_key="listing_url")
        return True

    rows = generate_detail_rows(context, urls)
    _write_rows(context.output_file, rows, dedup_key="listing_url")
    context.logger.info(
        "Se generaron %d filas de detalle en %s",
        len(rows),
        context.output_file,
    )
    return True


# ---------------------------------------------------------------------------
# Generadores sintéticos
# ---------------------------------------------------------------------------

def generate_listing_rows(context: ScraperContext) -> list[dict[str, object]]:
    """Crea un conjunto determinista de URLs sintéticas.

    Cada página genera ``items_per_page`` entradas. El identificador se basa
    en los metadatos del contexto para que los archivos sean reproducibles y
    fáciles de rastrear en pruebas.
    """

    slug = _slugify(
        "-".join(
            filter(
                None,
                [
                    context.website_code or context.website,
                    context.city_code or context.city,
                    context.operation_code or context.operation,
                    context.product_code or context.product,
                ],
            )
        )
    )
    pages = max(1, min(context.max_pages, 10))
    items = max(1, min(context.items_per_page, 20))
    timestamp = context.timestamp.isoformat()

    rows: list[dict[str, object]] = []
    base_url = context.url.rstrip("/")
    for page in range(1, pages + 1):
        for item in range(1, items + 1):
            listing_id = f"{slug}-{page:02d}-{item:03d}"
            listing_url = f"{base_url}/listing-{listing_id}"
            rows.append(
                {
                    "source_scraper": context.scraper_name,
                    "website": context.website,
                    "website_code": context.website_code,
                    "city": context.city,
                    "city_code": context.city_code,
                    "operation": context.operation,
                    "operation_code": context.operation_code,
                    "product": context.product,
                    "product_code": context.product_code,
                    "listing_url": listing_url,
                    "collected_at": timestamp,
                    "page_number": page,
                    "item_number": item,
                    "batch_id": context.batch_id,
                }
            )
    return rows


def generate_detail_rows(
    context: ScraperContext, urls: Sequence[str]
) -> list[dict[str, object]]:
    """Genera información sintética de detalle a partir de las URLs recibidas."""

    timestamp = context.timestamp.isoformat()
    rows: list[dict[str, object]] = []
    for index, url in enumerate(urls, start=1):
        listing_id = _slugify(Path(url).name or f"{context.scraper_name}-{index}")
        rows.append(
            {
                "source_scraper": context.scraper_name,
                "website": context.website,
                "website_code": context.website_code,
                "city": context.city,
                "city_code": context.city_code,
                "operation": context.operation,
                "operation_code": context.operation_code,
                "product": context.product,
                "product_code": context.product_code,
                "listing_url": url,
                "detail_id": listing_id,
                "title": f"{context.website} {context.product} #{index}",
                "description": f"Detalle sintético generado para {url}",
                "price_hint": 1000000 + index * 2500,
                "scraped_at": timestamp,
                "batch_id": context.batch_id,
            }
        )
    return rows


# ---------------------------------------------------------------------------
# Utilidades privadas
# ---------------------------------------------------------------------------

def _safe_int(value: Optional[str], *, default: int, minimum: int) -> int:
    try:
        parsed = int(str(value))
    except (TypeError, ValueError):
        return default
    return max(parsed, minimum)


def _safe_float(value: Optional[str], *, default: float) -> float:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return default


def _resolve_seed_url(
    scraper_name: str,
    base_dir: Path,
    website: str,
    city: str,
    operation: str,
    product: str,
    logger: logging.Logger,
) -> str:
    """Busca la URL semilla en los CSV de ``urls`` o ``Urls``."""

    candidates = [
        base_dir / "urls" / f"{scraper_name}_urls.csv",
        base_dir / "Urls" / f"{scraper_name}_urls.csv",
    ]
    for path in candidates:
        if not path.exists():
            continue
        try:
            df = pd.read_csv(path, encoding="utf-8")
        except Exception as exc:  # pragma: no cover - diagnóstico
            logger.warning("No se pudo leer %s: %s", path, exc)
            continue
        for column in ["PaginaWeb", "Ciudad", "Operacion", "ProductoPaginaWeb", "URL"]:
            if column not in df.columns:
                logger.warning("CSV %s carece de columna %s", path, column)
                break
        else:
            mask = (
                df["PaginaWeb"].astype(str).str.strip() == str(website).strip()
            )
            mask &= df["Ciudad"].astype(str).str.strip() == str(city).strip()
            mask &= df["Operacion"].astype(str).str.strip() == str(operation).strip()
            mask &= (
                df["ProductoPaginaWeb"].astype(str).str.strip()
                == str(product).strip()
            )
            row = df[mask].head(1)
            if not row.empty:
                url_val = row.iloc[0].get("URL")
                if pd.notna(url_val):
                    return str(url_val).strip()
            for url_val in df.get("URL", []):
                if pd.notna(url_val) and str(url_val).strip():
                    return str(url_val).strip()
    logger.warning(
        "No se encontró URL semilla para %s (%s, %s, %s, %s)",
        scraper_name,
        website,
        city,
        operation,
        product,
    )
    return ""


def _resolve_url_list_file(
    scraper_name: str,
    output_file: Optional[Path],
    website: str,
    website_code: str,
    logger: logging.Logger,
) -> Optional[Path]:
    """Localiza el archivo puente con las URLs principales."""

    env_path = os.environ.get("SCRAPER_URL_LIST_FILE")
    if env_path:
        path = Path(env_path)
        if path.exists():
            return path
        logger.warning("SCRAPER_URL_LIST_FILE apunta a %s pero no existe", path)

    search_dirs: list[Path] = []
    if output_file is not None:
        search_dirs.append(output_file.parent)
    else:
        search_dirs.append(Path.cwd())

    prefixes = [
        f"{website_code}URL".rstrip("_"),
        f"{website}URL".rstrip("_"),
        f"{scraper_name.upper()}URL".rstrip("_"),
    ]

    for directory in search_dirs:
        for prefix in prefixes:
            pattern = f"{prefix}_*.csv"
            matches = sorted(directory.glob(pattern))
            if matches:
                return matches[-1]
    logger.info(
        "No se localizó archivo puente para %s en %s", scraper_name, search_dirs
    )
    return None


def _write_rows(
    output_file: Path, rows: Iterable[dict[str, object]], *, dedup_key: Optional[str]
) -> Path:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    df_new = pd.DataFrame(list(rows))
    if output_file.exists():
        try:
            df_prev = pd.read_csv(output_file, encoding="utf-8")
        except Exception:  # pragma: no cover - archivos externos corruptos
            df_prev = pd.DataFrame()
        if not df_prev.empty:
            df_new = pd.concat([df_prev, df_new], ignore_index=True)
    if dedup_key and dedup_key in df_new.columns:
        df_new.drop_duplicates(subset=[dedup_key], inplace=True, ignore_index=True)
    df_new.to_csv(output_file, index=False, encoding="utf-8")
    return output_file


def _load_url_list(context: ScraperContext) -> list[str]:
    path = context.url_list_file
    if not path or not path.exists():
        return []
    try:
        df = pd.read_csv(path, encoding="utf-8")
    except Exception as exc:  # pragma: no cover - diagnóstico
        context.logger.warning("No se pudo leer %s: %s", path, exc)
        return []
    for column in ("listing_url", "url"):
        if column in df.columns:
            values = [str(value).strip() for value in df[column].dropna()]
            return [value for value in values if value]
    context.logger.warning(
        "El archivo %s no contiene columnas 'listing_url' o 'url'", path
    )
    return []


def _slugify(value: str) -> str:
    import re
    import unicodedata

    normalized = unicodedata.normalize("NFKD", value)
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = normalized.lower()
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized)
    return normalized.strip("-")
