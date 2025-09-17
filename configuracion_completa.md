# Guía de Configuración Completa

Este documento resume el proceso para poner en marcha el sistema de
orquestación en un servidor Ubuntu 24.04 limpio y validar que los flujos
sintéticos funcionan correctamente.

## 1. Preparación del entorno

1. Instalar dependencias del sistema:
   ```bash
   sudo apt update
   sudo apt install -y python3 python3-venv python3-pip
   ```
2. Clonar el repositorio y crear un entorno virtual:
   ```bash
   git clone <repo>
   cd Esdata_710
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

## 2. Verificación rápida

- La carpeta `Scrapers/` debe contener los scrapers adaptados:
  `cyt.py`, `inm24.py`, `inm24_det.py`, `lam.py`, `lam_det.py`, `mit.py`,
  `prop.py`, `tro.py`.
- `Scrapers Originales/` conserva la versión previa como referencia.
- Los CSV de entrada residen en `urls/` y deben tener las columnas
  `PaginaWeb`, `Ciudad`, `Operacion`, `ProductoPaginaWeb`, `URL`.
- `config/config.yaml` contiene la configuración central y las abreviaturas.

Ejecutar el validador para comprobar estructura y base de datos:

```bash
python validate_system.py
```

Todos los chequeos deberían mostrar `✅`.

## 3. Configuración del scraping

1. Actualizar los CSV en `urls/` respetando el orden deseado de ejecución.
2. Revisar prioridades y límites en `config/config.yaml`:
   ```yaml
   execution:
     max_parallel_scrapers: 8
     retry_delay_minutes: 30
   websites:
     Inm24:
       priority: 1
       has_detail_scraper: true
   ```
3. Confirmar que las abreviaturas usadas coinciden con las de la
   `Lista de Variables/Lista de Variables Orquestacion.csv`.

## 4. Ejecución típica

```bash
python orchestrator.py plan        # Revisión del plan
python orchestrator.py run         # Ejecuta el lote completo
python monitor_cli.py overview     # Estado en tiempo real
```

Los scrapers sintéticos generan archivos deterministas que respetan la jerarquía
oficial (`data/<PaginaWeb>/<Ciudad>/<Operacion>/<Producto>/<MesAño>/<Ejecución>/`).
Estos archivos sirven para validar la orquestación, el monitoreo y la base de
nomenclatura.

## 5. Sustituir por scrapers reales (opcional)

1. Abrir el scraper correspondiente en `Scrapers/` y reemplazar la lógica
   sintética por la extracción real conservando:
   ```python
   from esdata.scrapers.common import build_context, run_main_scraper
   context = build_context("inm24")
   ```
2. Escribir los resultados en `context.output_file` respetando las columnas
   `listing_url`, `collected_at`, etc.
3. Para scrapers de detalle usar `run_detail_scraper()` como guía; la ruta del
   archivo puente se inyecta en la variable `SCRAPER_URL_LIST_FILE`.

## 6. Checklist final

- [ ] `requirements.txt` instalado en el entorno virtual.
- [ ] `validate_system.py` sin errores.
- [ ] CSV de `urls/` revisados y ordenados.
- [ ] `config/config.yaml` actualizado con prioridades y límites correctos.
- [ ] Ejecución de prueba (`python orchestrator.py run`).
- [ ] Monitoreo funcionando (`python monitor_cli.py overview`).

Con estos pasos el sistema queda listo para operar y sirve como base para
integrar scrapers reales sin modificar la capa de orquestación.
