# Carpeta `legacy`

Esta carpeta contiene los módulos de la versión original del sistema de orquestación:

- `Controlador.py`
- `Orquestador.py`
- `Herramientas.py`

Se preservan únicamente como referencia histórica durante la transición hacia la arquitectura basada en:

- `orchestrator.py`
- `scraper_adapter.py`
- Base de datos SQLite (`orchestrator.db`)
- `monitor_cli.py`

No deben usarse en producción ni mezclarse con la nueva ejecución.

## Próxima eliminación
Una vez completada la fase de armonización (adaptación de scrapers al nuevo flujo y migración total de paths), esta carpeta podrá eliminarse.
