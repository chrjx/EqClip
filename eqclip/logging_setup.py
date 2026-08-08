"""Central logging configuration for EqClip.

Logs go to ~/Library/Logs/EqClip/eqclip.log -- the standard macOS location
Console.app also watches -- with rotation so it can't grow unbounded, plus
a mirrored stream to stdout so `python3 main.py` shows the same thing live
in Terminal. Full request/response text (backend, model, image size,
timing, and the transcribed text itself) is logged at INFO so the whole
pipeline is visible for debugging things like slow responses.
"""

import logging
import logging.handlers
import os

LOG_DIR = os.path.expanduser("~/Library/Logs/EqClip")
LOG_PATH = os.path.join(LOG_DIR, "eqclip.log")

_ROOT_NAME = "eqclip"
_configured = False


def setup(level=logging.INFO):
    global _configured
    if _configured:
        return logging.getLogger(_ROOT_NAME)

    os.makedirs(LOG_DIR, exist_ok=True)

    logger = logging.getLogger(_ROOT_NAME)
    logger.setLevel(level)
    logger.propagate = False

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-7s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.handlers.RotatingFileHandler(
        LOG_PATH, maxBytes=2 * 1024 * 1024, backupCount=3
    )
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(fmt)
    logger.addHandler(console_handler)

    _configured = True
    logger.info("Logging started -> %s", LOG_PATH)
    return logger


def get_logger(name):
    return logging.getLogger(f"{_ROOT_NAME}.{name}")
