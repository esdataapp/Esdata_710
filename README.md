# Sistema de Orquestación de Scraping Inmobiliario

La carpeta **Esdata_710** contiene una plataforma lista para coordinar scrapers
inmobiliarios guiados por archivos CSV. La orquestación es asíncrona, registra
todos los eventos en SQLite y genera los archivos siguiendo la jerarquía
``<PaginaWeb>/<Ciudad>/<Operacion>/<Producto>/<MesAño>/<Ejecución>``.  
Los scrapers incluidos son **sintéticos**: producen datos deterministas a partir
de las URLs del CSV para validar el flujo extremo a extremo sin depender de
Selenium ni acceso a internet. En producción se pueden sustituir fácilmente por
implementaciones reales reutilizando la misma infraestructura.

## 📦 Componentes

| Componente | Descripción |
|------------|-------------|
| `orchestrator.py` | CLI principal. Planea lotes, ejecuta scrapers en paralelo y gestiona reintentos. |
| `esdata/` | Paquete con la configuración, el repositorio SQLite, el scheduler y utilidades compartidas. |
| `esdata/scrapers/common.py` | API de apoyo para leer contexto desde el orquestador y generar archivos normalizados. |
| `Scrapers/` | Scrapers principales y de detalle basados en `common.py`. Funcionan sin Selenium. |
| `Scrapers Originales/` | Código histórico de referencia. Se conserva pero no participa en la orquestación. |
| `monitor_cli.py` | Monitor en terminal para revisar lotes, tareas y métricas rápidas. |
| `validate_system.py` | Verificador de instalación (estructura de carpetas, CSV, scrapers y base de datos). |

## 🗂️ Flujo general

1. Cada scraper tiene un CSV en `urls/` con las columnas obligatorias
   `PaginaWeb`, `Ciudad`, `Operacion`, `ProductoPaginaWeb`, `URL`.
2. El orquestador genera tareas respetando el orden del CSV y crea un lote con
   identificador `<Mes><Año>_<01|02>` dependiendo de la quincena actual.
3. Los scrapers principales (Inm24, Lam, CyT, Mit, Prop, Tro) producen archivos
   `*URL_...csv` con URLs sintéticas y los metadatos del lote.
4. Los scrapers de detalle (`inm24_det`, `lam_det`) leen el archivo puente y
   generan información adicional en el mismo directorio.
5. Todo el progreso queda registrado en `orchestrator.db` para permitir
   reanudaciones y análisis posteriores.

## ⚙️ Requisitos

- Python 3.12 o superior.
- Dependencias Python mínimas definidas en `requirements.txt`:
  `numpy`, `pandas`, `pyyaml`, `tabulate`, `psutil`.

Instalación recomendada:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> **Nota:** No se necesita Selenium ni controladores de navegador para ejecutar
> los scrapers incluidos. Para migrar a scraping real basta con sustituir la
> lógica sintética por la extracción deseada conservando la llamada a
> `build_context()` y `run_main_scraper()` / `run_detail_scraper()`.

## 🧾 Configuración

La configuración central está en `config/config.yaml`.

- `database.path`: ruta (relativa) del archivo SQLite.
- `data.base_path`: carpeta base de salida (`data/` por defecto).
- `execution.max_parallel_scrapers`: concurrencia máxima.
- `execution.max_retry_attempts`: intentos antes de marcar una tarea como fallida.
- `websites`: metadatos por sitio (prioridad, scraper de detalle, límites de páginas).
- `aliases`: normalización de los valores leídos desde los CSV (abreviaturas oficiales).

El archivo `Lista de Variables/Lista de Variables Orquestacion.csv` define las
abreviaturas que utiliza el sistema (por ejemplo `Inm24`, `Lam`, `Gdl`, `Ven`).

## ▶️ Ejecución básica

1. **Planificar tareas**
   ```bash
   python orchestrator.py plan
   ```

2. **Ejecutar un lote completo**
   ```bash
   python orchestrator.py run
   ```
   - Crea las carpetas destino siguiendo la jerarquía oficial.
   - Mantiene siempre activo el scraper prioritario (Inm24) y rota el resto
     según la prioridad configurada.
   - Cuando un scraper principal termina, libera automáticamente su scraper de
     detalle asociado.

3. **Reanudar un lote interrumpido**
   ```bash
   python orchestrator.py resume
   ```

4. **Filtrar scrapers específicos**
   ```bash
   python orchestrator.py run --scrapers inm24 lam
   ```

## 📊 Monitoreo y validación

- `python monitor_cli.py overview` – estado general del lote activo o del último
  completado.
- `python monitor_cli.py batches --limit 5` – historial resumido de ejecuciones.
- `python monitor_cli.py tasks --status pending failed` – detalle de tareas por estado.
- `python validate_system.py` – confirma que existan directorios, CSV, scrapers y
  tablas en la base de datos.

## 🗃️ Datos generados

Los archivos se almacenan en:

```
data/<PaginaWeb>/<Ciudad>/<Operacion>/<Producto>/<MesAño>/<Ejecución>/
```

Ejemplo con datos sintéticos:

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

Los scrapers sintéticos generan columnas como `listing_url`, `collected_at`,
`detail_id`, `price_hint`, etc. Estas columnas pueden sustituirse por datos
reales sin modificar la orquestación.

## 🛠️ Personalizar scrapers reales

1. Importar las utilidades compartidas:
   ```python
   from esdata.scrapers.common import build_context, run_main_scraper
   context = build_context("inm24")
   ```
2. Reemplazar la generación sintética por la lógica real (requests, Selenium,
   etc.) y escribir el CSV en `context.output_file`.
3. Mantener la estructura de columnas esperada (`listing_url`, metadatos del
   contexto) para preservar la compatibilidad con los scrapers de detalle.
4. Para scrapers de detalle utilizar `run_detail_scraper()` como referencia:
   el orquestador inyecta la ruta del archivo puente mediante
   `SCRAPER_URL_LIST_FILE`.

## 🚀 Próximos pasos sugeridos

- Sustituir los scrapers sintéticos por implementaciones reales utilizando la
  misma interfaz.
- Añadir monitorización avanzada (metrics server, dashboard) si se requiere.
- Integrar tareas de respaldo automático para `orchestrator.db` y los CSV.
- Crear servicios `systemd` apoyándose en el CLI existente (`Controlador.py`
  actúa como alias para compatibilidad con la generación anterior).

Con estos elementos el repositorio queda listo para ejecutar flujos de scraping
robustos, reanudables y documentados, además de servir como base para nuevas
integraciones empresariales.
