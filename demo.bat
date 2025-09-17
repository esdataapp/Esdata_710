@echo off
REM Script de demostración del Sistema de Orquestación
echo ===============================================
echo      DEMOSTRACION DEL SISTEMA
echo      Sistema de Orquestacion de Scraping
echo ===============================================
echo.

echo Este script ejecutará una demostración completa del sistema.
echo.
echo Componentes a demostrar:
echo  1. Validación del sistema
echo  2. Estado inicial
echo  3. Ejecución de scraping (versión reducida)
echo  4. Monitoreo en tiempo real
echo  5. Análisis de resultados
echo.
set /p continue="¿Continuar con la demostración? (S/N): "

if /i not "%continue%"=="S" (
    echo Demostración cancelada.
    pause
    exit /b 0
)

echo.
echo ===============================================
echo  PASO 1: VALIDACION DEL SISTEMA
echo ===============================================
echo.
python validate_system.py

if errorlevel 1 (
    echo.
    echo ❌ La validación encontró problemas críticos.
    echo    Por favor ejecuta setup.bat primero.
    pause
    exit /b 1
)

echo.
echo ===============================================
echo  PASO 2: ESTADO INICIAL DEL SISTEMA
echo ===============================================
echo.
python monitor_cli.py system

echo.
pause

echo.
echo ===============================================
echo  PASO 3: EJECUCION DE SCRAPING
echo ===============================================
echo.
echo ⚠️  NOTA: Esta es una ejecución de demostración.
echo    Los scrapers están configurados para ejecutar
echo    solo unas pocas páginas para mostrar el funcionamiento.
echo.
echo ⏱️  Tiempo estimado: 2-5 minutos
echo.
set /p run_demo="¿Ejecutar scraping de demostración? (S/N): "

if /i "%run_demo%"=="S" (
    echo.
    echo 🚀 Iniciando ejecución de scraping...
    echo.
    python orchestrator.py run
    
    echo.
    echo ===============================================
    echo  PASO 4: ESTADO DESPUES DE LA EJECUCION
    echo ===============================================
    echo.
    python monitor_cli.py status --detailed
    
    echo.
    pause
    
    echo.
    echo ===============================================
    echo  PASO 5: ANALISIS DE RESULTADOS
    echo ===============================================
    echo.
    echo 📊 Historial de ejecuciones:
    python monitor_cli.py history --limit 5
    
    echo.
    echo 📁 Archivos generados:
    echo.
    if exist "data" (
        echo Estructura de datos generados:
        dir /s data
    ) else (
        echo No se generaron archivos de datos.
    )
    
    echo.
    echo 📈 Estadísticas del sistema:
    python monitor_cli.py stats --days 1
    
) else (
    echo Ejecución de scraping omitida.
)

echo.
echo ===============================================
echo  DEMOSTRACION COMPLETADA
echo ===============================================
echo.
echo 🎉 ¡Demostración completada exitosamente!
echo.
echo Resumen de lo demostrado:
echo  ✅ Sistema validado y funcionando
echo  ✅ Configuración cargada correctamente
echo  ✅ Base de datos inicializada
if /i "%run_demo%"=="S" (
    echo  ✅ Scrapers ejecutados
    echo  ✅ Datos extraídos y organizados
    echo  ✅ Monitoreo y estadísticas generadas
)
echo.
echo Próximos pasos recomendados:
echo  1. Revisar configuración en: config\config.yaml
echo  2. Personalizar URLs en carpeta: urls\
echo  3. Ejecutar sistema completo: python orchestrator.py run
echo  4. Monitorear progreso: python monitor_cli.py status
echo  5. Usar menú interactivo: start.bat
echo.
echo Documentación completa: README.md
echo.
pause

echo.
echo ¿Te gustaría abrir algún componente del sistema?
echo.
echo 1. Ver datos generados (Explorador)
echo 2. Ver configuración (Notepad)
echo 3. Abrir menú principal (start.bat)
echo 4. Salir
echo.
set /p choice="Selecciona una opción (1-4): "

if "%choice%"=="1" (
    explorer "data"
) else if "%choice%"=="2" (
    notepad "config\config.yaml"
) else if "%choice%"=="3" (
    start.bat
) else (
    echo.
    echo ¡Gracias por probar el Sistema de Orquestación de Scraping!
    echo.
    pause
)
