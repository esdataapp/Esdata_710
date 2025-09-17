import os

def crear_carpetas_necesarias():
    """Crea todas las carpetas necesarias para el proyecto si no existen."""
    carpetas = [
        "urls",
        "lista de variables",
        "Scrapers",
        "data"
    ]
    for carpeta in carpetas:
        if not os.path.exists(carpeta):
            os.makedirs(carpeta)
            print(f"Carpeta '{carpeta}' creada.")

def limpiar_archivos_json(carpeta):
    """Elimina todos los archivos JSON en la carpeta especificada."""
    # ...existing code...