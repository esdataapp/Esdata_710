"""DEPRECADO
Controlador de la versión anterior. Conservado solo como referencia.
"""

import os
import Herramientas as h  # type: ignore
from Orquestador import Orquestador  # type: ignore

def main():
    h.crear_carpetas_necesarias()
    base_path = os.path.dirname(os.path.abspath(__file__))
    urls_path = os.path.join(base_path, 'urls')
    listas_path = os.path.join(base_path, 'lista de variables')
    scrapers_path = os.path.join(base_path, 'Scrapers')
    orquestador = Orquestador(urls_path, listas_path, scrapers_path)
    orquestador.ejecutar_scrapers()

if __name__ == "__main__":
    main()
