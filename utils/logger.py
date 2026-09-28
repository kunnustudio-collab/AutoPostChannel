"""
MedQuiz AI - Logger Module
Provides rotating file logging and console output.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from config import LOG_FILE

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logger(name: str = "medquiz") -> logging.Logger:
    """Configures and returns a logger instance with rotating file and console handlers."""
    logger = logging.getLogger(name)

    if logger.hasHandlers():
        return logger

    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT)

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Rotating File Handler (Max 10MB per file, keeping 5 backups)
    try:
        file_handler = RotatingFileHandler(
            filename=str(LOG_FILE),
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8"
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"Warning: Failed to initialize file logger: {e}", file=sys.stderr)

    return logger


logger = setup_logger("medquiz")
