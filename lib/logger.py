## lib/logger.py


import os
import logging
import datetime
from dotenv import load_dotenv
from colorlog import ColoredFormatter
from logging.handlers import RotatingFileHandler

load_dotenv()

# Environment Config
LOG_DIR = "logs"
ENV = os.getenv("ENV", "development").lower()
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FILE = os.getenv("LOG_FILE", os.path.join(LOG_DIR, "app.log"))

# Feature toggles (enabled by default, override in .env if needed)
ENABLE_CONSOLE_LOG = os.getenv("ENABLE_CONSOLE_LOG", "true").lower() == "true"
ENABLE_FILE_LOG = os.getenv("ENABLE_FILE_LOG", "true").lower() == "true"

# Ensure logs directory exists if file logging is enabled
if ENABLE_FILE_LOG:
    os.makedirs(LOG_DIR, exist_ok=True)

# Formatter - Console and File (No color in file logs)
DATE_FORMAT = "%Y-%m-%d %H:%M:%S.%f"
LOG_FORMAT = "%(asctime)s [%(name)s] - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"

# Custom formatter to include milliseconds
class MillisecondFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        dt = datetime.datetime.fromtimestamp(record.created)
        if datefmt:
            s = dt.strftime(datefmt)
            return s[:-3]
        return super().formatTime(record, datefmt)

# Colored formatter subclass to support milliseconds in console
class ColoredMillisecondFormatter(ColoredFormatter):
    def formatTime(self, record, datefmt=None):
        dt = datetime.datetime.fromtimestamp(record.created)
        if datefmt:
            s = dt.strftime(datefmt)
            return s[:-3]
        return super().formatTime(record, datefmt)

# Use custom colored formatter for console output
COLORED_FORMAT = ColoredMillisecondFormatter(
    "%(log_color)s%(asctime)s [%(name)s] - %(levelname)s - %(filename)s:%(lineno)d - %(message)s",
    datefmt=DATE_FORMAT,
    log_colors={
        "DEBUG": "cyan",
        "INFO": "green",
        "WARNING": "yellow",
        "ERROR": "red",
        "CRITICAL": "bold_red",
    },
)

def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)

    # Avoid re-configuring handlers on repeated calls
    if logger.handlers:
        return logger

    # Fast path: if logging is fully disabled, attach NullHandler and return
    if not ENABLE_CONSOLE_LOG and not ENABLE_FILE_LOG:
        null_handler = logging.NullHandler()
        logger.addHandler(null_handler)
        # Set to a minimal level so that no real logging occurs
        logger.setLevel(logging.WARNING)
        return logger

    # Set the global log level as configured
    logger.setLevel(LOG_LEVEL)

    # Console Handler (optional)
    if ENABLE_CONSOLE_LOG:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(LOG_LEVEL)
        console_handler.setFormatter(COLORED_FORMAT)
        logger.addHandler(console_handler)

    # File Handler with rotation (optional)
    if ENABLE_FILE_LOG:
        file_handler = RotatingFileHandler(
            LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5
        )
        file_handler.setLevel(LOG_LEVEL)
        file_handler.setFormatter(MillisecondFormatter(LOG_FORMAT, datefmt=DATE_FORMAT))
        logger.addHandler(file_handler)

    # Prevent logs from propagating to the root logger
    logger.propagate = False

    return logger