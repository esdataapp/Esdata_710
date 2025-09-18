#!/usr/bin/env python3
"""Scraper sintético para Inmuebles24 (fase de URLs).

El flujo oficial indica que ``inm24.py`` produce un archivo puente con las URLs
que posteriormente consumirá ``inm24_det.py``. Este refactor delega la lógica
común al módulo ``esdata.scrapers.common`` y genera un dataset determinista que
respeta las abreviaturas y la jerarquía de carpetas definida por el
orquestador.
"""
from __future__ import annotations

from esdata.scrapers.common import build_context, run_main_scraper


def main() -> bool:
    context = build_context("inm24")
    # Inmuebles24 suele producir más listados por página; elevamos el valor
    # mínimo cuando se ejecuta en modo URL para obtener archivos menos vacíos
    # durante pruebas automatizadas.
    if context.mode != "detail" and context.items_per_page < 10:
        context.items_per_page = 10
    return run_main_scraper(context)


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
