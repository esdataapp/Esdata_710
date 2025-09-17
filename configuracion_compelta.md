# Guía de Configuración Completa

Este documento explica cómo preparar y verificar el sistema de orquestación en un servidor Ubuntu 24.04 limpio.

## 1. Preparación del entorno

1. Instalar dependencias del sistema:
   ```bash
   sudo apt update
   sudo apt install -y python3 python3-venv python3-pip chromium-browser
   ```
2. Clonar el repositorio y crear entorno virtual:
   ```bash
   git clone <repo>
   cd Esdata_710
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

## 2. Verificación de archivos base

| Carpeta | Descripción |
|---------|-------------|
| `Scrapers/` | Contiene los scrapers adaptados. Deben existir `cyt.py`, `inm24.py`, `inm24_det.py`, `lam.py`, `lam_det.py`, `mit.py`, `prop.py`, `tro.py`. |
| `urls/` | CSV de orquestación (`*_urls.csv`). Cada archivo debe tener las columnas `PaginaWeb`, `Ciudad`, `Operacion`, `ProductoPaginaWeb`, `URL`. |
| `Lista de Variables/` | Contiene `Lista de Variables Orquestacion.csv` con las abreviaturas oficiales. |
| `config/config.yaml` | Configuración central del sistema. |

Ejecute el validador para confirmar la estructura:

```bash
python validate_system.py
```

Todas las validaciones deben mostrar `✅`.

## 3. Configuración de scraping

1. **Actualizar URLs**: edite los CSV en `urls/` respetando el orden en que se desean ejecutar. Cada fila representa una tarea.
2. **Configurar prioridades** en `config/config.yaml`:
   ```yaml
   execution:
     max_parallel_scrapers: 8
     max_retry_attempts: 3
     retry_delay_minutes: 30

   websites:
     Inm24:
       priority: 1
       has_detail_scraper: true
     Lam:
       priority: 3
       has_detail_scraper: true
   ```
3. **Revisar límites** (`max_pages_per_session`, `rate_limit_seconds`) por sitio si es necesario.

## 4. Ejecución

1. **Planificación** (opcional):
   ```bash
   python orchestrator.py plan
   ```
2. **Ejecución**:
   ```bash
   python orchestrator.py run
   ```
   El orquestador generará un lote con identificador `<Mes><Año>_<01|02>` y lo guardará en `orchestrator.db`.
3. **Reanudación** después de un corte:
   ```bash
   python orchestrator.py resume
   ```

Los datos se almacenan en `data/<PaginaWeb>/<Ciudad>/<Operacion>/<Producto>/<MesAño>/<Ejecución>/`.

## 5. Monitoreo diario

- Resumen general: `python monitor_cli.py overview`
- Historial de lotes: `python monitor_cli.py batches --limit 5`
- Tareas pendientes/fallidas: `python monitor_cli.py tasks --status pending failed`

## 6. Copias de seguridad y limpieza

- La base de datos SQLite (`orchestrator.db`) y los CSV generados pueden copiarse a otro destino para respaldos.
- Los lotes antiguos pueden comprimirse manualmente conservando la estructura de carpetas.

## 7. Checklist final

- [ ] `requirements.txt` instalado en el entorno virtual.
- [ ] `validate_system.py` sin errores.
- [ ] CSV de `urls/` revisados y ordenados.
- [ ] `config/config.yaml` actualizado con prioridades y límites correctos.
- [ ] Prueba de ejecución (`python orchestrator.py run --dry-run` seguida de `python orchestrator.py run`).
- [ ] Monitoreo funcionando (`python monitor_cli.py overview`).

Con estos pasos el sistema queda listo para ejecutarse en producción y reanudarse automáticamente ante cualquier interrupción.
