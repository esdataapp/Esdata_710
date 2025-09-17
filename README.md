# Sistema de Orquestación de Scraping Inmobiliario

Este repositorio contiene una plataforma completa para ejecutar y monitorear scrapers inmobiliarios en Ubuntu 24.04. La nueva
arquitectura está centrada en un orquestador asíncrono que coordina los scrapers principales y de detalle a partir de los CSV de
la carpeta `urls/`, registra el estado en SQLite y organiza los datos en un árbol jerárquico listo para análisis.

## 📦 Componentes principales

| Componente | Descripción |
|------------|-------------|
| `orchestrator.py` | CLI principal. Carga los CSV, genera lotes y ejecuta los scrapers respetando dependencias y prioridades. |
| `esdata/` | Paquete con la lógica interna (configuración, base de datos, scheduler, normalización de variables). |
| `scraper_adapter.py` | Adaptador que expone una interfaz uniforme para los scrapers existentes y valida sus salidas. |
| `monitor_cli.py` | CLI ligera para consultar estados de lotes y tareas desde la terminal de Linux. |
| `validate_system.py` | Verificador rápido para confirmar estructura de carpetas, CSV, scrapers y esquema de base de datos. |
| `Scrapers/` | Scrapers principales y de detalle. Reciben parámetros mediante variables de entorno. |
| `urls/` | CSV de entrada que definen `PaginaWeb`, `Ciudad`, `Operacion`, `ProductoPaginaWeb` y `URL`.

## 🗂️ Estructura de directorios

```
Esdata_710/
├── config/                # config.yaml y ajustes adicionales
├── data/                  # Salidas de scraping organizadas por sitio/ciudad/operación/producto/mes/lote
├── logs/                  # Registros del orquestador y utilidades
├── Scrapers/              # Scrapers principales y de detalle
├── urls/                  # CSV de orquestación (un archivo por scraper)
├── esdata/                # Código fuente de la nueva arquitectura
├── orchestrator.db        # Base de datos SQLite con tareas y lotes
├── orchestrator.py        # Orquestador CLI
├── monitor_cli.py         # Monitor en terminal
├── scraper_adapter.py     # Adaptador de scrapers
└── validate_system.py     # Validador de instalación
```

## ⚙️ Requisitos

- Python 3.12 o superior
- Paquetes listados en `requirements.txt`
- Google Chrome/Chromium y controlador compatible (para scrapers Selenium)

Instalación de dependencias:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 🧾 Configuración

La configuración central se encuentra en `config/config.yaml`. Los valores más relevantes son:

- `database.path`: ruta (relativa al proyecto) del archivo SQLite.
- `data.base_path`: carpeta raíz donde se guardan los CSV generados.
- `data.urls_path`: carpeta con los CSV de orquestación.
- `execution.max_parallel_scrapers`: número máximo de scrapers simultáneos.
- `execution.max_retry_attempts`: intentos por tarea antes de marcarla como fallida.
- `websites`: metadatos por sitio (prioridad, scraper de detalle, rate limiting, etc.).
- `aliases`: normalización de nombres leídos desde los CSV.

El archivo `Lista de Variables/Lista de Variables Orquestacion.csv` define abreviaturas oficiales para sitios, ciudades, operaciones y productos. El orquestador las carga automáticamente.

## ▶️ Ejecución del orquestador

1. **Planificar** sin ejecutar:
   ```bash
   python orchestrator.py plan
   ```
   Muestra cuántas tareas se generarán por scraper y cuántas son de detalle.

2. **Ejecutar** un lote completo:
   ```bash
   python orchestrator.py run
   ```
   - Lee todos los CSV de `urls/`.
   - Genera un lote con identificador `<Mes><Año>_<01|02>` según la quincena.
   - Ejecuta los scrapers respetando prioridades (Inm24 siempre activo + rotación del resto) y libera automáticamente los scrapers de detalle.
   - Registra cada tarea en `orchestrator.db` con estados `pending`, `running`, `retrying`, `completed`, `failed` o `blocked`.

3. **Reanudar** un lote interrumpido:
   ```bash
   python orchestrator.py resume
   ```
   Si el lote anterior quedó en estado `running`, el scheduler retomará las tareas pendientes.

4. **Restringir scrapers** específicos:
   ```bash
   python orchestrator.py run --scrapers inm24 lam
   ```

## 📊 Monitoreo en terminal

El script `monitor_cli.py` expone comandos simples para consultar el estado sin necesidad de dashboards externos:

```bash
python monitor_cli.py overview         # Resumen del lote activo o último finalizado
python monitor_cli.py batches --limit 5 # Historial de los últimos lotes
python monitor_cli.py tasks --status pending running --batch Sep25_01
```

Las salidas se presentan en tablas tipo Markdown para copiarlas fácilmente a reportes o chats internos.

## ✅ Validación rápida

Antes de poner en marcha el sistema en un servidor limpio, ejecute:

```bash
python validate_system.py
```

El validador comprueba la estructura de carpetas, que los CSV contengan las columnas obligatorias, que los scrapers existan y que la base de datos tenga el esquema mínimo (`scraping_tasks`, `execution_batches`).

## 🗃️ Organización de datos

Cada tarea genera los archivos en `data/<PaginaWeb>/<Ciudad>/<Operacion>/<Producto>/<MesAño>/<Ejecución>/`. Los scrapers principales producen archivos con sufijo `URL_...`, mientras que los scrapers de detalle escriben en la misma carpeta sin el sufijo. Ejemplo:

```
data/
└── Inm24/
    └── Gdl/
        └── Ven/
            └── Dep/
                └── Sep25/
                    └── 01/
                        ├── Inm24URL_Gdl_Ven_Dep_Sep25_01.csv
                        └── Inm24_Gdl_Ven_Dep_Sep25_01.csv
```

## 📄 Licencia

Este proyecto se distribuye bajo la licencia MIT. Consulte el archivo `LICENSE` para más información.
