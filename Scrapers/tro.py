#!/usr/bin/env python3
"""Scraper sintético para Trovit."""
from __future__ import annotations

from esdata.scrapers.common import build_context, run_main_scraper


def main() -> bool:
    context = build_context("tro")
    return run_main_scraper(context)


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
