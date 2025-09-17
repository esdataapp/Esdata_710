# 🔌 API Reference - Sistema de Orquestación de Scraping

## 📋 Índice

- [Introducción](#-introducción)
- [Orchestrator API](#-orchestrator-api)
- [Monitor CLI API](#️-monitor-cli-api)
- [Scraper Adapter API](#-scraper-adapter-api)
- [Database API](#️-database-api)
- [Configuration API](#️-configuration-api)
- [Validation API](#-validation-api)
- [Utilities API](#️-utilities-api)
- [Error Codes](#-error-codes)

## 🎯 Introducción

Esta documentación describe las APIs internas del Sistema de Orquestación de Scraping. Estas APIs están diseñadas para:

- **Integración**: Facilitar la integración con sistemas externos
- **Extensibilidad**: Permitir la adición de nuevas funcionalidades
- **Mantenibilidad**: Proporcionar interfaces claras y consistentes
- **Testing**: Facilitar la creación de tests automatizados

### 📚 Convenciones de la API

- **Parámetros opcionales**: Marcados con `Optional[Type]`
- **Valores por defecto**: Especificados en la signatura
- **Excepciones**: Documentadas para cada método
- **Tipos de retorno**: Especificados usando type hints

## 🎛️ Orchestrator API

### 📋 Clase Principal: `WindowsScrapingOrchestrator`

```python
class WindowsScrapingOrchestrator:
    """
    Orquestador principal del sistema de scraping.
    
    Attributes:
        config (Dict): Configuración del sistema
        base_dir (Path): Directorio base del proyecto
        db_path (Path): Ruta de la base de datos
        running (bool): Estado de ejecución
        max_workers (int): Número máximo de workers
    """
    
    def __init__(self, config_path: Optional[str] = None) -> None:
        """
        Inicializa el orquestador.
        
        Args:
            config_path: Ruta al archivo de configuración
            
        Raises:
            ConfigurationError: Si la configuración es inválida
            DatabaseError: Si no se puede inicializar la DB
        """
```

#### 🚀 Métodos de Ejecución

```python
def run_execution_batch(self) -> bool:
    """
    Ejecuta un lote completo de scraping.
    
    Returns:
        bool: True si el lote se completó exitosamente
        
    Raises:
        ExecutionError: Si hay un error crítico en la ejecución
        DatabaseError: Si hay problemas con la base de datos
        ConfigurationError: Si la configuración es inválida
        
    Example:
        >>> orchestrator = WindowsScrapingOrchestrator()
        >>> success = orchestrator.run_execution_batch()
        >>> print(f"Ejecución exitosa: {success}")
    """

def execute_scraper_sync(self, task: ScrapingTask, batch_id: str, 
                        month_year: str, execution_number: int) -> bool:
    """
    Ejecuta un scraper individual de forma síncrona.
    
    Args:
        task: Tarea de scraping a ejecutar
        batch_id: ID del lote de ejecución
        month_year: Mes y año (ej: "Sep25")
        execution_number: Número de ejecución
        
    Returns:
        bool: True si el scraper se ejecutó exitosamente
        
    Raises:
        ScraperNotFoundError: Si el scraper no existe
        ExecutionTimeoutError: Si el scraper excede el timeout
        
    Example:
        >>> task = ScrapingTask(scraper_name="cyt", website="CyT", ...)
        >>> success = orchestrator.execute_scraper_sync(task, "Sep25_01", "Sep25", 1)
    """

def execute_tasks_sequential(self, tasks: List[ScrapingTask], batch_id: str, 
                           month_year: str, execution_number: int) -> None:
    """
    Ejecuta una lista de tareas secuencialmente.
    
    Args:
        tasks: Lista de tareas a ejecutar
        batch_id: ID del lote
        month_year: Mes y año
        execution_number: Número de ejecución
        
    Example:
        >>> tasks = [task1, task2, task3]
        >>> orchestrator.execute_tasks_sequential(tasks, "Sep25_01", "Sep25", 1)
    """
```

#### 📊 Métodos de Estado y Monitoreo

```python
def get_status_report(self) -> Dict[str, Any]:
    """
    Genera un reporte completo del estado del sistema.
    
    Returns:
        Dict con las siguientes claves:
        - status_counts: Conteo de tareas por estado
        - last_batch: Información del último lote
        - failed_tasks: Lista de tareas fallidas
        - system_running: Estado de ejecución
        - base_directory: Directorio base
        
    Example:
        >>> report = orchestrator.get_status_report()
        >>> print(f"Tareas completadas: {report['status_counts'].get('completed', 0)}")
    """

def get_batch_progress(self, batch_id: str) -> Dict[str, Any]:
    """
    Obtiene el progreso de un lote específico.
    
    Args:
        batch_id: ID del lote a consultar
        
    Returns:
        Dict con información de progreso:
        - total_tasks: Total de tareas
        - completed_tasks: Tareas completadas
        - failed_tasks: Tareas fallidas
        - progress_percentage: Porcentaje de progreso
        - estimated_completion: Tiempo estimado de finalización
        
    Raises:
        BatchNotFoundError: Si el lote no existe
        
    Example:
        >>> progress = orchestrator.get_batch_progress("Sep25_01")
        >>> print(f"Progreso: {progress['progress_percentage']:.1f}%")
    """
```

#### 🗂️ Métodos de Gestión de Datos

```python
def load_urls_from_csv(self, scraper_name: str) -> List[ScrapingTask]:
    """
    Carga URLs desde un archivo CSV y crea tareas de scraping.
    
    Args:
        scraper_name: Nombre del scraper (ej: "cyt", "inm24")
        
    Returns:
        Lista de objetos ScrapingTask
        
    Raises:
        FileNotFoundError: Si el archivo CSV no existe
        CSVFormatError: Si el formato del CSV es inválido
        
    Example:
        >>> tasks = orchestrator.load_urls_from_csv("cyt")
        >>> print(f"Cargadas {len(tasks)} tareas para CyT")
    """

def generate_batch_id(self) -> Tuple[str, str, int]:
    """
    Genera un ID único para un lote de ejecución.
    
    Returns:
        Tuple con:
        - batch_id: ID completo (ej: "Sep25_01")
        - month_year: Mes y año (ej: "Sep25")
        - execution_number: Número de ejecución (ej: 1)
        
    Example:
        >>> batch_id, month_year, exec_num = orchestrator.generate_batch_id()
        >>> print(f"Nuevo lote: {batch_id}")
    """

def create_sample_urls(self) -> None:
    """
    Crea archivos CSV de ejemplo para testing.
    
    Genera archivos de URLs de ejemplo en el directorio urls/
    para facilitar testing y configuración inicial.
    
    Example:
        >>> orchestrator.create_sample_urls()
        >>> # Se crean archivos cyt_urls.csv, inm24_urls.csv, etc.
    """
```

### 📝 Clase de Datos: `ScrapingTask`

```python
@dataclass
class ScrapingTask:
    """
    Representa una tarea individual de scraping.
    
    Attributes:
        scraper_name: Nombre del scraper (ej: "cyt")
        website: Código del sitio web (ej: "CyT")
        city: Código de ciudad (ej: "Gdl")
        operation: Tipo de operación (ej: "Ven")
        product: Tipo de producto (ej: "Dep")
        url: URL a scrapear
        order: Orden de ejecución
        status: Estado actual de la tarea
        attempts: Número de intentos realizados
        max_attempts: Máximo número de intentos
        created_at: Timestamp de creación
        started_at: Timestamp de inicio
        completed_at: Timestamp de finalización
        error_message: Mensaje de error si existe
    """
    
    scraper_name: str
    website: str
    city: str
    operation: str
    product: str
    url: str
    order: int
    status: ScrapingStatus = ScrapingStatus.PENDING
    attempts: int = 0
    max_attempts: int = 3
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
```

## 🖥️ Monitor CLI API

### 📋 Clase Principal: `ScrapingMonitorWindows`

```python
class ScrapingMonitorWindows:
    """
    Monitor del sistema para interfaz de línea de comandos.
    
    Proporciona métodos para monitoreo, control y visualización
    del estado del sistema desde la terminal.
    """
    
    def __init__(self) -> None:
        """Inicializa el monitor CLI."""
```

#### 📊 Métodos de Visualización

```python
def show_status(self, detailed: bool = False) -> None:
    """
    Muestra el estado actual del sistema.
    
    Args:
        detailed: Si True, muestra información detallada incluyendo tareas fallidas
        
    Output:
        Imprime tabla formateada con:
        - Estado del último lote
        - Estadísticas de tareas por estado
        - Información de timing
        - Tareas fallidas (si detailed=True)
        
    Example:
        >>> monitor = ScrapingMonitorWindows()
        >>> monitor.show_status(detailed=True)
    """

def show_history(self, limit: int = 10) -> None:
    """
    Muestra el historial de ejecuciones.
    
    Args:
        limit: Número máximo de lotes a mostrar
        
    Output:
        Tabla con historial de lotes incluyendo:
        - ID del lote
        - Fecha de ejecución
        - Duración
        - Tareas totales/completadas/fallidas
        - Estado final
        
    Example:
        >>> monitor.show_history(limit=20)
    """

def show_tasks(self, batch_id: Optional[str] = None) -> None:
    """
    Muestra las tareas de un lote específico.
    
    Args:
        batch_id: ID del lote. Si None, usa el último lote
        
    Output:
        Tabla detallada de tareas con:
        - Información del scraper
        - Estado actual
        - Número de intentos
        - Duración de ejecución
        
    Example:
        >>> monitor.show_tasks("Sep25_01")
        >>> monitor.show_tasks()  # Último lote
    """

def show_system(self) -> None:
    """
    Muestra información del sistema.
    
    Output:
        Información completa del sistema:
        - Rutas de directorios
        - Estado de archivos de configuración
        - Scrapers disponibles
        - Archivos de URLs
        - Uso de espacio en disco
        
    Example:
        >>> monitor.show_system()
    """

def show_stats(self, days: int = 30) -> None:
    """
    Muestra estadísticas de rendimiento.
    
    Args:
        days: Número de días hacia atrás para calcular estadísticas
        
    Output:
        Estadísticas detalladas:
        - Rendimiento por sitio web
        - Rendimiento por ciudad
        - Tasas de éxito
        - Promedio de intentos
        
    Example:
        >>> monitor.show_stats(days=60)
    """
```

#### 🎮 Métodos de Control

```python
def run_now(self) -> None:
    """
    Ejecuta un lote de scraping inmediatamente.
    
    Inicia una nueva ejecución del orquestador y muestra
    el progreso en tiempo real.
    
    Example:
        >>> monitor.run_now()
    """
```

## 🔧 Scraper Adapter API

### 📋 Clase Principal: `ImprovedScraperAdapter`

```python
class ImprovedScraperAdapter:
    """
    Adaptador mejorado para integrar scrapers existentes.
    
    Permite la ejecución de scrapers legacy dentro del
    nuevo sistema de orquestación.
    """
    
    def __init__(self, base_dir: Path) -> None:
        """
        Inicializa el adaptador.
        
        Args:
            base_dir: Directorio base del proyecto
        """
```

#### 🚀 Métodos de Adaptación

```python
def adapt_and_execute_scraper(self, task_info: Dict[str, Any]) -> bool:
    """
    Adapta y ejecuta un scraper específico.
    
    Args:
        task_info: Diccionario con información de la tarea:
            - scraper_name: Nombre del scraper
            - website: Código del sitio web
            - city: Código de ciudad
            - operation: Tipo de operación
            - product: Tipo de producto
            - url: URL a scrapear
            - output_file: Archivo de salida
            
    Returns:
        bool: True si el scraper se ejecutó exitosamente
        
    Raises:
        ScraperNotFoundError: Si el scraper no existe
        AdaptationError: Si no se puede adaptar el scraper
        
    Example:
        >>> adapter = ImprovedScraperAdapter(base_dir)
        >>> task_info = {
        ...     'scraper_name': 'cyt',
        ...     'website': 'CyT',
        ...     'city': 'Gdl',
        ...     'operation': 'Ven',
        ...     'product': 'Dep',
        ...     'url': 'https://example.com',
        ...     'output_file': 'output.csv'
        ... }
        >>> success = adapter.adapt_and_execute_scraper(task_info)
    """

def create_modified_scraper(self, scraper_name: str, task_info: Dict[str, Any], 
                          config: Dict[str, Any]) -> Optional[Path]:
    """
    Crea una versión modificada del scraper con configuración específica.
    
    Args:
        scraper_name: Nombre del scraper
        task_info: Información de la tarea
        config: Configuración del scraper
        
    Returns:
        Path al scraper modificado o None si hay error
        
    Example:
        >>> modified_path = adapter.create_modified_scraper("cyt", task_info, config)
        >>> if modified_path:
        ...     print(f"Scraper modificado creado en: {modified_path}")
    """
```

#### 🎯 Métodos Específicos por Scraper

```python
def modify_cyt_scraper(self, content: str, task_info: Dict[str, Any]) -> str:
    """
    Aplica modificaciones específicas para el scraper CyT.
    
    Args:
        content: Contenido original del scraper
        task_info: Información de la tarea
        
    Returns:
        str: Contenido modificado del scraper
        
    Modifica:
        - URL base según la ciudad y producto
        - Nombre del archivo de salida
        - Número de páginas a procesar
        - Configuración de rate limiting
    """

def modify_inm24_scraper(self, content: str, task_info: Dict[str, Any]) -> str:
    """
    Aplica modificaciones específicas para el scraper Inm24.
    
    Args:
        content: Contenido original del scraper
        task_info: Información de la tarea
        
    Returns:
        str: Contenido modificado del scraper
        
    Modifica:
        - Patrones de URL según ciudad y tipo
        - Configuración de seleniumbase
        - Manejo de CAPTCHAs
        - Archivos de salida
    """
```

## 🗄️ Database API

### 📋 Gestión de Base de Datos

```python
class DatabaseManager:
    """
    Gestor de base de datos SQLite para el sistema.
    
    Proporciona métodos de alto nivel para interactuar
    con la base de datos del sistema.
    """
    
    def __init__(self, db_path: str) -> None:
        """
        Inicializa el gestor de base de datos.
        
        Args:
            db_path: Ruta al archivo de base de datos SQLite
        """
```

#### 📊 Métodos de Consulta

```python
def get_batch_info(self, batch_id: str) -> Optional[Dict[str, Any]]:
    """
    Obtiene información de un lote específico.
    
    Args:
        batch_id: ID del lote a consultar
        
    Returns:
        Dict con información del lote o None si no existe
        
    Example:
        >>> db = DatabaseManager("orchestrator.db")
        >>> info = db.get_batch_info("Sep25_01")
        >>> if info:
        ...     print(f"Lote iniciado: {info['started_at']}")
    """

def get_task_statistics(self, batch_id: Optional[str] = None, 
                       days: Optional[int] = None) -> Dict[str, Any]:
    """
    Obtiene estadísticas de tareas.
    
    Args:
        batch_id: ID del lote específico (opcional)
        days: Días hacia atrás para estadísticas (opcional)
        
    Returns:
        Dict con estadísticas:
        - total_tasks: Total de tareas
        - completed_tasks: Tareas completadas
        - failed_tasks: Tareas fallidas
        - success_rate: Tasa de éxito
        - avg_duration: Duración promedio
        
    Example:
        >>> stats = db.get_task_statistics(days=30)
        >>> print(f"Tasa de éxito: {stats['success_rate']:.2f}%")
    """

def get_scraper_performance(self, scraper_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Obtiene métricas de rendimiento por scraper.
    
    Args:
        scraper_name: Scraper específico (opcional, por defecto todos)
        
    Returns:
        Lista de diccionarios con métricas por scraper:
        - scraper_name: Nombre del scraper
        - total_executions: Total de ejecuciones
        - success_rate: Tasa de éxito
        - avg_duration: Duración promedio
        - last_execution: Última ejecución
        
    Example:
        >>> performance = db.get_scraper_performance()
        >>> for scraper in performance:
        ...     print(f"{scraper['scraper_name']}: {scraper['success_rate']:.1f}%")
    """
```

#### 📝 Métodos de Escritura

```python
def create_batch(self, batch_id: str, month_year: str, 
                execution_number: int) -> bool:
    """
    Crea un nuevo lote de ejecución.
    
    Args:
        batch_id: ID único del lote
        month_year: Mes y año (ej: "Sep25")
        execution_number: Número de ejecución
        
    Returns:
        bool: True si se creó exitosamente
        
    Raises:
        DatabaseError: Si hay error en la base de datos
        
    Example:
        >>> success = db.create_batch("Sep25_01", "Sep25", 1)
    """

def update_task_status(self, task_id: int, status: str, 
                      error_message: Optional[str] = None) -> bool:
    """
    Actualiza el estado de una tarea.
    
    Args:
        task_id: ID de la tarea
        status: Nuevo estado
        error_message: Mensaje de error (opcional)
        
    Returns:
        bool: True si se actualizó exitosamente
        
    Example:
        >>> db.update_task_status(123, "completed")
        >>> db.update_task_status(124, "failed", "Connection timeout")
    """

def insert_tasks(self, tasks: List[ScrapingTask], batch_id: str) -> bool:
    """
    Inserta múltiples tareas en la base de datos.
    
    Args:
        tasks: Lista de tareas a insertar
        batch_id: ID del lote al que pertenecen
        
    Returns:
        bool: True si todas las tareas se insertaron exitosamente
        
    Example:
        >>> tasks = [task1, task2, task3]
        >>> success = db.insert_tasks(tasks, "Sep25_01")
    """
```

## ⚙️ Configuration API

### 📋 Gestión de Configuración

```python
class ConfigManager:
    """
    Gestor de configuración del sistema.
    
    Maneja la carga, validación y acceso a la configuración
    del sistema desde archivos YAML.
    """
    
    def __init__(self, config_path: str) -> None:
        """
        Inicializa el gestor de configuración.
        
        Args:
            config_path: Ruta al archivo de configuración YAML
        """
```

#### 📖 Métodos de Lectura

```python
def get_config(self, section: Optional[str] = None) -> Union[Dict[str, Any], Any]:
    """
    Obtiene la configuración o una sección específica.
    
    Args:
        section: Sección específica a obtener (opcional)
        
    Returns:
        Dict completo de configuración o valor de la sección
        
    Raises:
        ConfigurationError: Si la sección no existe
        
    Example:
        >>> config_manager = ConfigManager("config.yaml")
        >>> all_config = config_manager.get_config()
        >>> db_config = config_manager.get_config("database")
        >>> max_workers = config_manager.get_config("execution.max_parallel_scrapers")
    """

def get_scraper_config(self, scraper_name: str) -> Dict[str, Any]:
    """
    Obtiene la configuración específica de un scraper.
    
    Args:
        scraper_name: Nombre del scraper
        
    Returns:
        Dict con configuración del scraper
        
    Raises:
        ScraperNotFoundError: Si el scraper no está configurado
        
    Example:
        >>> cyt_config = config_manager.get_scraper_config("cyt")
        >>> rate_limit = cyt_config.get("rate_limit_seconds", 2)
    """

def get_website_config(self, website_code: str) -> Dict[str, Any]:
    """
    Obtiene la configuración de un sitio web específico.
    
    Args:
        website_code: Código del sitio web (ej: "CyT", "Inm24")
        
    Returns:
        Dict con configuración del sitio web
        
    Example:
        >>> website_config = config_manager.get_website_config("CyT")
        >>> priority = website_config.get("priority", 999)
    """
```

#### ✏️ Métodos de Escritura

```python
def update_config(self, section: str, key: str, value: Any) -> bool:
    """
    Actualiza un valor específico en la configuración.
    
    Args:
        section: Sección de la configuración
        key: Clave a actualizar
        value: Nuevo valor
        
    Returns:
        bool: True si se actualizó exitosamente
        
    Example:
        >>> config_manager.update_config("execution", "max_parallel_scrapers", 8)
        >>> config_manager.update_config("websites.CyT", "priority", 1)
    """

def validate_config(self) -> Tuple[bool, List[str]]:
    """
    Valida la configuración actual.
    
    Returns:
        Tuple con:
        - bool: True si la configuración es válida
        - List[str]: Lista de errores encontrados
        
    Example:
        >>> is_valid, errors = config_manager.validate_config()
        >>> if not is_valid:
        ...     for error in errors:
        ...         print(f"Error: {error}")
    """
```

## ✅ Validation API

### 📋 Validador del Sistema

```python
class SystemValidator:
    """
    Validador completo del sistema.
    
    Verifica que todos los componentes del sistema
    estén configurados correctamente.
    """
    
    def __init__(self, base_dir: Path) -> None:
        """
        Inicializa el validador.
        
        Args:
            base_dir: Directorio base del proyecto
        """
```

#### 🔍 Métodos de Validación

```python
def validate_all(self) -> bool:
    """
    Ejecuta todas las validaciones del sistema.
    
    Returns:
        bool: True si todas las validaciones pasan
        
    Validaciones incluidas:
        - Estructura de directorios
        - Archivo de configuración
        - Dependencias de Python
        - Archivos de scrapers
        - Archivos de URLs
        - Base de datos
        - Permisos de archivos
        - Funcionalidad básica
        
    Example:
        >>> validator = SystemValidator(base_dir)
        >>> if validator.validate_all():
        ...     print("Sistema validado correctamente")
    """

def validate_directory_structure(self) -> bool:
    """
    Valida la estructura de directorios del proyecto.
    
    Returns:
        bool: True si la estructura es correcta
        
    Verifica:
        - Existencia de directorios requeridos
        - Permisos de escritura
        - Estructura jerárquica correcta
    """

def validate_configuration(self) -> bool:
    """
    Valida el archivo de configuración.
    
    Returns:
        bool: True si la configuración es válida
        
    Verifica:
        - Sintaxis YAML correcta
        - Secciones requeridas presentes
        - Tipos de datos correctos
        - Valores en rangos válidos
    """

def validate_python_dependencies(self) -> bool:
    """
    Valida que todas las dependencias de Python estén instaladas.
    
    Returns:
        bool: True si todas las dependencias están disponibles
        
    Verifica:
        - Paquetes requeridos instalados
        - Versiones compatibles
        - Módulos importables
    """

def validate_scrapers(self) -> bool:
    """
    Valida los archivos de scrapers.
    
    Returns:
        bool: True si todos los scrapers son válidos
        
    Verifica:
        - Existencia de archivos .py
        - Sintaxis Python correcta
        - Funciones requeridas presentes
        - Importaciones válidas
    """

def validate_url_files(self) -> bool:
    """
    Valida los archivos CSV de URLs.
    
    Returns:
        bool: True si todos los archivos son válidos
        
    Verifica:
        - Formato CSV correcto
        - Columnas requeridas presentes
        - URLs válidas
        - Datos consistentes
    """
```

#### 📊 Métodos de Reporte

```python
def generate_report(self) -> str:
    """
    Genera un reporte completo de validación.
    
    Returns:
        str: Reporte formateado con resultados de validación
        
    Incluye:
        - Resumen de validaciones
        - Detalles de errores encontrados
        - Recomendaciones de corrección
        - Información del sistema
        
    Example:
        >>> report = validator.generate_report()
        >>> with open("validation_report.txt", "w") as f:
        ...     f.write(report)
    """
```

## 🛠️ Utilities API

### 📋 Utilidades del Sistema

```python
class SystemUtils:
    """
    Utilidades generales del sistema.
    
    Proporciona funciones auxiliares para operaciones
    comunes del sistema.
    """
    
    @staticmethod
    def get_system_info() -> Dict[str, Any]:
        """
        Obtiene información del sistema.
        
        Returns:
            Dict con información del sistema:
            - os_name: Nombre del sistema operativo
            - python_version: Versión de Python
            - cpu_count: Número de CPUs
            - memory_total: Memoria total en GB
            - disk_free: Espacio libre en disco en GB
            
        Example:
            >>> info = SystemUtils.get_system_info()
            >>> print(f"Python {info['python_version']} en {info['os_name']}")
        """
    
    @staticmethod
    def calculate_optimal_workers() -> int:
        """
        Calcula el número óptimo de workers para el sistema.
        
        Returns:
            int: Número recomendado de workers
            
        Considera:
            - Número de CPUs disponibles
            - Cantidad de memoria RAM
            - Carga actual del sistema
            
        Example:
            >>> optimal = SystemUtils.calculate_optimal_workers()
            >>> print(f"Workers recomendados: {optimal}")
        """
    
    @staticmethod
    def cleanup_temp_files(temp_dir: Path, max_age_hours: int = 24) -> int:
        """
        Limpia archivos temporales antiguos.
        
        Args:
            temp_dir: Directorio de archivos temporales
            max_age_hours: Antigüedad máxima en horas
            
        Returns:
            int: Número de archivos eliminados
            
        Example:
            >>> cleaned = SystemUtils.cleanup_temp_files(Path("temp"), 12)
            >>> print(f"Archivos limpiados: {cleaned}")
        """
    
    @staticmethod
    def compress_old_data(data_dir: Path, days_old: int = 30) -> List[str]:
        """
        Comprime datos antiguos para ahorrar espacio.
        
        Args:
            data_dir: Directorio de datos
            days_old: Antigüedad en días para comprimir
            
        Returns:
            List[str]: Lista de archivos comprimidos
            
        Example:
            >>> compressed = SystemUtils.compress_old_data(Path("data"), 60)
            >>> print(f"Archivos comprimidos: {len(compressed)}")
        """
```

### 📊 Utilidades de Métricas

```python
class MetricsUtils:
    """
    Utilidades para cálculo y análisis de métricas.
    """
    
    @staticmethod
    def calculate_success_rate(completed: int, failed: int) -> float:
        """
        Calcula la tasa de éxito.
        
        Args:
            completed: Número de tareas completadas
            failed: Número de tareas fallidas
            
        Returns:
            float: Tasa de éxito como porcentaje (0-100)
            
        Example:
            >>> rate = MetricsUtils.calculate_success_rate(95, 5)
            >>> print(f"Tasa de éxito: {rate}%")
        """
    
    @staticmethod
    def calculate_throughput(tasks_completed: int, duration_minutes: float) -> float:
        """
        Calcula el throughput del sistema.
        
        Args:
            tasks_completed: Número de tareas completadas
            duration_minutes: Duración en minutos
            
        Returns:
            float: Tareas por minuto
            
        Example:
            >>> throughput = MetricsUtils.calculate_throughput(120, 60)
            >>> print(f"Throughput: {throughput} tareas/min")
        """
    
    @staticmethod
    def estimate_completion_time(pending_tasks: int, current_rate: float) -> datetime:
        """
        Estima el tiempo de finalización.
        
        Args:
            pending_tasks: Número de tareas pendientes
            current_rate: Tasa actual de procesamiento (tareas/min)
            
        Returns:
            datetime: Tiempo estimado de finalización
            
        Example:
            >>> eta = MetricsUtils.estimate_completion_time(50, 2.5)
            >>> print(f"ETA: {eta.strftime('%H:%M:%S')}")
        """
```

## ❌ Error Codes

### 📋 Códigos de Error del Sistema

| Código | Categoría | Descripción | Acción Recomendada |
|--------|-----------|-------------|-------------------|
| **0** | Success | Operación exitosa | Continuar |
| **1** | General | Error general no específico | Revisar logs |
| **2** | Configuration | Error de configuración | Verificar config.yaml |
| **3** | Dependencies | Dependencias faltantes | Ejecutar `pip install -r requirements.txt` |
| **4** | Database | Error de base de datos | Verificar permisos y espacio |
| **5** | Network | Error de conectividad | Verificar conexión a internet |
| **6** | FileSystem | Error de sistema de archivos | Verificar permisos y espacio |
| **7** | Scraper | Error específico de scraper | Revisar scraper específico |
| **8** | Timeout | Timeout de operación | Aumentar timeout o verificar recursos |
| **9** | Validation | Error de validación | Corregir datos de entrada |
| **10** | Authentication | Error de autenticación | Verificar credenciales |

### 🚨 Excepciones Personalizadas

```python
class ScrapingOrchestrationError(Exception):
    """Excepción base para errores del sistema de orquestación."""
    pass

class ConfigurationError(ScrapingOrchestrationError):
    """Error en la configuración del sistema."""
    pass

class DatabaseError(ScrapingOrchestrationError):
    """Error en operaciones de base de datos."""
    pass

class ScraperNotFoundError(ScrapingOrchestrationError):
    """Error cuando no se encuentra un scraper específico."""
    pass

class ExecutionTimeoutError(ScrapingOrchestrationError):
    """Error cuando una operación excede el tiempo límite."""
    pass

class AdaptationError(ScrapingOrchestrationError):
    """Error en la adaptación de scrapers legacy."""
    pass

class ValidationError(ScrapingOrchestrationError):
    """Error en la validación de datos o configuración."""
    pass
```

### 📞 Manejo de Errores

```python
# Ejemplo de manejo de errores
try:
    orchestrator = WindowsScrapingOrchestrator()
    success = orchestrator.run_execution_batch()
except ConfigurationError as e:
    logger.error(f"Error de configuración: {e}")
    exit(2)
except DatabaseError as e:
    logger.error(f"Error de base de datos: {e}")
    exit(4)
except Exception as e:
    logger.error(f"Error inesperado: {e}")
    exit(1)
```

---

## 📝 Notas de Uso

### 🔧 Mejores Prácticas

1. **Manejo de Excepciones**: Siempre manejar excepciones específicas
2. **Logging**: Usar logging apropiado para debugging
3. **Configuración**: Validar configuración antes de usar
4. **Recursos**: Limpiar recursos después del uso
5. **Threading**: Usar locks apropiados para operaciones concurrentes

### 📚 Ejemplos de Integración

```python
# Ejemplo completo de uso de la API
from orchestrator import WindowsScrapingOrchestrator
from monitor_cli import ScrapingMonitorWindows
from improved_scraper_adapter import ImprovedScraperAdapter

# Inicializar componentes
orchestrator = WindowsScrapingOrchestrator()
monitor = ScrapingMonitorWindows()

# Ejecutar scraping
try:
    success = orchestrator.run_execution_batch()
    if success:
        print("Scraping completado exitosamente")
        monitor.show_status(detailed=True)
    else:
        print("Scraping falló")
        monitor.show_system()
except Exception as e:
    print(f"Error: {e}")
```

Esta API proporciona una interfaz completa y consistente para interactuar con todos los componentes del sistema de orquestación, facilitando tanto el uso directo como la integración con sistemas externos.
