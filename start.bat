@echo off
REM Script de inicio rápido para el Sistema de Orquestación
echo ===============================================
echo   Sistema de Orquestacion de Scraping
echo   Menu Principal
echo ===============================================
echo.

:menu
echo Selecciona una opción:
echo.
echo 1. Ver estado del sistema
echo 2. Ejecutar scraping completo
echo 3. Ver historial de ejecuciones
echo 4. Ver información del sistema
echo 5. Ver estadísticas
echo 6. Test del sistema
echo 7. Abrir carpeta de datos
echo 8. Editar configuración
echo 9. Salir
echo.
set /p choice="Ingresa tu opción (1-9): "

if "%choice%"=="1" goto status
if "%choice%"=="2" goto run
if "%choice%"=="3" goto history
if "%choice%"=="4" goto system
if "%choice%"=="5" goto stats
if "%choice%"=="6" goto test
if "%choice%"=="7" goto data
if "%choice%"=="8" goto config
if "%choice%"=="9" goto exit

echo Opción inválida. Intenta de nuevo.
echo.
goto menu

:status
echo.
echo === ESTADO DEL SISTEMA ===
python monitor_cli.py status --detailed
echo.
pause
goto menu

:run
echo.
echo === EJECUTANDO SCRAPING ===
echo ADVERTENCIA: Esta operación puede tomar varios minutos
echo.
set /p confirm="¿Continuar? (S/N): "
if /i "%confirm%"=="S" (
    python orchestrator.py run
) else (
    echo Operación cancelada.
)
echo.
pause
goto menu

:history
echo.
echo === HISTORIAL DE EJECUCIONES ===
python monitor_cli.py history --limit 15
echo.
pause
goto menu

:system
echo.
echo === INFORMACIÓN DEL SISTEMA ===
python monitor_cli.py system
echo.
pause
goto menu

:stats
echo.
echo === ESTADÍSTICAS ===
python monitor_cli.py stats --days 60
echo.
pause
goto menu

:test
echo.
echo === TEST DEL SISTEMA ===
python orchestrator.py test
echo.
pause
goto menu

:data
echo.
echo === ABRIENDO CARPETA DE DATOS ===
explorer "data"
goto menu

:config
echo.
echo === EDITANDO CONFIGURACIÓN ===
notepad "config\config.yaml"
goto menu

:exit
echo.
echo ¡Hasta luego!
pause
exit

