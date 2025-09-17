#!/usr/bin/env python3
"""Scraper sintético para Casas y Terrenos (CyT).

El orquestador proporciona la URL semilla y el archivo de salida. Este script
utiliza utilidades compartidas para generar un conjunto determinista de URLs que
simulan el resultado de un scraping real. El objetivo es validar la
orquestación, la nomenclatura de carpetas y los procesos de encadenamiento sin
requerir acceso a la web ni dependencias de Selenium.
"""
from __future__ import annotations

from esdata.scrapers.common import build_context, run_main_scraper


def main() -> bool:
    context = build_context("cyt")
    return run_main_scraper(context)


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
