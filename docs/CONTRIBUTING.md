# 🤝 Contributing Guide - Sistema de Orquestación de Scraping

## 📋 Índice

- [Bienvenida](#-bienvenida)
- [Código de Conducta](#-código-de-conducta)
- [Cómo Contribuir](#-cómo-contribuir)
- [Configuración de Desarrollo](#️-configuración-de-desarrollo)
- [Estándares de Código](#-estándares-de-código)
- [Proceso de Pull Request](#-proceso-de-pull-request)
- [Testing](#-testing)
- [Documentación](#-documentación)
- [Reporte de Issues](#-reporte-de-issues)

## 👋 Bienvenida

¡Gracias por tu interés en contribuir al Sistema de Orquestación de Scraping! Este proyecto se beneficia enormemente de las contribuciones de la comunidad, desde reportes de bugs hasta nuevas funcionalidades.

### 🎯 Tipos de Contribuciones Bienvenidas

- 🐛 **Reportes de bugs y fixes**
- ✨ **Nuevas funcionalidades**
- 📚 **Mejoras en documentación**
- 🧪 **Tests adicionales**
- 🎨 **Mejoras en la interfaz CLI**
- ⚡ **Optimizaciones de performance**
- 🔒 **Mejoras de seguridad**
- 🌐 **Soporte para nuevos sitios web**

## 📜 Código de Conducta

### 🤝 Nuestros Compromisos

- **Respeto**: Tratar a todos con respeto y dignidad
- **Inclusión**: Crear un ambiente acogedor para personas de todos los backgrounds
- **Colaboración**: Trabajar juntos hacia objetivos comunes
- **Constructividad**: Proporcionar feedback constructivo y útil

### 🚫 Comportamientos No Aceptables

- Lenguaje ofensivo, discriminatorio o acosador
- Ataques personales o trolling
- Publicación de información privada sin permiso
- Cualquier comportamiento que pueda considerarse inapropiado en un entorno profesional

### 📞 Reporte de Problemas

Si experimentas o presencias comportamiento inaceptable, por favor reporta a [conduct@scraping-system.com](mailto:conduct@scraping-system.com).

## 🚀 Cómo Contribuir

### 🔍 Encontrando Formas de Contribuir

1. **Issues Existentes**: Revisa los [issues abiertos](https://github.com/proyecto/issues)
2. **Good First Issues**: Busca issues etiquetados como `good-first-issue`
3. **Help Wanted**: Issues etiquetados como `help-wanted`
4. **Roadmap**: Revisa nuestro [roadmap del proyecto](ROADMAP.md)

### 📝 Proceso General

1. **Fork** el repositorio
2. **Crear** una rama para tu feature: `git checkout -b feature/nueva-funcionalidad`
3. **Desarrollar** tu contribución
4. **Escribir** tests para tu código
5. **Ejecutar** la suite de tests completa
6. **Documentar** los cambios
7. **Commit** con mensajes descriptivos
8. **Push** a tu fork: `git push origin feature/nueva-funcionalidad`
9. **Crear** un Pull Request

## 🛠️ Configuración de Desarrollo

### 📋 Requisitos Previos

- Python 3.8+
- Git
- Editor de código (VS Code recomendado)
- Windows 10/11 o WSL2

### ⚙️ Setup del Entorno de Desarrollo

```bash
# 1. Fork y clonar el repositorio
git clone https://github.com/tu-usuario/scraping-orchestrator.git
cd scraping-orchestrator

# 2. Crear entorno virtual
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# 3. Instalar dependencias de desarrollo
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 4. Instalar pre-commit hooks
pre-commit install

# 5. Configurar variables de entorno
copy .env.example .env
# Editar .env con tu configuración local

# 6. Ejecutar tests para verificar setup
python -m pytest tests/ -v

# 7. Ejecutar validación del sistema
python validate_system.py
```

### 📁 Estructura del Proyecto para Desarrollo

```
scraping-orchestrator/
├── src/                          # Código fuente principal
│   ├── orchestrator.py          # Orquestador principal
│   ├── monitor_cli.py           # CLI de monitoreo
│   ├── adapters/                # Adaptadores de scrapers
│   └── utils/                   # Utilidades
├── tests/                       # Tests
│   ├── unit/                    # Tests unitarios
│   ├── integration/             # Tests de integración
│   └── e2e/                     # Tests end-to-end
├── docs/                        # Documentación
├── config/                      # Configuración
├── tools/                       # Scripts de desarrollo
└── examples/                    # Ejemplos de uso
```

### 🔧 Herramientas de Desarrollo

#### **requirements-dev.txt**
```txt
# Testing
pytest>=7.4.0
pytest-cov>=4.1.0
pytest-mock>=3.11.0
pytest-asyncio>=0.21.0

# Code Quality
black>=23.7.0
flake8>=6.0.0
isort>=5.12.0
mypy>=1.5.0

# Pre-commit
pre-commit>=3.3.0

# Documentation
sphinx>=7.1.0
sphinx-rtd-theme>=1.3.0

# Development utilities
ipython>=8.14.0
jupyter>=1.0.0
```

#### **.pre-commit-config.yaml**
```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
      - id: check-merge-conflict

  - repo: https://github.com/psf/black
    rev: 23.7.0
    hooks:
      - id: black
        language_version: python3

  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort
        args: ["--profile", "black"]

  - repo: https://github.com/pycqa/flake8
    rev: 6.0.0
    hooks:
      - id: flake8
        args: [--max-line-length=88, --extend-ignore=E203]

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.5.0
    hooks:
      - id: mypy
        additional_dependencies: [types-all]
```

## 📏 Estándares de Código

### 🐍 Estilo Python

Seguimos **PEP 8** con algunas adaptaciones:

```python
# Ejemplo de código bien formateado

from typing import Dict, List, Optional, Union
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class ScrapingOrchestrator:
    """
    Orquestador principal del sistema de scraping.
    
    Este clase coordina la ejecución de múltiples scrapers
    y gestiona el estado del sistema.
    
    Attributes:
        config: Configuración del sistema
        db_path: Ruta a la base de datos
        running: Estado de ejecución actual
    """
    
    def __init__(self, config_path: Optional[str] = None) -> None:
        """
        Inicializa el orquestador.
        
        Args:
            config_path: Ruta opcional al archivo de configuración
            
        Raises:
            ConfigurationError: Si la configuración es inválida
        """
        self.config = self._load_config(config_path)
        self.db_path = Path(self.config["database"]["path"])
        self.running = False
        
        logger.info("Orchestrator initialized successfully")
    
    def execute_batch(self, batch_id: str) -> bool:
        """
        Ejecuta un lote de scraping.
        
        Args:
            batch_id: Identificador único del lote
            
        Returns:
            True si el lote se ejecutó exitosamente
            
        Raises:
            ExecutionError: Si hay un error durante la ejecución
        """
        try:
            logger.info(f"Starting batch execution: {batch_id}")
            # Implementación...
            return True
        except Exception as e:
            logger.error(f"Batch execution failed: {e}")
            raise ExecutionError(f"Failed to execute batch {batch_id}") from e
```

### 📝 Convenciones de Naming

| Tipo | Convención | Ejemplo |
|------|------------|---------|
| **Variables** | snake_case | `batch_id`, `config_path` |
| **Funciones** | snake_case | `execute_batch()`, `load_config()` |
| **Clases** | PascalCase | `ScrapingOrchestrator`, `TaskManager` |
| **Constantes** | UPPER_SNAKE_CASE | `MAX_RETRIES`, `DEFAULT_TIMEOUT` |
| **Archivos** | snake_case | `orchestrator.py`, `task_manager.py` |
| **Módulos** | snake_case | `utils`, `adapters` |

### 📚 Documentación de Código

```python
def complex_function(param1: str, param2: Optional[int] = None) -> Dict[str, Any]:
    """
    Breve descripción de la función en una línea.
    
    Descripción más detallada de qué hace la función,
    incluyendo cualquier comportamiento especial o consideraciones.
    
    Args:
        param1: Descripción del primer parámetro
        param2: Descripción del segundo parámetro (opcional)
        
    Returns:
        Diccionario con los resultados procesados:
        - key1: Descripción del valor
        - key2: Descripción de otro valor
        
    Raises:
        ValueError: Si param1 está vacío
        TypeError: Si param2 no es un entero
        
    Example:
        >>> result = complex_function("test", 42)
        >>> print(result["key1"])
        processed_value
        
    Note:
        Esta función tiene efectos secundarios en el sistema de archivos.
    """
```

### 🧪 Testing

#### **Tests Unitarios**
```python
# tests/unit/test_orchestrator.py

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from src.orchestrator import ScrapingOrchestrator
from src.exceptions import ConfigurationError


class TestScrapingOrchestrator:
    """Tests para la clase ScrapingOrchestrator."""
    
    @pytest.fixture
    def mock_config(self):
        """Configuración mock para tests."""
        return {
            "database": {"path": "test.db"},
            "execution": {"max_parallel_scrapers": 4}
        }
    
    @pytest.fixture
    def orchestrator(self, mock_config, tmp_path):
        """Instancia de orchestrator para tests."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("database:\n  path: test.db")
        
        with patch('src.orchestrator.yaml.safe_load', return_value=mock_config):
            return ScrapingOrchestrator(str(config_file))
    
    def test_initialization_success(self, orchestrator):
        """Test inicialización exitosa del orchestrator."""
        assert orchestrator.config is not None
        assert orchestrator.running is False
        assert orchestrator.db_path.name == "test.db"
    
    def test_initialization_with_invalid_config(self, tmp_path):
        """Test inicialización con configuración inválida."""
        config_file = tmp_path / "invalid_config.yaml"
        config_file.write_text("invalid: yaml: content:")
        
        with pytest.raises(ConfigurationError):
            ScrapingOrchestrator(str(config_file))
    
    @patch('src.orchestrator.ScrapingOrchestrator._execute_tasks')
    def test_execute_batch_success(self, mock_execute, orchestrator):
        """Test ejecución exitosa de lote."""
        mock_execute.return_value = True
        
        result = orchestrator.execute_batch("test_batch")
        
        assert result is True
        mock_execute.assert_called_once()
    
    def test_execute_batch_with_empty_batch_id(self, orchestrator):
        """Test ejecución con batch_id vacío."""
        with pytest.raises(ValueError, match="batch_id cannot be empty"):
            orchestrator.execute_batch("")
```

#### **Tests de Integración**
```python
# tests/integration/test_scraper_integration.py

import pytest
import tempfile
from pathlib import Path

from src.orchestrator import ScrapingOrchestrator
from src.adapters import ImprovedScraperAdapter


class TestScraperIntegration:
    """Tests de integración entre orchestrator y adapters."""
    
    @pytest.fixture
    def temp_project_dir(self):
        """Directorio temporal del proyecto para tests."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            
            # Crear estructura básica
            (project_dir / "Scrapers").mkdir()
            (project_dir / "urls").mkdir()
            (project_dir / "data").mkdir()
            (project_dir / "config").mkdir()
            
            # Crear scraper mock
            scraper_content = '''
def main():
    print("Mock scraper executed")
    return True
'''
            (project_dir / "Scrapers" / "test_scraper.py").write_text(scraper_content)
            
            # Crear URL file mock
            url_content = "PaginaWeb,Ciudad,Operacion,ProductoPaginaWeb,URL\\nTest,Gdl,Ven,Dep,https://example.com"
            (project_dir / "urls" / "test_scraper_urls.csv").write_text(url_content)
            
            yield project_dir
    
    def test_full_scraper_execution_workflow(self, temp_project_dir):
        """Test del workflow completo de ejecución de scraper."""
        # Configurar orchestrator
        orchestrator = ScrapingOrchestrator()
        orchestrator.base_dir = temp_project_dir
        
        # Cargar tareas
        tasks = orchestrator.load_urls_from_csv("test_scraper")
        assert len(tasks) == 1
        assert tasks[0].scraper_name == "test_scraper"
        
        # Configurar adapter
        adapter = ImprovedScraperAdapter(temp_project_dir)
        
        # Ejecutar tarea
        task_info = {
            'scraper_name': 'test_scraper',
            'website': 'Test',
            'city': 'Gdl',
            'operation': 'Ven',
            'product': 'Dep',
            'url': 'https://example.com',
            'output_file': str(temp_project_dir / "output.csv")
        }
        
        result = adapter.adapt_and_execute_scraper(task_info)
        assert result is True
```

### 🔍 Code Review Checklist

#### **Para el Autor del PR**

- [ ] Código sigue las convenciones de estilo
- [ ] Tests añadidos para nueva funcionalidad
- [ ] Documentación actualizada
- [ ] Changelog actualizado
- [ ] Pre-commit hooks pasan
- [ ] Tests pasan localmente
- [ ] Performance considerado
- [ ] Seguridad considerada

#### **Para el Reviewer**

- [ ] Código es claro y mantenible
- [ ] Lógica de negocio es correcta
- [ ] Tests cubren casos edge
- [ ] No hay código duplicado
- [ ] Manejo de errores es apropiado
- [ ] Logging es adecuado
- [ ] Documentación es clara
- [ ] Breaking changes identificados

## 🔄 Proceso de Pull Request

### 📝 Template de Pull Request

```markdown
## 📋 Descripción

Breve descripción de los cambios realizados.

### 🎯 Tipo de Cambio

- [ ] 🐛 Bug fix
- [ ] ✨ Nueva funcionalidad
- [ ] 💥 Breaking change
- [ ] 📚 Documentación
- [ ] 🎨 Refactoring
- [ ] ⚡ Performance
- [ ] 🧪 Tests

### 🔗 Issues Relacionados

Fixes #123
Related to #456

### 🧪 Testing

- [ ] Tests unitarios añadidos/actualizados
- [ ] Tests de integración añadidos/actualizados
- [ ] Tests manuales realizados

### 📚 Documentación

- [ ] Documentación actualizada
- [ ] Changelog actualizado
- [ ] API documentation actualizada

### ✅ Checklist

- [ ] Código sigue estándares del proyecto
- [ ] Self-review realizado
- [ ] Tests pasan
- [ ] Pre-commit hooks pasan
- [ ] No hay conflictos de merge
```

### 🔍 Proceso de Review

1. **Automated Checks**: CI/CD ejecuta tests y linting
2. **Code Review**: Al menos un maintainer revisa el código
3. **Testing**: Tests automatizados y manuales según sea necesario
4. **Documentation**: Verificar que la documentación está actualizada
5. **Approval**: Aprobación de maintainer
6. **Merge**: Squash and merge o merge commit según el caso

### 📊 Criterios de Aceptación

- ✅ Todos los tests pasan
- ✅ Code coverage no disminuye significativamente
- ✅ Performance no se degrada
- ✅ Documentación está actualizada
- ✅ Breaking changes están documentados
- ✅ Al menos una aprobación de maintainer

## 🧪 Testing

### 🎯 Estrategia de Testing

```
pyramid de tests:
    /\
   /  \
  /E2E \ <- Pocos tests, alta confianza
 /______\
/  INTEG  \ <- Tests de integración
/__________\
/   UNIT    \ <- Muchos tests, rápidos
/____________\
```

### 📋 Tipos de Tests

#### **1. Tests Unitarios**
- **Propósito**: Probar funciones/métodos individuales
- **Scope**: Una función o método específico
- **Velocidad**: Muy rápidos (< 1ms cada uno)
- **Aislamiento**: Mocks para dependencias externas

```python
def test_calculate_success_rate():
    """Test cálculo de tasa de éxito."""
    # Arrange
    completed = 95
    failed = 5
    
    # Act
    rate = calculate_success_rate(completed, failed)
    
    # Assert
    assert rate == 95.0
```

#### **2. Tests de Integración**
- **Propósito**: Probar interacciones entre componentes
- **Scope**: Múltiples clases trabajando juntas
- **Velocidad**: Moderados (< 100ms cada uno)
- **Aislamiento**: Base de datos en memoria, filesystem temporal

```python
def test_orchestrator_database_integration():
    """Test integración orchestrator-database."""
    # Usar base de datos temporal
    with tempfile.NamedTemporaryFile(suffix='.db') as temp_db:
        orchestrator = ScrapingOrchestrator(db_path=temp_db.name)
        
        # Test operaciones CRUD
        batch_id = orchestrator.create_batch()
        assert batch_id is not None
        
        batch_info = orchestrator.get_batch_info(batch_id)
        assert batch_info['batch_id'] == batch_id
```

#### **3. Tests End-to-End**
- **Propósito**: Probar workflows completos
- **Scope**: Sistema completo
- **Velocidad**: Lentos (> 1s cada uno)
- **Aislamiento**: Ambiente de test dedicado

```python
def test_complete_scraping_workflow():
    """Test workflow completo de scraping."""
    # Setup ambiente de test
    setup_test_environment()
    
    # Ejecutar workflow completo
    result = run_scraping_workflow("test_batch")
    
    # Verificar resultados
    assert result.success is True
    assert result.tasks_completed > 0
    assert result.output_files_generated > 0
```

### 🚀 Ejecutar Tests

```bash
# Todos los tests
python -m pytest

# Tests unitarios solamente
python -m pytest tests/unit/

# Tests con coverage
python -m pytest --cov=src tests/

# Tests específicos
python -m pytest tests/unit/test_orchestrator.py::test_initialization

# Tests con output verbose
python -m pytest -v

# Tests en paralelo
python -m pytest -n auto

# Tests que fallan solamente
python -m pytest --lf
```

### 📊 Coverage Requirements

- **Mínimo**: 80% coverage total
- **Target**: 90% coverage para código nuevo
- **Critical paths**: 95% coverage requerido

```bash
# Generar reporte de coverage
python -m pytest --cov=src --cov-report=html tests/

# Ver reporte
open htmlcov/index.html
```

## 📚 Documentación

### 📝 Tipos de Documentación

1. **README.md**: Información general y getting started
2. **API Documentation**: Documentación de APIs y interfaces
3. **User Guides**: Guías para usuarios finales
4. **Developer Documentation**: Documentación técnica
5. **Examples**: Ejemplos de uso
6. **Changelog**: Registro de cambios

### ✍️ Escribiendo Documentación

#### **Principios**

- **Claridad**: Usar lenguaje simple y directo
- **Completitud**: Cubrir todos los casos de uso
- **Actualidad**: Mantener sincronizada con el código
- **Ejemplos**: Incluir ejemplos prácticos
- **Estructura**: Organización lógica y navegable

#### **Formato Markdown**

```markdown
# Título Principal

## Sección

### Subsección

**Texto en negrita** y *texto en cursiva*

```python
# Bloque de código con sintaxis highlighting
def example_function():
    return "Hello World"
```

> Nota importante en blockquote

- Lista con bullets
- Segundo elemento

1. Lista numerada
2. Segundo elemento

| Columna 1 | Columna 2 |
|-----------|-----------|
| Valor A   | Valor B   |

[Link externo](https://example.com)
[Link interno](./other-doc.md)
```

## 🐛 Reporte de Issues

### 📋 Template de Bug Report

```markdown
## 🐛 Bug Report

### 📝 Descripción

Descripción clara y concisa del bug.

### 🔄 Pasos para Reproducir

1. Ir a '...'
2. Hacer click en '....'
3. Scroll down to '....'
4. Ver error

### 🎯 Comportamiento Esperado

Descripción clara de lo que esperabas que pasara.

### 📱 Screenshots

Si aplica, agregar screenshots para ayudar a explicar el problema.

### 🖥️ Información del Sistema

- OS: [e.g. Windows 10]
- Python Version: [e.g. 3.9.7]
- Versión del Proyecto: [e.g. 1.2.3]

### 📝 Contexto Adicional

Cualquier otra información que pueda ser relevante.
```

### ✨ Template de Feature Request

```markdown
## ✨ Feature Request

### 🎯 ¿Está relacionado con un problema?

Descripción clara de cuál es el problema. Ej: Estoy siempre frustrado cuando [...]

### 💡 Solución Propuesta

Descripción clara de lo que te gustaría que pasara.

### 🔄 Alternativas Consideradas

Descripción de cualquier solución alternativa que hayas considerado.

### 📝 Contexto Adicional

Cualquier otra información o screenshots sobre la feature request.
```

### 🏷️ Labels para Issues

| Label | Propósito | Ejemplo |
|-------|-----------|---------|
| `bug` | Bug confirmado | Error en base de datos |
| `enhancement` | Nueva funcionalidad | Agregar soporte para sitio X |
| `documentation` | Mejora en docs | Actualizar README |
| `good-first-issue` | Fácil para novatos | Typo en documentación |
| `help-wanted` | Necesita ayuda | Implementar feature compleja |
| `question` | Pregunta | ¿Cómo configuro X? |
| `wontfix` | No se arreglará | Feature fuera de scope |
| `duplicate` | Issue duplicado | Ya reportado en #123 |

---

## 🎉 ¡Gracias por Contribuir!

Tu tiempo y esfuerzo ayudan a hacer este proyecto mejor para todos. Cada contribución, sin importar cuán pequeña sea, es valiosa y apreciada.

### 🏆 Reconocimiento

Los contribuidores son reconocidos en:

- **README.md**: Lista de contribuidores
- **CHANGELOG.md**: Créditos por feature/fix
- **Release Notes**: Menciones especiales
- **Contributors Page**: Página dedicada (futuro)

### 📞 ¿Necesitas Ayuda?

- 💬 **Discord**: [Únete a nuestro servidor](https://discord.gg/scraping-orchestrator)
- 📧 **Email**: [contribuidores@scraping-system.com](mailto:contribuidores@scraping-system.com)
- 📖 **Documentación**: [docs.scraping-system.com](https://docs.scraping-system.com)
- 🐛 **Issues**: [GitHub Issues](https://github.com/proyecto/issues)

¡Esperamos tus contribuciones! 🚀
