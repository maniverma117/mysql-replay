"""
Centralized logger for MySQL Buffer Pool Warmer
"""

import logging
import os
from logging.handlers import RotatingFileHandler

import config


def create_logger():

    logger = logging.getLogger(config.APP_NAME)

    # Prevent duplicate handlers
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, config.LOG_LEVEL.upper(), logging.INFO))

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(threadName)-15s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    #
    # Console Logger
    #
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    console.setLevel(logging.INFO)

    logger.addHandler(console)

    #
    # File Logger
    #
    log_dir = os.path.dirname(config.LOG_FILE) or os.getcwd()
    log_file_path = config.LOG_FILE

    if log_dir:
        try:
            os.makedirs(log_dir, exist_ok=True)
        except OSError:
            fallback_dir = os.path.join(os.getcwd(), "logs")
            try:
                os.makedirs(fallback_dir, exist_ok=True)
            except OSError:
                fallback_dir = os.getcwd()
            log_file_path = os.path.join(fallback_dir, os.path.basename(config.LOG_FILE))

    try:
        file_handler = RotatingFileHandler(
            filename=log_file_path,
            maxBytes=100 * 1024 * 1024,   # 100 MB
            backupCount=10,
            encoding="utf-8"
        )
    except OSError:
        file_handler = logging.StreamHandler()

    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

    logger.addHandler(file_handler)

    logger.propagate = False

    return logger


logger = create_logger()