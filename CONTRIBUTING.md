# 🤝 Contributing to Sistema de Orquestación de Scraping

¡Gracias por tu interés en contribuir a nuestro proyecto! Esta guía te ayudará a entender cómo puedes participar en el desarrollo y mejora del sistema.

## 📋 Tabla de Contenidos

- [Código de Conducta](#-código-de-conducta)
- [Cómo Contribuir](#-cómo-contribuir)
- [Configuración del Entorno de Desarrollo](#️-configuración-del-entorno-de-desarrollo)
- [Estándares de Código](#-estándares-de-código)
- [Proceso de Pull Request](#-proceso-de-pull-request)
- [Tipos de Contribuciones](#-tipos-de-contribuciones)
- [Reportar Bugs](#-reportar-bugs)
- [Solicitar Funcionalidades](#-solicitar-funcionalidades)

## 📜 Código de Conducta

### Nuestro Compromiso

Nos comprometemos a hacer de la participación en nuestro proyecto una experiencia libre de acoso para todos, independientemente de:

- Edad
- Discapacidad
- Etnia
- Identidad y expresión de género
- Nivel de experiencia
- Nacionalidad
- Apariencia personal
- Raza
- Religión
- Orientación sexual

### Comportamiento Esperado

**Ejemplos de comportamiento que contribuye a crear un ambiente positivo:**

✅ Usar lenguaje acogedor e inclusivo
✅ Respetar diferentes puntos de vista y experiencias
✅ Aceptar críticas constructivas de manera elegante
✅ Enfocarse en lo que es mejor para la comunidad
✅ Mostrar empatía hacia otros miembros de la comunidad

### Comportamiento Inaceptable

❌ Uso de lenguaje o imágenes sexualizadas
❌ Comentarios despectivos, insultos o ataques personales
❌ Acoso público o privado
❌ Publicar información privada de otros sin permiso
❌ Cualquier conducta que sea inapropiada en un entorno profesional

## 🚀 Cómo Contribuir

### 🔍 Primeros Pasos

1. **Familiarízate con el proyecto**
   - Lee la documentación completa
   - Ejecuta el sistema localmente
   - Explora el código fuente

2. **Revisa las issues existentes**
   - Busca issues etiquetadas como `good first issue`
   - Lee issues abiertas para entender problemas conocidos
   - Verifica si alguien ya está trabajando en lo que te interesa

3. **Únete a la conversación**
   - Comenta en issues relevantes
   - Haz preguntas si algo no está claro
   - Propón ideas y soluciones

### 🛠️ Tipos de Contribuciones Bienvenidas

| Tipo | Descripción | Etiqueta |
|------|-------------|----------|
| **Bug Fixes** | Corrección de errores | `bug` |
| **Features** | Nuevas funcionalidades | `enhancement` |
| **Documentation** | Mejoras en documentación | `documentation` |
| **Performance** | Optimizaciones | `performance` |
| **Testing** | Mejoras en tests | `testing` |
| **Refactoring** | Mejoras de código | `refactoring` |

## 🛠️ Configuración del Entorno de Desarrollo

### 📋 Prerrequisitos

- Python 3.8+
- Git
- Conocimientos básicos de web scraping
- Familiaridad con SQLite

### 🔧 Setup del Entorno

```bash
# 1. Fork del repositorio
# Haz fork en GitHub: https://github.com/proyecto/scraping-orchestrator

# 2. Clonar tu fork
git clone https://github.com/tu-usuario/scraping-orchestrator.git
cd scraping-orchestrator

# 3. Agregar remote upstream
git remote add upstream https://github.com/proyecto/scraping-orchestrator.git

# 4. Crear entorno virtual
python -m venv venv

# 5. Activar entorno virtual
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 6. Instalar dependencias de desarrollo
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 7. Instalar pre-commit hooks
pre-commit install

# 8. Verificar instalación
python validate_system.py
python -m pytest tests/ -v
```

### 📦 Dependencias de Desarrollo

```txt
# requirements-dev.txt
pytest>=7.4.0
pytest-cov>=4.1.0
pytest-mock>=3.11.0
black>=23.7.0
flake8>=6.0.0
isort>=5.12.0
mypy>=1.5.0
pre-commit>=3.3.3
sphinx>=7.1.0
```

### 🧪 Ejecutar Tests

```bash
# Ejecutar todos los tests
python -m pytest

# Tests con cobertura
python -m pytest --cov=src

# Tests específicos
python -m pytest tests/test_orchestrator.py

# Tests con verbose output
python -m pytest -v
```

## 📏 Estándares de Código

### 🐍 Estilo de Python

Seguimos **PEP 8** con algunas adaptaciones:

#### **Formateo Automático**
```bash
# Black para formateo
black .

# isort para imports
isort .

# Verificar estilo
flake8 .
```

#### **Configuración en .flake8**
```ini
[flake8]
max-line-length = 88
extend-ignore = E203, E501, W503
exclude = 
    .git,
    __pycache__,
    venv,
    .venv,
    build,
    dist
```

#### **Configuración en pyproject.toml**
```toml
[tool.black]
line-length = 88
target-version = ['py38']
include = '\.pyi?$'

[tool.isort]
profile = "black"
multi_line_output = 3

[tool.mypy]
python_version = "3.8"
warn_return_any = true
warn_unused_configs = true
```

### 📝 Convenciones de Código

#### **Nombres de Variables y Funciones**
```python
# ✅ Correcto
def calculate_success_rate(completed_tasks: int, total_tasks: int) -> float:
    """Calcula la tasa de éxito."""
    return (completed_tasks / total_tasks) * 100

scraper_name = "cyt"
max_retry_attempts = 3

# ❌ Incorrecto
def calcSuccessRate(ct, tt):
    return ct/tt*100

scraperName = "cyt"
maxRetryAttempts = 3
```

#### **Nombres de Clases**
```python
# ✅ Correcto
class ScrapingOrchestrator:
    pass

class DatabaseManager:
    pass

# ❌ Incorrecto
class scraping_orchestrator:
    pass

class databaseManager:
    pass
```

#### **Constantes**
```python
# ✅ Correcto
MAX_PARALLEL_SCRAPERS = 8
DEFAULT_TIMEOUT_SECONDS = 30
SUPPORTED_WEBSITES = ["CyT", "Inm24", "Lam"]

# ❌ Incorrecto
max_parallel_scrapers = 8
defaultTimeout = 30
```

### 📖 Documentación de Código

#### **Docstrings**
```python
def execute_scraper(self, task: ScrapingTask) -> bool:
    """
    Ejecuta un scraper individual.
    
    Args:
        task: Tarea de scraping a ejecutar
        
    Returns:
        bool: True si el scraper se ejecutó exitosamente
        
    Raises:
        ScraperNotFoundError: Si el scraper no existe
        ExecutionTimeoutError: Si el scraper excede el timeout
        
    Example:
        >>> task = ScrapingTask(scraper_name="cyt", ...)
        >>> success = orchestrator.execute_scraper(task)
        >>> if success:
        ...     print("Scraper ejecutado exitosamente")
    """
```

#### **Type Hints**
```python
from typing import Dict, List, Optional, Union
from pathlib import Path

def load_config(config_path: Path) -> Dict[str, Any]:
    """Carga configuración desde archivo."""
    pass

def process_tasks(tasks: List[ScrapingTask]) -> Optional[Dict[str, int]]:
    """Procesa lista de tareas."""
    pass
```

### 🧪 Testing

#### **Estructura de Tests**
```
tests/
├── unit/
│   ├── test_orchestrator.py
│   ├── test_adapter.py
│   └── test_monitor.py
├── integration/
│   ├── test_database.py
│   └── test_scraper_integration.py
├── e2e/
│   └── test_complete_workflow.py
└── fixtures/
    ├── test_config.yaml
    └── sample_data.csv
```

#### **Ejemplo de Test Unitario**
```python
import pytest
from unittest.mock import Mock, patch
from orchestrator import WindowsScrapingOrchestrator, ScrapingTask

class TestOrchestrator:
    
    @pytest.fixture
    def orchestrator(self):
        """Fixture para crear instancia de orquestrador."""
        return WindowsScrapingOrchestrator()
    
    def test_generate_batch_id(self, orchestrator):
        """Test generación de ID de lote."""
        batch_id, month_year, exec_num = orchestrator.generate_batch_id()
        
        assert isinstance(batch_id, str)
        assert len(batch_id) > 0
        assert "_" in batch_id
        assert isinstance(exec_num, int)
        assert exec_num >= 1
    
    @patch('orchestrator.pd.read_csv')
    def test_load_urls_from_csv(self, mock_read_csv, orchestrator):
        """Test carga de URLs desde CSV."""
        # Configurar mock
        mock_df = Mock()
        mock_df.iterrows.return_value = [
            (0, {'PaginaWeb': 'CyT', 'Ciudad': 'Gdl', 'Operacion': 'Ven', 
                 'ProductoPaginaWeb': 'Dep', 'URL': 'https://example.com'})
        ]
        mock_read_csv.return_value = mock_df
        
        # Ejecutar test
        tasks = orchestrator.load_urls_from_csv("cyt")
        
        # Verificar resultados
        assert len(tasks) == 1
        assert tasks[0].scraper_name == "cyt"
        assert tasks[0].website == "CyT"
```

#### **Ejemplo de Test de Integración**
```python
import tempfile
import sqlite3
from pathlib import Path
from orchestrator import WindowsScrapingOrchestrator

class TestDatabaseIntegration:
    
    def test_database_operations(self):
        """Test operaciones completas de base de datos."""
        
        # Crear base de datos temporal
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            db_path = tmp.name
        
        try:
            # Configurar orquestrador con DB temporal
            orchestrator = WindowsScrapingOrchestrator()
            orchestrator.db_path = Path(db_path)
            orchestrator._init_database()
            
            # Test generación de lote
            batch_id, month_year, exec_num = orchestrator.generate_batch_id()
            
            # Verificar en base de datos
            with sqlite3.connect(db_path) as conn:
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM execution_batches WHERE batch_id = ?",
                    (batch_id,)
                )
                count = cursor.fetchone()[0]
                assert count >= 0  # El lote puede o no estar creado aún
                
        finally:
            # Limpiar
            Path(db_path).unlink(missing_ok=True)
```

## 🔄 Proceso de Pull Request

### 📋 Antes de Crear el PR

1. **Sincronizar con upstream**
   ```bash
   git fetch upstream
   git checkout main
   git merge upstream/main
   ```

2. **Crear rama para tu feature**
   ```bash
   git checkout -b feature/nueva-funcionalidad
   # o
   git checkout -b bugfix/corregir-error
   ```

3. **Hacer cambios y commits**
   ```bash
   # Hacer cambios
   git add .
   git commit -m "feat: agregar nueva funcionalidad de X"
   ```

### 📝 Mensaje de Commit

Usamos **Conventional Commits**:

```
<tipo>[alcance opcional]: <descripción>

[cuerpo opcional]

[footer opcional]
```

#### **Tipos de Commit**
- `feat`: Nueva funcionalidad
- `fix`: Corrección de bug
- `docs`: Cambios en documentación
- `style`: Cambios de formato (no afectan funcionalidad)
- `refactor`: Refactoring de código
- `test`: Agregar o modificar tests
- `chore`: Mantenimiento (dependencias, config, etc.)

#### **Ejemplos**
```bash
# Nueva funcionalidad
git commit -m "feat: agregar soporte para sitio web Trovit"

# Corrección de bug
git commit -m "fix: resolver timeout en scraper de Inmuebles24"

# Documentación
git commit -m "docs: actualizar guía de instalación"

# Breaking change
git commit -m "feat!: cambiar formato de configuración YAML"
```

### 🔍 Checklist del Pull Request

Antes de enviar tu PR, verifica:

- [ ] **Código funciona**: Tests pasan localmente
- [ ] **Estilo consistente**: Black, isort, flake8 sin errores
- [ ] **Tests incluidos**: Nuevas funcionalidades tienen tests
- [ ] **Documentación actualizada**: README o docs actualizados si es necesario
- [ ] **Commits limpios**: Mensajes descriptivos y commits atómicos
- [ ] **Sin conflictos**: Rama sincronizada con main
- [ ] **Descripción clara**: PR tiene descripción detallada

### 📄 Template de Pull Request

```markdown
## Descripción
Breve descripción de los cambios realizados.

## Tipo de Cambio
- [ ] Bug fix (cambio que corrige un issue)
- [ ] Nueva funcionalidad (cambio que agrega funcionalidad)
- [ ] Breaking change (cambio que rompe compatibilidad)
- [ ] Documentación

## ¿Cómo se ha probado?
Describe las pruebas que ejecutaste para verificar tus cambios.

- [ ] Tests unitarios
- [ ] Tests de integración
- [ ] Pruebas manuales

## Checklist
- [ ] Mi código sigue las convenciones del proyecto
- [ ] He realizado auto-review de mi código
- [ ] He comentado mi código en áreas difíciles de entender
- [ ] He actualizado la documentación correspondiente
- [ ] Mis cambios no generan warnings nuevos
- [ ] He agregado tests que prueban mi funcionalidad
- [ ] Tests nuevos y existentes pasan localmente

## Screenshots (si aplica)
Agrega screenshots para cambios en UI.

## Issues Relacionadas
Fixes #(número de issue)
```

## 🐛 Reportar Bugs

### 📋 Antes de Reportar

1. **Verifica que sea realmente un bug**
2. **Busca en issues existentes**
3. **Prueba con la última versión**
4. **Recolecta información de diagnóstico**

### 📝 Template para Bug Report

```markdown
**Descripción del Bug**
Descripción clara y concisa del bug.

**Pasos para Reproducir**
1. Ir a '...'
2. Hacer clic en '....'
3. Hacer scroll hacia '....'
4. Ver error

**Comportamiento Esperado**
Descripción clara de lo que esperabas que pasara.

**Screenshots**
Si aplica, agrega screenshots del problema.

**Información del Sistema:**
 - OS: [e.g. Windows 10]
 - Python: [e.g. 3.9.7]
 - Versión del proyecto: [e.g. 1.2.3]

**Logs**
```
Pega logs relevantes aquí
```

**Contexto Adicional**
Cualquier otra información relevante sobre el problema.
```

### 🔍 Información de Diagnóstico

```bash
# Generar información de diagnóstico
python validate_system.py > diagnostico.txt
python monitor_cli.py system >> diagnostico.txt
python --version >> diagnostico.txt
pip list >> diagnostico.txt
```

## 💡 Solicitar Funcionalidades

### 📝 Template para Feature Request

```markdown
**¿Tu solicitud está relacionada con un problema?**
Descripción clara del problema: "Estoy frustrado cuando [...]"

**Describe la solución que te gustaría**
Descripción clara de lo que quieres que pase.

**Describe alternativas que has considerado**
Descripción de soluciones alternativas que has considerado.

**Contexto adicional**
Cualquier otra información o screenshots sobre la solicitud.

**Prioridad**
- [ ] Baja
- [ ] Media  
- [ ] Alta
- [ ] Crítica
```

## 🏆 Reconocimiento de Contribuidores

### 🌟 Tipos de Contribuciones Reconocidas

Reconocemos todas las formas de contribución:

- 💻 **Código**: Implementación de funcionalidades y bug fixes
- 📖 **Documentación**: Mejoras en docs, tutoriales, ejemplos
- 🐛 **Bug Reports**: Identificación y reporte de problemas
- 💡 **Ideas**: Sugerencias de mejoras y nuevas funcionalidades
- 🤔 **Feedback**: Revisiones de código y sugerencias
- 📢 **Promoción**: Compartir el proyecto, escribir blogs
- 🌍 **Traducción**: Traducciones de documentación
- 🎨 **Diseño**: Mejoras en UI/UX y visualización

### 📊 Sistema de Reconocimiento

Los contribuidores son reconocidos en:

1. **Archivo CONTRIBUTORS.md**
2. **Release notes**
3. **README principal**
4. **Documentación del proyecto**

## 🤝 Comunidad y Soporte

### 💬 Canales de Comunicación

- **GitHub Issues**: Para bugs y feature requests
- **GitHub Discussions**: Para preguntas y conversaciones generales
- **Email**: soporte@scraping-system.com
- **Slack**: #dev-scraping (para contribuidores activos)

### ❓ Obtener Ayuda

Si necesitas ayuda:

1. **Revisa la documentación**
2. **Busca en issues existentes**
3. **Pregunta en GitHub Discussions**
4. **Contacta a maintainers**

### 🎯 Roadmap del Proyecto

Consulta nuestro [roadmap público](ROADMAP.md) para ver:
- Funcionalidades planificadas
- Prioridades del proyecto
- Oportunidades de contribución

---

## 📞 Contacto de Maintainers

- **Lead Developer**: [@tu-usuario](https://github.com/tu-usuario)
- **DevOps Lead**: [@devops-user](https://github.com/devops-user)
- **Documentation Lead**: [@docs-user](https://github.com/docs-user)

---

¡Gracias por contribuir al Sistema de Orquestación de Scraping! 🎉

Tu participación hace que este proyecto sea mejor para toda la comunidad.
