#!/usr/bin/env python3
"""Scraper de detalle sintético para Inmuebles24.

Consume el archivo de URLs generado por ``inm24.py`` y crea registros de detalle
con información determinista. El objetivo es facilitar pruebas de la
orquestación y del encadenamiento de scrapers sin depender de automatización
real sobre el sitio web.
"""
from __future__ import annotations

import os

from esdata.scrapers.common import build_context, run_detail_scraper


def main() -> bool:
    context = build_context("inm24_det")
    if context.mode != "detail":
        # Permite ejecutar el script manualmente sin depender del orquestador.
        os.environ["SCRAPER_MODE"] = "detail"
        context = build_context("inm24_det")
    return run_detail_scraper(context)


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
