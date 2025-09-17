import os
import Herramientas as h
from Orquestador import Orquestador

def main():
    # Crear la estructura de carpetas principal utilizando Herramientas
    h.crear_carpetas_necesarias()

    # Definir las rutas de las carpetas
    base_path = os.path.dirname(os.path.abspath(__file__))
    urls_path = os.path.join(base_path, 'urls')
    listas_path = os.path.join(base_path, 'lista de variables')
    scrapers_path = os.path.join(base_path, 'Scrapers')

    # Instanciar y ejecutar el orquestador con las rutas necesarias
    orquestador = Orquestador(urls_path, listas_path, scrapers_path)
    orquestador.ejecutar_scrapers()

if __name__ == "__main__":
    main()
