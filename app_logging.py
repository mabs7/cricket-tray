"""Bounded local diagnostics, useful for investigating disappearing windows."""
import logging
from logging.handlers import RotatingFileHandler
from settings import settings_path

def configure_logging():
    try:
        path = settings_path().with_name("app.log")
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(path, maxBytes=512_000, backupCount=2, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.INFO)
    except OSError:
        pass

