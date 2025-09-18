"""DEPRECADO
Funciones utilitarias versión anterior. Reemplazadas por lógica centralizada.
"""

import os

def crear_carpetas_necesarias():
    carpetas = ["urls", "lista de variables", "Scrapers", "data"]
    for carpeta in carpetas:
        if not os.path.exists(carpeta):
            os.makedirs(carpeta)
            print(f"Carpeta '{carpeta}' creada.")

def limpiar_archivos_json(carpeta):
    # Obsoleto: se deja placeholder
    pass
