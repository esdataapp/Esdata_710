#!/usr/bin/env python3
"""
Monitor CLI - Herramienta de monitoreo para Windows
Sistema de Orquestación de Scraping Inmobiliario
"""

import argparse
import json
import sqlite3
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import yaml
from tabulate import tabulate

# Configurar el directorio base
BASE_DIR = Path(r"C:\Users\criss\Desktop\Esdata 710")
CONFIG_PATH = BASE_DIR / "config" / "config.yaml"

class ScrapingMonitorWindows:
    """Monitor del sistema de scraping para Windows"""
    
    def __init__(self):
        self.base_dir = BASE_DIR
        self.config = self._load_config()
        self.db_path = Path(self.config['database']['path'])
    
    def _load_config(self) -> dict:
        """Carga configuración"""
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            print(f"ERROR: Archivo de configuración no encontrado: {CONFIG_PATH}")
            print("Ejecuta 'python orchestrator.py setup' primero")
            sys.exit(1)
    
    def get_db_connection(self):
        """Obtiene conexión a la base de datos"""
        if not self.db_path.exists():
            print("ERROR: Base de datos no encontrada")
            print("Ejecuta 'python orchestrator.py run' primero para crear la base de datos")
            sys.exit(1)
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def show_status(self, detailed=False):
        """Muestra el estado actual del sistema"""
        print("=== ESTADO DEL SISTEMA DE SCRAPING ===\n")
        
        try:
            with self.get_db_connection() as conn:
                # Estado del último lote
                cursor = conn.execute("""
                    SELECT * FROM execution_batches
                    ORDER BY started_at DESC LIMIT 1
                """)
                last_batch = cursor.fetchone()
                
                if not last_batch:
                    print("❌ No hay lotes de ejecución registrados")
                    print("💡 Ejecuta: python orchestrator.py run")
                    return
                
                # Estadísticas del último lote
                cursor = conn.execute("""
                    SELECT status, COUNT(*) as count
                    FROM scraping_tasks
                    WHERE execution_batch = ?
                    GROUP BY status
                """, (last_batch['batch_id'],))
                
                status_counts = {row['status']: row['count'] for row in cursor.fetchall()}
                
                # Mostrar información del lote
                print(f"📦 Lote Actual: {last_batch['batch_id']}")
                print(f"📅 Iniciado: {last_batch['started_at']}")
                print(f"📊 Estado: {last_batch['status'].upper()}")
                print(f"📈 Total de tareas: {last_batch['total_tasks'] or 0}")
                
                if last_batch['completed_at']:
                    started = datetime.fromisoformat(last_batch['started_at'])
                    completed = datetime.fromisoformat(last_batch['completed_at'])
                    duration = completed - started
                    print(f"⏱️  Duración: {duration}")
                else:
                    started = datetime.fromisoformat(last_batch['started_at'])
                    duration = datetime.now() - started
                    print(f"⏱️  Duración actual: {duration} (en progreso)")
                
                print("\n--- ESTADO DE TAREAS ---")
                
                # Tabla de estados
                status_data = []
                total_tasks = last_batch['total_tasks'] or 1
                
                status_emojis = {
                    'completed': '✅',
                    'running': '🔄',
                    'pending': '⏳',
                    'failed': '❌',
                    'retrying': '🔁'
                }
                
                for status, count in status_counts.items():
                    percentage = (count / total_tasks * 100)
                    emoji = status_emojis.get(status, '❓')
                    status_data.append([
                        f"{emoji} {status.upper()}",
                        count,
                        f"{percentage:.1f}%"
                    ])
                
                print(tabulate(status_data, headers=["Estado", "Cantidad", "Porcentaje"], tablefmt="grid"))
                
                if detailed:
                    # Mostrar tareas fallidas
                    cursor = conn.execute("""
                        SELECT scraper_name, website, city, operation, product, error_message, attempts
                        FROM scraping_tasks
                        WHERE status = 'failed' AND execution_batch = ?
                        ORDER BY scraper_name, website
                    """, (last_batch['batch_id'],))
                    
                    failed_tasks = cursor.fetchall()
                    
                    if failed_tasks:
                        print("\n--- TAREAS FALLIDAS ---")
                        failed_data = []
                        
                        for task in failed_tasks:
                            error_short = task['error_message'][:50] + "..." if task['error_message'] and len(task['error_message']) > 50 else task['error_message'] or "N/A"
                            failed_data.append([
                                task['scraper_name'],
                                task['website'],
                                f"{task['city']}-{task['operation']}-{task['product']}",
                                task['attempts'],
                                error_short
                            ])
                        
                        print(tabulate(failed_data, headers=["Scraper", "Sitio", "Config", "Intentos", "Error"], tablefmt="grid"))
                
        except Exception as e:
            print(f"❌ Error obteniendo estado: {e}")
    
    def show_history(self, limit=10):
        """Muestra el historial de ejecuciones"""
        print(f"=== HISTORIAL DE EJECUCIONES (últimas {limit}) ===\n")
        
        try:
            with self.get_db_connection() as conn:
                cursor = conn.execute("""
                    SELECT batch_id, month_year, execution_number, started_at, completed_at,
                           total_tasks, completed_tasks, failed_tasks, status
                    FROM execution_batches
                    ORDER BY started_at DESC
                    LIMIT ?
                """, (limit,))
                
                batches = cursor.fetchall()
                
                if not batches:
                    print("❌ No hay historial de ejecuciones")
                    return
                
                history_data = []
                
                for batch in batches:
                    started = datetime.fromisoformat(batch['started_at'])
                    
                    if batch['completed_at']:
                        completed = datetime.fromisoformat(batch['completed_at'])
                        duration = str(completed - started)
                        status_emoji = "✅" if batch['status'] == 'completed' else "❌"
                    else:
                        duration = "En progreso"
                        status_emoji = "🔄"
                    
                    history_data.append([
                        batch['batch_id'],
                        started.strftime("%Y-%m-%d %H:%M"),
                        duration,
                        batch['total_tasks'] or 0,
                        batch['completed_tasks'] or 0,
                        batch['failed_tasks'] or 0,
                        f"{status_emoji} {batch['status'].upper()}"
                    ])
                
                print(tabulate(history_data, headers=["Lote", "Fecha", "Duración", "Total", "OK", "Fallos", "Estado"], tablefmt="grid"))
                
        except Exception as e:
            print(f"❌ Error obteniendo historial: {e}")
    
    def show_tasks(self, batch_id=None):
        """Muestra las tareas del último lote o de un lote específico"""
        if batch_id:
            print(f"=== TAREAS DEL LOTE: {batch_id} ===\n")
        else:
            print("=== TAREAS DEL ÚLTIMO LOTE ===\n")
        
        try:
            with self.get_db_connection() as conn:
                if not batch_id:
                    # Obtener el último lote
                    cursor = conn.execute("""
                        SELECT batch_id FROM execution_batches
                        ORDER BY started_at DESC LIMIT 1
                    """)
                    result = cursor.fetchone()
                    if not result:
                        print("❌ No hay lotes de ejecución")
                        return
                    batch_id = result['batch_id']
                    print(f"📦 Mostrando último lote: {batch_id}\n")
                
                cursor = conn.execute("""
                    SELECT scraper_name, website, city, operation, product, status,
                           attempts, started_at, completed_at, error_message
                    FROM scraping_tasks
                    WHERE execution_batch = ?
                    ORDER BY scraper_name, website, city
                """, (batch_id,))
                
                tasks = cursor.fetchall()
                
                if not tasks:
                    print(f"❌ No hay tareas para el lote {batch_id}")
                    return
                
                task_data = []
                status_emojis = {
                    'completed': '✅',
                    'running': '🔄',
                    'pending': '⏳',
                    'failed': '❌',
                    'retrying': '🔁'
                }
                
                for task in tasks:
                    duration = "N/A"
                    if task['started_at'] and task['completed_at']:
                        started = datetime.fromisoformat(task['started_at'])
                        completed = datetime.fromisoformat(task['completed_at'])
                        duration = str(completed - started)
                    elif task['started_at']:
                        started = datetime.fromisoformat(task['started_at'])
                        duration = str(datetime.now() - started) + " (activo)"
                    
                    emoji = status_emojis.get(task['status'], '❓')
                    
                    task_data.append([
                        task['scraper_name'],
                        task['website'],
                        f"{task['city']}-{task['operation']}-{task['product']}",
                        f"{emoji} {task['status'].upper()}",
                        task['attempts'],
                        duration
                    ])
                
                print(tabulate(task_data, headers=["Scraper", "Sitio", "Configuración", "Estado", "Intentos", "Duración"], tablefmt="grid"))
                
        except Exception as e:
            print(f"❌ Error obteniendo tareas: {e}")
    
    def show_system(self):
        """Muestra información del sistema"""
        print("=== INFORMACIÓN DEL SISTEMA ===\n")
        
        try:
            # Información básica
            print(f"📁 Directorio base: {self.base_dir}")
            print(f"🗄️  Base de datos: {self.db_path}")
            print(f"📂 Scrapers: {Path(self.config['scrapers']['path'])}")
            print(f"🌐 URLs: {Path(self.config['data']['urls_path'])}")
            print(f"💾 Datos: {Path(self.config['data']['base_path'])}")
            
            # Verificar archivos
            print("\n--- VERIFICACIÓN DE ARCHIVOS ---")
            
            checks = [
                ("Base de datos", self.db_path),
                ("Configuración", CONFIG_PATH),
                ("Carpeta scrapers", Path(self.config['scrapers']['path'])),
                ("Carpeta URLs", Path(self.config['data']['urls_path'])),
                ("Carpeta datos", Path(self.config['data']['base_path']))
            ]
            
            for name, path in checks:
                if path.exists():
                    print(f"✅ {name}: OK")
                else:
                    print(f"❌ {name}: No encontrado - {path}")
            
            # Archivos de scrapers
            scrapers_dir = Path(self.config['scrapers']['path'])
            if scrapers_dir.exists():
                scrapers = list(scrapers_dir.glob("*.py"))
                print(f"\n🔧 Scrapers encontrados: {len(scrapers)}")
                for scraper in scrapers:
                    print(f"   • {scraper.name}")
            
            # Archivos de URLs
            urls_dir = Path(self.config['data']['urls_path'])
            if urls_dir.exists():
                url_files = list(urls_dir.glob("*_urls.csv"))
                print(f"\n🌐 Archivos de URLs: {len(url_files)}")
                for url_file in url_files:
                    try:
                        df = pd.read_csv(url_file)
                        print(f"   • {url_file.name}: {len(df)} URLs")
                    except:
                        print(f"   • {url_file.name}: Error leyendo archivo")
            
            # Espacio en disco (aproximado)
            if self.base_dir.exists():
                total_size = sum(f.stat().st_size for f in self.base_dir.rglob('*') if f.is_file())
                size_mb = total_size / (1024 * 1024)
                print(f"\n💽 Espacio usado: {size_mb:.1f} MB")
                
        except Exception as e:
            print(f"❌ Error obteniendo información del sistema: {e}")
    
    def show_stats(self, days=30):
        """Muestra estadísticas de rendimiento"""
        print(f"=== ESTADÍSTICAS (últimos {days} días) ===\n")
        
        try:
            date_limit = datetime.now() - timedelta(days=days)
            
            with self.get_db_connection() as conn:
                # Estadísticas por sitio web
                cursor = conn.execute("""
                    SELECT website, 
                           COUNT(*) as total_tasks,
                           SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                           SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                           AVG(attempts) as avg_attempts
                    FROM scraping_tasks
                    WHERE created_at >= ?
                    GROUP BY website
                    ORDER BY total_tasks DESC
                """, (date_limit.isoformat(),))
                
                website_stats = cursor.fetchall()
                
                if website_stats:
                    print("--- POR SITIO WEB ---")
                    stats_data = []
                    
                    for stat in website_stats:
                        success_rate = (stat['completed'] / stat['total_tasks'] * 100) if stat['total_tasks'] > 0 else 0
                        
                        stats_data.append([
                            stat['website'],
                            stat['total_tasks'],
                            stat['completed'],
                            stat['failed'],
                            f"{success_rate:.1f}%",
                            f"{stat['avg_attempts']:.1f}"
                        ])
                    
                    print(tabulate(stats_data, headers=["Sitio", "Total", "OK", "Fallos", "Éxito", "Prom.Int."], tablefmt="grid"))
                else:
                    print("❌ No hay estadísticas disponibles para el período especificado")
                
                # Estadísticas por ciudad
                cursor = conn.execute("""
                    SELECT city, 
                           COUNT(*) as total_tasks,
                           SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                           SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
                    FROM scraping_tasks
                    WHERE created_at >= ?
                    GROUP BY city
                    ORDER BY total_tasks DESC
                    LIMIT 10
                """, (date_limit.isoformat(),))
                
                city_stats = cursor.fetchall()
                
                if city_stats:
                    print("\n--- POR CIUDAD (Top 10) ---")
                    city_data = []
                    
                    for stat in city_stats:
                        success_rate = (stat['completed'] / stat['total_tasks'] * 100) if stat['total_tasks'] > 0 else 0
                        
                        city_data.append([
                            stat['city'],
                            stat['total_tasks'],
                            stat['completed'],
                            stat['failed'],
                            f"{success_rate:.1f}%"
                        ])
                    
                    print(tabulate(city_data, headers=["Ciudad", "Total", "OK", "Fallos", "Éxito"], tablefmt="grid"))
                
        except Exception as e:
            print(f"❌ Error obteniendo estadísticas: {e}")
    
    def run_now(self):
        """Ejecuta un lote de scraping inmediatamente"""
        print("🚀 Iniciando ejecución inmediata...\n")
        
        try:
            # Cambiar al directorio del proyecto
            original_cwd = os.getcwd()
            os.chdir(self.base_dir)
            
            # Ejecutar orchestrator
            import subprocess
            result = subprocess.run([
                sys.executable, 'orchestrator.py', 'run'
            ], capture_output=True, text=True, encoding='utf-8')
            
            # Restaurar directorio
            os.chdir(original_cwd)
            
            if result.returncode == 0:
                print("✅ Ejecución completada exitosamente")
                if result.stdout:
                    print("\n--- OUTPUT ---")
                    print(result.stdout)
            else:
                print("❌ Error en la ejecución")
                if result.stderr:
                    print("\n--- ERROR ---")
                    print(result.stderr)
                    
        except Exception as e:
            print(f"❌ Error ejecutando scraping: {e}")
            os.chdir(original_cwd)


def main():
    """Función principal del CLI"""
    parser = argparse.ArgumentParser(description='Monitor CLI - Sistema de Orquestación de Scraping')
    
    parser.add_argument('command', nargs='?', choices=[
        'status', 'history', 'tasks', 'system', 'stats', 'run'
    ], help='Comando a ejecutar')
    
    parser.add_argument('--detailed', '-d', action='store_true', help='Mostrar información detallada')
    parser.add_argument('--limit', '-l', type=int, default=10, help='Número de elementos a mostrar')
    parser.add_argument('--batch-id', '-b', help='ID específico del lote')
    parser.add_argument('--days', type=int, default=30, help='Días hacia atrás para estadísticas')
    
    args = parser.parse_args()
    
    if not args.command:
        print("=== MONITOR CLI - Sistema de Orquestación de Scraping ===")
        print(f"📁 Directorio: {BASE_DIR}")
        print("\nComandos disponibles:")
        print("  python monitor_cli.py status     # Estado actual")
        print("  python monitor_cli.py history    # Historial de ejecuciones")
        print("  python monitor_cli.py tasks      # Tareas del último lote")
        print("  python monitor_cli.py system     # Información del sistema")
        print("  python monitor_cli.py stats      # Estadísticas de rendimiento")
        print("  python monitor_cli.py run        # Ejecutar scraping ahora")
        print("\nOpciones:")
        print("  --detailed, -d                   # Información detallada")
        print("  --limit N, -l N                  # Limitar resultados")
        print("  --batch-id ID, -b ID             # Lote específico")
        print("  --days N                         # Días para estadísticas")
        return
    
    monitor = ScrapingMonitorWindows()
    
    try:
        if args.command == 'status':
            monitor.show_status(detailed=args.detailed)
        elif args.command == 'history':
            monitor.show_history(limit=args.limit)
        elif args.command == 'tasks':
            monitor.show_tasks(batch_id=args.batch_id)
        elif args.command == 'system':
            monitor.show_system()
        elif args.command == 'stats':
            monitor.show_stats(days=args.days)
        elif args.command == 'run':
            monitor.run_now()
    except KeyboardInterrupt:
        print("\n❌ Operación cancelada por el usuario")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == '__main__':
    main()
