import logging
import sys

from app.config import settings


def setup_logging() -> None:
    """Configure le logging pour l'application."""
    log_level = logging.DEBUG if settings.debug else logging.INFO

    # Format des logs
    log_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Configuration du handler console
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(log_format, datefmt=date_format))

    # Configuration du logger racine
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(handler)

    # Reduire le niveau de log pour les librairies externes
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Retourne un logger configure pour un module."""
    return logging.getLogger(name)
