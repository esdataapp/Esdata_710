import os
import subprocess
import Herramientas as h

class Orquestador:
    def __init__(self, urls_path, listas_path, scrapers_path):
        self.urls_path = urls_path
        self.listas_path = listas_path
        self.scrapers_path = scrapers_path
        self.data_path = os.path.join(os.path.dirname(scrapers_path), 'data')

    def ejecutar_scrapers(self):
        h.limpiar_archivos_json(self.data_path)
        
        scrapers = [f for f in os.listdir(self.scrapers_path) if f.endswith('.py') and f != '__init__.py']
        
        for scraper_file in scrapers:
            scraper_name = os.path.splitext(scraper_file)[0]
            url_file = os.path.join(self.urls_path, f"{scraper_name}_urls.txt")
            lista_file = os.path.join(self.listas_path, f"{scraper_name}_lista.txt")
            scraper_path = os.path.join(self.scrapers_path, scraper_file)
            
            if os.path.exists(url_file) and os.path.exists(lista_file):
                print(f"Ejecutando scraper: {scraper_file}")
                try:
                    # Pasa las rutas como argumentos de línea de comandos al scraper
                    subprocess.run(['python', scraper_path, url_file, lista_file], check=True)
                except subprocess.CalledProcessError as e:
                    print(f"Error al ejecutar {scraper_file}: {e}")
            else:
                print(f"Archivos de configuración no encontrados para {scraper_name}, saltando scraper.")
