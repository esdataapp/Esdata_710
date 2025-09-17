# 🔄 Flujo del Sistema de Orquestación de Scraping

## 📋 Índice

- [Descripción General del Flujo](#-descripción-general-del-flujo)
- [Flujo de Ejecución Principal](#-flujo-de-ejecución-principal)
- [Flujos de Scrapers Específicos](#-flujos-de-scrapers-específicos)
- [Gestión de Estados](#-gestión-de-estados)
- [Flujo de Manejo de Errores](#-flujo-de-manejo-de-errores)
- [Flujo de Datos](#-flujo-de-datos)
- [Flujo de Configuración](#️-flujo-de-configuración)
- [Flujo de Monitoreo](#-flujo-de-monitoreo)

## 🎯 Descripción General del Flujo

El sistema opera mediante un **flujo de orquestación coordinada** que ejecuta múltiples scrapers de forma inteligente, respetando dependencias, prioridades y límites de recursos.

### 🏗️ Principios del Flujo

1. **Ejecución por Fases**: Scrapers principales → Scrapers de detalle
2. **Dependencias Automáticas**: Los scrapers de detalle esperan a los principales
3. **Paralelización Inteligente**: Múltiples scrapers ejecutan simultáneamente cuando es posible
4. **Recuperación Automática**: Reintentos y recuperación ante fallos
5. **Trazabilidad Completa**: Cada paso es registrado y auditable

## 🚀 Flujo de Ejecución Principal

### 📊 Diagrama de Flujo Completo

```mermaid
flowchart TD
    START([Usuario inicia ejecución]) --> INIT[Inicializar Sistema]
    
    INIT --> VALIDATE{Validar Sistema}
    VALIDATE -->|Error| FAIL_INIT[Fallo de Inicialización]
    VALIDATE -->|OK| LOAD_CONFIG[Cargar Configuración]
    
    LOAD_CONFIG --> GEN_BATCH[Generar ID de Lote]
    GEN_BATCH --> LOAD_URLS[Cargar URLs desde CSVs]
    
    LOAD_URLS --> CREATE_TASKS[Crear Tareas en DB]
    CREATE_TASKS --> PLAN_EXEC[Planificar Ejecución]
    
    PLAN_EXEC --> PHASE1[FASE 1: Scrapers Principales]
    
    subgraph PHASE1_DETAIL [Fase 1: Ejecución Paralela]
        INM24[inm24.py - P1]
        CYT[cyt.py - P2]
        LAM[lam.py - P3]
        MIT[mit.py - P4]
        PROP[prop.py - P5]
        TRO[tro.py - P6]
    end
    
    PHASE1 --> PHASE1_DETAIL
    
    PHASE1_DETAIL --> CHECK_DEPS{Verificar Dependencias}
    CHECK_DEPS -->|URLs Generadas| PHASE2[FASE 2: Scrapers de Detalle]
    CHECK_DEPS -->|Sin Dependencias| FINALIZE[Finalizar Lote]
    
    subgraph PHASE2_DETAIL [Fase 2: Ejecución Secuencial]
        INM24_DET[inm24_det.py]
        LAM_DET[lam_det.py]
    end
    
    PHASE2 --> PHASE2_DETAIL
    PHASE2_DETAIL --> FINALIZE
    
    FINALIZE --> METRICS[Generar Métricas]
    METRICS --> BACKUP[Ejecutar Backup]
    BACKUP --> CLEANUP[Limpiar Temporales]
    CLEANUP --> NOTIFY[Enviar Notificaciones]
    NOTIFY --> END([Ejecución Completada])
    
    FAIL_INIT --> LOG_ERROR[Registrar Error]
    LOG_ERROR --> END
```

### ⏱️ Timeline de Ejecución

```mermaid
gantt
    title Cronograma de Ejecución de Scraping
    dateFormat X
    axisFormat %H:%M
    
    section Inicialización
    Validar Sistema     :init, 0, 2
    Cargar Config       :config, after init, 1
    Generar Lote        :batch, after config, 1
    Crear Tareas        :tasks, after batch, 2
    
    section Fase 1: Principales
    inm24.py (P1)       :inm24, after tasks, 8
    cyt.py (P2)         :cyt, after tasks, 6
    lam.py (P3)         :lam, after tasks, 7
    mit.py (P4)         :mit, after tasks, 5
    prop.py (P5)        :prop, after tasks, 4
    tro.py (P6)         :tro, after tasks, 3
    
    section Fase 2: Detalle
    inm24_det.py        :inm24det, after inm24, 5
    lam_det.py          :lamdet, after lam, 4
    
    section Finalización
    Generar Métricas    :metrics, after inm24det, 1
    Backup              :backup, after metrics, 2
    Notificaciones      :notify, after backup, 1
```

### 🔄 Estados del Flujo

```mermaid
stateDiagram-v2
    [*] --> Inicializando
    Inicializando --> Configurando
    Configurando --> Planificando
    Planificando --> EjecutandoFase1
    
    EjecutandoFase1 --> ProcesandoDependencias
    ProcesandoDependencias --> EjecutandoFase2 : Con dependencias
    ProcesandoDependencias --> Finalizando : Sin dependencias
    
    EjecutandoFase2 --> Finalizando
    Finalizando --> Completado
    
    Configurando --> Error : Error configuración
    EjecutandoFase1 --> Error : Error crítico
    EjecutandoFase2 --> Error : Error crítico
    Error --> Recuperando
    Recuperando --> EjecutandoFase1 : Recuperación exitosa
    Recuperando --> Error : Recuperación fallida
    
    Completado --> [*]
    Error --> [*]
```

## 🔧 Flujos de Scrapers Específicos

### 📊 Flujo de Scraper Principal (Ejemplo: CyT)

```mermaid
sequenceDiagram
    participant Orch as Orchestrator
    participant Adapter as Scraper Adapter
    participant CyT as cyt.py
    participant Web as CasasyTerrenos.com
    participant FS as File System
    participant DB as Database
    
    Orch->>Adapter: execute_scraper(cyt_task)
    Adapter->>Adapter: load_scraper_config(cyt)
    Adapter->>Adapter: modify_scraper_parameters()
    Adapter->>CyT: execute_main()
    
    loop Para cada página
        CyT->>Web: GET página con listings
        Web-->>CyT: HTML con propiedades
        CyT->>CyT: parse_page_source(html)
        CyT->>CyT: extract_property_data()
    end
    
    CyT->>FS: save_to_csv(data)
    FS-->>CyT: file_saved_successfully
    CyT-->>Adapter: execution_completed
    Adapter->>FS: move_to_final_location()
    Adapter->>DB: update_task_status(completed)
    Adapter-->>Orch: task_completed_successfully
```

### 🔗 Flujo de Scraper de Detalle (Ejemplo: Inm24_det)

```mermaid
sequenceDiagram
    participant Orch as Orchestrator
    participant Adapter as Scraper Adapter
    participant Det as inm24_det.py
    participant Main as URL File (inm24)
    participant Web as Inmuebles24.com
    participant FS as File System
    participant DB as Database
    
    Orch->>Adapter: execute_detail_scraper(inm24_det)
    Adapter->>FS: find_url_file(Inm24URL_*.csv)
    FS-->>Adapter: url_file_path
    
    Adapter->>Det: execute_with_urls(url_file)
    Det->>Main: read_urls_from_csv()
    
    loop Para cada URL de detalle
        Det->>Web: GET página de propiedad específica
        Web-->>Det: HTML con datos detallados
        Det->>Det: extract_detailed_data()
    end
    
    Det->>FS: save_detailed_data()
    Det-->>Adapter: detail_execution_completed
    Adapter->>DB: update_task_status(completed)
    Adapter-->>Orch: detail_task_completed
```

### ⚙️ Flujo de Configuración Dinámica

```mermaid
flowchart TD
    START([Inicio de Scraper]) --> LOAD_BASE[Cargar Config Base]
    LOAD_BASE --> GET_TASK[Obtener Task Info]
    GET_TASK --> ADAPT_CONFIG[Adaptar Configuración]
    
    ADAPT_CONFIG --> MODIFY_URL[Modificar URLs Base]
    MODIFY_URL --> SET_OUTPUT[Configurar Output Path]
    SET_OUTPUT --> APPLY_LIMITS[Aplicar Límites]
    
    APPLY_LIMITS --> INJECT_CONFIG[Inyectar en Scraper]
    INJECT_CONFIG --> EXECUTE[Ejecutar Scraper]
    
    EXECUTE --> MONITOR[Monitorear Ejecución]
    MONITOR --> CHECK_STATUS{Estado OK?}
    
    CHECK_STATUS -->|OK| SAVE_RESULTS[Guardar Resultados]
    CHECK_STATUS -->|Error| HANDLE_ERROR[Manejar Error]
    
    SAVE_RESULTS --> UPDATE_DB[Actualizar DB]
    UPDATE_DB --> FINISH([Completado])
    
    HANDLE_ERROR --> RETRY_LOGIC{¿Reintentar?}
    RETRY_LOGIC -->|Sí| EXECUTE
    RETRY_LOGIC -->|No| MARK_FAILED[Marcar como Fallido]
    MARK_FAILED --> FINISH
```

## 🎛️ Gestión de Estados

### 📊 Diagrama de Estados de Tareas

```mermaid
stateDiagram-v2
    [*] --> PENDING
    PENDING --> RUNNING : Scraper iniciado
    
    RUNNING --> COMPLETED : Éxito
    RUNNING --> FAILED : Error
    RUNNING --> TIMEOUT : Tiempo agotado
    
    FAILED --> RETRYING : Dentro de límite
    FAILED --> PERMANENTLY_FAILED : Máximo intentos
    
    RETRYING --> RUNNING : Nuevo intento
    TIMEOUT --> RETRYING : Reintento por timeout
    
    COMPLETED --> [*]
    PERMANENTLY_FAILED --> [*]
    
    note right of PENDING
        Tarea creada pero no iniciada
        Esperando en cola
    end note
    
    note right of RUNNING
        Scraper ejecutándose
        Monitoreando progreso
    end note
    
    note right of FAILED
        Error temporal
        Evaluar si reintentar
    end note
    
    note right of RETRYING
        Preparando nuevo intento
        Aplicando delay
    end note
```

### 🔄 Transiciones de Estado Permitidas

| Estado Actual | Estado Destino | Condición | Acción |
|---------------|----------------|-----------|---------|
| PENDING | RUNNING | Scraper disponible | Iniciar ejecución |
| RUNNING | COMPLETED | Éxito | Guardar resultados |
| RUNNING | FAILED | Error recuperable | Evaluar reintentos |
| RUNNING | TIMEOUT | Tiempo límite | Terminar proceso |
| FAILED | RETRYING | attempts < max_attempts | Programar reintento |
| FAILED | PERMANENTLY_FAILED | attempts >= max_attempts | Marcar como fallido |
| TIMEOUT | RETRYING | Timeout recuperable | Programar reintento |
| RETRYING | RUNNING | Delay completado | Reiniciar ejecución |

### 🎯 Gestión de Estados por Lote

```mermaid
flowchart TD
    NEW_BATCH[Nuevo Lote] --> INIT_TASKS[Inicializar Tareas]
    INIT_TASKS --> ALL_PENDING{Todas Pendientes?}
    
    ALL_PENDING -->|Sí| START_EXEC[Iniciar Ejecución]
    ALL_PENDING -->|No| ERROR_INIT[Error Inicialización]
    
    START_EXEC --> MONITOR_BATCH[Monitorear Lote]
    
    MONITOR_BATCH --> CHECK_PROGRESS{Verificar Progreso}
    CHECK_PROGRESS --> ANY_RUNNING{¿Hay Running?}
    
    ANY_RUNNING -->|Sí| CONTINUE_MONITOR[Continuar Monitoreo]
    ANY_RUNNING -->|No| ALL_COMPLETE{¿Todas Completas?}
    
    ALL_COMPLETE -->|Sí| BATCH_SUCCESS[Lote Exitoso]
    ALL_COMPLETE -->|No| BATCH_PARTIAL[Lote Parcial]
    
    CONTINUE_MONITOR --> CHECK_PROGRESS
    
    BATCH_SUCCESS --> FINALIZE[Finalizar]
    BATCH_PARTIAL --> FINALIZE
    ERROR_INIT --> FINALIZE
```

## ⚠️ Flujo de Manejo de Errores

### 🚨 Clasificación de Errores

```mermaid
flowchart TD
    ERROR[Error Detectado] --> CLASSIFY{Clasificar Error}
    
    CLASSIFY -->|Red| NETWORK_ERROR[Error de Red]
    CLASSIFY -->|Parsing| PARSING_ERROR[Error de Parsing]
    CLASSIFY -->|Sistema| SYSTEM_ERROR[Error de Sistema]
    CLASSIFY -->|Config| CONFIG_ERROR[Error de Configuración]
    
    NETWORK_ERROR --> RETRY_NET{¿Reintentar?}
    PARSING_ERROR --> RETRY_PARSE{¿Reintentar?}
    SYSTEM_ERROR --> CRITICAL{¿Crítico?}
    CONFIG_ERROR --> FIX_CONFIG[Requerir Corrección]
    
    RETRY_NET -->|Sí| WAIT_NETWORK[Esperar Red]
    RETRY_NET -->|No| LOG_NET_FAIL[Log Fallo Red]
    
    RETRY_PARSE -->|Sí| RETRY_PARSE_LOGIC[Reintento Parsing]
    RETRY_PARSE -->|No| LOG_PARSE_FAIL[Log Fallo Parsing]
    
    CRITICAL -->|Sí| STOP_SYSTEM[Detener Sistema]
    CRITICAL -->|No| ISOLATE_ERROR[Aislar Error]
    
    WAIT_NETWORK --> RETRY_EXECUTION[Reintentar Ejecución]
    RETRY_PARSE_LOGIC --> RETRY_EXECUTION
    ISOLATE_ERROR --> CONTINUE_OTHERS[Continuar Otros]
    
    LOG_NET_FAIL --> MARK_FAILED[Marcar Fallido]
    LOG_PARSE_FAIL --> MARK_FAILED
    FIX_CONFIG --> PAUSE_SYSTEM[Pausar Sistema]
    STOP_SYSTEM --> EMERGENCY_STOP[Parada de Emergencia]
```

### 🔄 Estrategias de Reintento

```python
class RetryStrategy:
    """Estrategias de reintento configurables"""
    
    def exponential_backoff(self, attempt, base_delay=30):
        """Backoff exponencial: 30s, 60s, 120s, 240s..."""
        return base_delay * (2 ** attempt)
    
    def linear_backoff(self, attempt, base_delay=30):
        """Backoff lineal: 30s, 60s, 90s, 120s..."""
        return base_delay * (attempt + 1)
    
    def fixed_delay(self, attempt, delay=30):
        """Delay fijo: 30s entre cada intento"""
        return delay
    
    def immediate_retry(self, attempt):
        """Reintento inmediato (para errores menores)"""
        return 0
```

### 📊 Flujo de Recuperación Automática

```mermaid
sequenceDiagram
    participant Orch as Orchestrator
    participant Task as Task Manager
    participant Retry as Retry Manager
    participant Scraper as Scraper
    participant Alert as Alert System
    
    Orch->>Task: execute_task()
    Task->>Scraper: run_scraper()
    Scraper-->>Task: ERROR
    
    Task->>Retry: should_retry(error, attempts)
    Retry-->>Task: yes, delay=60s
    
    Task->>Task: wait(60s)
    Task->>Scraper: run_scraper() [attempt 2]
    Scraper-->>Task: ERROR
    
    Task->>Retry: should_retry(error, attempts)
    Retry-->>Task: yes, delay=120s
    
    Task->>Task: wait(120s)
    Task->>Scraper: run_scraper() [attempt 3]
    Scraper-->>Task: SUCCESS
    
    Task->>Orch: task_completed
    
    alt Si hubiera fallado attempt 3
        Task->>Retry: should_retry(error, attempts)
        Retry-->>Task: no, max_attempts_reached
        Task->>Alert: send_alert(task_failed)
        Task->>Orch: task_permanently_failed
    end
```

## 📊 Flujo de Datos

### 🗂️ Estructura de Datos en el Flujo

```mermaid
flowchart LR
    subgraph INPUT [Entrada]
        CSV_URLS[CSVs de URLs]
        CONFIG[config.yaml]
        SCRAPERS[Scripts .py]
    end
    
    subgraph PROCESSING [Procesamiento]
        TASKS[Tareas en Memoria]
        ADAPTER[Adapter Logic]
        SCRAPERS_EXEC[Ejecución Scrapers]
    end
    
    subgraph STORAGE [Almacenamiento]
        DB[(SQLite DB)]
        FILES[Archivos CSV]
        LOGS[Log Files]
    end
    
    subgraph OUTPUT [Salida]
        ORGANIZED_DATA[Datos Organizados]
        METRICS[Métricas]
        REPORTS[Reportes]
    end
    
    CSV_URLS --> TASKS
    CONFIG --> ADAPTER
    SCRAPERS --> SCRAPERS_EXEC
    
    TASKS --> DB
    ADAPTER --> SCRAPERS_EXEC
    SCRAPERS_EXEC --> FILES
    
    DB --> METRICS
    FILES --> ORGANIZED_DATA
    LOGS --> REPORTS
    
    ORGANIZED_DATA --> OUTPUT
    METRICS --> OUTPUT
    REPORTS --> OUTPUT
```

### 📋 Formato de Datos Intermedios

#### **TaskInfo Structure**
```json
{
  "task_id": "uuid-string",
  "scraper_name": "cyt",
  "website": "CyT",
  "city": "Gdl",
  "operation": "Ven",
  "product": "Dep",
  "url": "https://example.com",
  "order": 1,
  "status": "pending",
  "attempts": 0,
  "max_attempts": 3,
  "created_at": "2025-09-16T10:00:00",
  "started_at": null,
  "completed_at": null,
  "error_message": null,
  "execution_batch": "Sep25_01",
  "output_path": "data/CyT/Gdl/Ven/Dep/Sep25/01/CyT_Gdl_Ven_Dep_Sep25_01.csv"
}
```

#### **BatchInfo Structure**
```json
{
  "batch_id": "Sep25_01",
  "month_year": "Sep25",
  "execution_number": 1,
  "started_at": "2025-09-16T10:00:00",
  "completed_at": null,
  "total_tasks": 28,
  "completed_tasks": 0,
  "failed_tasks": 0,
  "status": "running",
  "estimated_completion": "2025-09-16T11:30:00"
}
```

### 🔄 Transformaciones de Datos

```mermaid
flowchart TD
    CSV_INPUT[CSV URLs] --> PARSE_CSV[Parse CSV]
    PARSE_CSV --> VALIDATE_DATA[Validate Data]
    VALIDATE_DATA --> CREATE_TASKS[Create Task Objects]
    
    CREATE_TASKS --> ENRICH_TASKS[Enrich with Config]
    ENRICH_TASKS --> PRIORITIZE[Apply Priorities]
    PRIORITIZE --> SCHEDULE[Schedule Execution]
    
    SCHEDULE --> EXECUTE[Execute Scrapers]
    EXECUTE --> RAW_OUTPUT[Raw Scraper Output]
    
    RAW_OUTPUT --> NORMALIZE[Normalize Format]
    NORMALIZE --> VALIDATE_OUTPUT[Validate Output]
    VALIDATE_OUTPUT --> ORGANIZE[Organize by Structure]
    
    ORGANIZE --> FINAL_CSV[Final CSV Files]
    FINAL_CSV --> UPDATE_DB[Update Database]
    UPDATE_DB --> GENERATE_METRICS[Generate Metrics]
```

## ⚙️ Flujo de Configuración

### 🔧 Carga de Configuración

```mermaid
flowchart TD
    START[Inicio Sistema] --> CHECK_CONFIG{¿Config existe?}
    
    CHECK_CONFIG -->|No| CREATE_DEFAULT[Crear Config Default]
    CHECK_CONFIG -->|Sí| LOAD_CONFIG[Cargar config.yaml]
    
    CREATE_DEFAULT --> VALIDATE_DEFAULT[Validar Default]
    LOAD_CONFIG --> VALIDATE_CONFIG[Validar Configuración]
    
    VALIDATE_DEFAULT --> APPLY_CONFIG[Aplicar Configuración]
    VALIDATE_CONFIG -->|Válida| APPLY_CONFIG
    VALIDATE_CONFIG -->|Inválida| SHOW_ERRORS[Mostrar Errores]
    
    SHOW_ERRORS --> FIX_CONFIG{¿Corregir?}
    FIX_CONFIG -->|Sí| EDIT_CONFIG[Editar Configuración]
    FIX_CONFIG -->|No| USE_DEFAULT[Usar Default]
    
    EDIT_CONFIG --> VALIDATE_CONFIG
    USE_DEFAULT --> APPLY_CONFIG
    
    APPLY_CONFIG --> INIT_COMPONENTS[Inicializar Componentes]
    INIT_COMPONENTS --> READY[Sistema Listo]
```

### 🎯 Configuración por Scraper

```mermaid
sequenceDiagram
    participant Orch as Orchestrator
    participant Config as Config Manager
    participant Adapter as Scraper Adapter
    participant Scraper as Specific Scraper
    
    Orch->>Config: get_scraper_config(scraper_name)
    Config-->>Orch: base_config
    
    Orch->>Adapter: adapt_scraper(scraper_name, task_info, base_config)
    
    Adapter->>Adapter: load_scraper_specific_config()
    Adapter->>Adapter: apply_task_overrides()
    Adapter->>Adapter: calculate_dynamic_params()
    
    Adapter->>Scraper: inject_config(final_config)
    Scraper->>Scraper: apply_configuration()
    Scraper-->>Adapter: configuration_applied
    
    Adapter-->>Orch: scraper_configured
```

## 📊 Flujo de Monitoreo

### 📈 Recolección de Métricas

```mermaid
flowchart TD
    EVENTS[Eventos del Sistema] --> COLLECTORS[Collectors de Métricas]
    
    COLLECTORS --> TASK_METRICS[Métricas de Tareas]
    COLLECTORS --> SYSTEM_METRICS[Métricas de Sistema]
    COLLECTORS --> PERFORMANCE_METRICS[Métricas de Performance]
    
    TASK_METRICS --> AGGREGATOR[Agregador Central]
    SYSTEM_METRICS --> AGGREGATOR
    PERFORMANCE_METRICS --> AGGREGATOR
    
    AGGREGATOR --> STORAGE_METRICS[Almacenar en DB]
    AGGREGATOR --> REAL_TIME[Dashboard Tiempo Real]
    AGGREGATOR --> ALERTS[Sistema de Alertas]
    
    STORAGE_METRICS --> HISTORICAL[Análisis Histórico]
    REAL_TIME --> CLI_DISPLAY[Display CLI]
    ALERTS --> NOTIFICATIONS[Notificaciones]
```

### 🎛️ Dashboard en Tiempo Real

```mermaid
sequenceDiagram
    participant User as Usuario
    participant CLI as Monitor CLI
    participant Orch as Orchestrator
    participant DB as Database
    participant Metrics as Metrics Collector
    
    User->>CLI: monitor_cli.py status
    CLI->>DB: get_current_batch()
    DB-->>CLI: batch_info
    
    CLI->>DB: get_task_statistics()
    DB-->>CLI: task_stats
    
    CLI->>Metrics: get_real_time_metrics()
    Metrics-->>CLI: performance_data
    
    CLI->>CLI: render_dashboard()
    CLI-->>User: formatted_display
    
    loop Actualización automática
        CLI->>DB: refresh_data()
        CLI->>CLI: update_display()
    end
```

### 📊 Flujo de Alertas

```mermaid
flowchart TD
    MONITOR[Monitoreo Continuo] --> CHECK_THRESHOLDS{Verificar Umbrales}
    
    CHECK_THRESHOLDS -->|Normal| CONTINUE[Continuar Monitoreo]
    CHECK_THRESHOLDS -->|Alerta| CLASSIFY_ALERT[Clasificar Alerta]
    
    CLASSIFY_ALERT --> INFO_ALERT[Alerta Informativa]
    CLASSIFY_ALERT --> WARNING_ALERT[Alerta de Advertencia]
    CLASSIFY_ALERT --> CRITICAL_ALERT[Alerta Crítica]
    
    INFO_ALERT --> LOG_ALERT[Registrar en Log]
    WARNING_ALERT --> LOG_ALERT
    WARNING_ALERT --> SEND_EMAIL[Enviar Email]
    
    CRITICAL_ALERT --> LOG_ALERT
    CRITICAL_ALERT --> SEND_EMAIL
    CRITICAL_ALERT --> SEND_SLACK[Enviar Slack]
    CRITICAL_ALERT --> ESCALATE[Escalar Alerta]
    
    LOG_ALERT --> CONTINUE
    SEND_EMAIL --> CONTINUE
    SEND_SLACK --> CONTINUE
    ESCALATE --> EMERGENCY_RESPONSE[Respuesta de Emergencia]
```

---

## 📝 Conclusión del Flujo

El sistema de flujos del orquestador está diseñado para:

### ✅ **Garantías de Ejecución**
- **Completitud**: Todas las tareas son procesadas o marcadas como fallidas
- **Orden**: Las dependencias son respetadas automáticamente
- **Consistencia**: Los estados son siempre coherentes
- **Durabilidad**: Toda la información crítica es persistida

### 🔄 **Flexibilidad Operacional**
- **Configuración dinámica**: Parámetros ajustables sin reiniciar
- **Escalabilidad**: Fácil adición de nuevos scrapers
- **Recuperación**: Múltiples niveles de recuperación automática
- **Monitoreo**: Visibilidad completa de todos los procesos

### 📊 **Observabilidad Total**
- **Trazabilidad**: Cada operación es registrada y auditable
- **Métricas**: Datos cuantitativos de rendimiento y calidad
- **Alertas**: Notificación proactiva de problemas
- **Reportes**: Análisis histórico y tendencias

Este diseño de flujos asegura que el sistema opera de manera **predecible**, **confiable** y **mantenible**, facilitando tanto la operación diaria como la evolución futura del sistema.
