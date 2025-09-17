@echo off
REM Script de configuración inicial para Windows
REM Sistema de Orquestación de Scraping
echo ===============================================
echo   Sistema de Orquestacion de Scraping
echo   Configuracion Inicial - Windows
echo ===============================================
echo.

REM Verificar que estamos en el directorio correcto
if not exist "orchestrator.py" (
    echo ERROR: No se encuentra orchestrator.py
    echo Ejecuta este script desde la carpeta Esdata 710
    pause
    exit /b 1
)

echo 1. Verificando Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python no está instalado o no está en el PATH
    echo Instala Python desde https://python.org
    pause
    exit /b 1
)
echo    ✓ Python encontrado

echo.
echo 2. Instalando dependencias de Python...
pip install -r requirements.txt
if errorlevel 1 (
    echo WARNING: Algunas dependencias pueden haber fallado
    echo Continúa de todas formas...
)
echo    ✓ Dependencias instaladas

echo.
echo 3. Creando directorios necesarios...
if not exist "logs" mkdir logs
if not exist "temp" mkdir temp
if not exist "backups" mkdir backups
echo    ✓ Directorios creados

echo.
echo 4. Configurando archivos de ejemplo...
python orchestrator.py setup
if errorlevel 1 (
    echo WARNING: Error creando archivos de ejemplo
) else (
    echo    ✓ Archivos de ejemplo creados
)

echo.
echo 5. Ejecutando validación completa del sistema...
python validate_system.py
if errorlevel 1 (
    echo WARNING: Validación encontró problemas
) else (
    echo    ✓ Validación exitosa
)

echo.
echo 6. Ejecutando test básico...
python orchestrator.py test
if errorlevel 1 (
    echo WARNING: Test básico falló
) else (
    echo    ✓ Test básico exitoso
)

echo.
echo ===============================================
echo           CONFIGURACION COMPLETADA
echo ===============================================
echo.
echo Comandos principales:
echo   python orchestrator.py run       - Ejecutar scraping
echo   python monitor_cli.py status     - Ver estado
echo   python monitor_cli.py system     - Info del sistema
echo.
echo Archivos importantes:
echo   • config\config.yaml             - Configuración
echo   • urls\                          - CSVs con URLs a scrapear
echo   • Scrapers\                      - Scripts de scraping
echo   • data\                          - Datos extraídos
echo.
echo Siguientes pasos:
echo 1. Edita los archivos CSV en la carpeta 'urls\'
echo 2. Ejecuta: python orchestrator.py run
echo 3. Monitorea: python monitor_cli.py status
echo.
pause
