#!/usr/bin/env python3
"""Scraper de detalle sintético para Lamudi."""
from __future__ import annotations

import os

from esdata.scrapers.common import build_context, run_detail_scraper


def main() -> bool:
    context = build_context("lam_det")
    if context.mode != "detail":
        os.environ["SCRAPER_MODE"] = "detail"
        context = build_context("lam_det")
    return run_detail_scraper(context)


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
