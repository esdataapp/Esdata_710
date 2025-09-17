#!/usr/bin/env python3
"""Scraper sintético para Lamudi (fase de URLs)."""
from __future__ import annotations

from esdata.scrapers.common import build_context, run_main_scraper


def main() -> bool:
    context = build_context("lam")
    if context.mode != "detail" and context.items_per_page < 8:
        context.items_per_page = 8
    return run_main_scraper(context)


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
