#!/usr/bin/env python3
"""Test simplificado del orchestrador"""

import sys
from pathlib import Path
from orchestrator import WindowsScrapingOrchestrator
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Test con URLs limitadas"""
    try:
        # Inicializar orchestrador
        orchestrator = WindowsScrapingOrchestrator()
        
        # Cargar URLs desde archivo de test
        test_urls_file = Path("urls/test_urls.csv")
        
        print("=== TEST ORCHESTRADOR ===")
        print(f"Archivo URLs: {test_urls_file}")
        
        if not test_urls_file.exists():
            print(f"ERROR: Archivo {test_urls_file} no existe")
            return False
            
        # Ejecutar con URLs limitadas
        batch_id, month_year, execution_number = orchestrator.generate_batch_id()
        
        # Cargar URLs de test - vamos a usar una tarea manual
        import pandas as pd
        df = pd.read_csv(test_urls_file)
        main_tasks = []
        
        for order, (_, row) in enumerate(df.iterrows()):
            from orchestrator import ScrapingTask, ScrapingStatus
            task = ScrapingTask(
                scraper_name=row['PaginaWeb'].lower(),
                website=row['PaginaWeb'],
                city=row['Ciudad'],
                operation=row['Operacion'],
                product=row['ProductoPaginaWeb'],
                url=row['URL'],
                order=order + 1
            )
            main_tasks.append(task)
        
        print(f"Tareas cargadas: {len(main_tasks)}")
        for task in main_tasks:
            print(f"  - {task.scraper_name}: {task.url}")
        
        # Ejecutar tareas
        orchestrator.execute_tasks_parallel(main_tasks, batch_id, month_year, execution_number)
        
        return True
        
    except Exception as e:
        logger.error(f"Error en test: {e}")
        return False

if __name__ == "__main__":
    main()