__copyright__ = "Copyright (C) 2025 TwoBitsWare"
__license__ = "GNU GPLv2"

import logging
import logging.config
import sys
from pathlib import Path

APP_LOGGER_NAME = "Beanquick"

def setup_logging(
    toga_logs_path: Path, 
    app_log_level: int = logging.INFO, 
    console_log_level: int = logging.DEBUG
) -> None:
    """
    Logging system configuration for a Toga application.
    
    Args:
        toga_logs_path: The app.paths.logs Path object from the Toga App.
        app_log_level: Minimum logging level for application file logs.
        console_log_level: Minimum logging level for console output.
        
    Raises:
        OSError: If log directory cannot be created.
        ValueError: If log levels are invalid.
    """
    if not toga_logs_path.exists():
        try:
            toga_logs_path.mkdir(parents=True, exist_ok=True)
        except OSError as e:
           raise OSError(f"Failed to create log directory at {toga_logs_path}: {e}") from e


    log_file_name = "app.log"
    log_file_path = toga_logs_path / log_file_name

    # Calculate the minimum level needed across all handlers
    min_level = min(app_log_level, console_log_level)

    LOGGING_CONFIG = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": "%(asctime)s - %(levelname)s - [%(name)s:%(module)s:%(funcName)s:%(lineno)d] - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "simple_console": {
                "format": "%(asctime)s - %(levelname)s - [%(name)s] - %(message)s",
                "datefmt": "%H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "level": console_log_level,
                "class": "logging.StreamHandler",
                "formatter": "simple_console",
                "stream": sys.stdout,
            },
            "file_rotating": {
                "level": app_log_level,
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "standard",
                "filename": str(log_file_path),
                "maxBytes": 5 * 1024 * 1024, # 5 MB
                "backupCount": 5,
                "encoding": "utf-8",
                "mode": "a",
            },
        },
        "loggers": {
            APP_LOGGER_NAME: {
                "handlers": ["console", "file_rotating"],
                "level": min_level,
                "propagate": False,
            },
        },
        "root": {
            "handlers": ["console", "file_rotating"],
            "level": min_level,
        },
    }

    try:
        logging.config.dictConfig(LOGGING_CONFIG)
        init_logger = logging.getLogger(APP_LOGGER_NAME)
        init_logger.info(f"Logging system configuration complete. Log file located at: {log_file_path}")
        init_logger.info(f"App file log level: {logging.getLevelName(app_log_level)}")
        init_logger.info(f"Console log level: {logging.getLevelName(console_log_level)}")
    except Exception as e:
        # Fallback to basic logging if configuration fails
        logging.basicConfig(
            level=min_level,
            format="%(asctime)s - %(levelname)s - [%(name)s:%(module)s:%(funcName)s:%(lineno)d] - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler(str(log_file_path), mode="a", encoding="utf-8", delay=True)
            ]
        )
        fallback_logger = logging.getLogger(APP_LOGGER_NAME)
        fallback_logger.error("Failed to configure logging system, falling back to basic configuration.")

   
def get_logger(name: str = APP_LOGGER_NAME) -> logging.Logger:
    """
    Get a logger instance for the application.
    
    Args:
        name: Logger name, defaults to APP_LOGGER_NAME
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


def set_log_level(logger_name: str, level: int) -> None:
    """
    Dynamically change log level for a specific logger.
    
    Args:
        logger_name: Name of the logger
        level: New log level
    """
    logger = logging.getLogger(logger_name)
    logger.setLevel(level)
    logger.info(f"Log level changed to {logging.getLevelName(level)}")
