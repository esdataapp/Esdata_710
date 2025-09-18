#!/usr/bin/env python3
"""Alias histórico para ejecutar el nuevo orquestador."""
import sys

import orchestrator


def main() -> None:
    if len(sys.argv) == 1:
        sys.argv.append("run")
    orchestrator.main()


if __name__ == "__main__":
    main()
