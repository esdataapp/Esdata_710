"""
Módulo de utilidad para la creación y gestión de navegadores SeleniumBase.

Este módulo centraliza la lógica para obtener un driver de SeleniumBase,
permitiendo configuraciones consistentes a través de todos los scrapers,
incluyendo el modo 'headless' y el modo con GUI virtual para scrapers
que necesitan interactuar con captchas.
"""
import logging
from contextlib import contextmanager
from seleniumbase import Driver

logger = logging.getLogger(__name__)

@contextmanager
def get_browser(scraper_name: str, headless: bool = True):
    """
    Proporciona un driver de SeleniumBase configurado.
    Se encarga de iniciar y cerrar el driver correctamente.

    Args:
        scraper_name (str): Nombre del scraper que usará el navegador.
        headless (bool): Si es True, se ejecuta en modo sin cabeza.
                         Si es False, se ejecuta con GUI (requiere xvfb en servidor).

    Yields:
        Driver: Una instancia del driver de SeleniumBase.
    """
    logger.info(f"[{scraper_name}] Solicitando navegador en modo {'headless' if headless else 'GUI'}.")
    
    driver_args = {
        "uc": True,
        "headless": headless,
        "block_images": True,
        "args": [
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--window-size=1280,1024"
        ]
    }

    # Si no es headless, nos aseguramos de que xvfb esté en uso.
    if not headless:
        driver_args["xvfb"] = True

    driver = None
    try:
        driver = Driver(**driver_args)
        logger.info(f"[{scraper_name}] Navegador iniciado con éxito.")
        yield driver
    except Exception as e:
        logger.error(f"[{scraper_name}] Fallo al iniciar el navegador: {e}", exc_info=True)
        raise
    finally:
        if driver:
            driver.quit()
            logger.info(f"[{scraper_name}] Navegador cerrado.")
