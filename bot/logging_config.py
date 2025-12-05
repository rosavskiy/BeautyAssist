"""
Logging configuration with rotation and structured JSON logging.

This module sets up professional logging for the application with:
- Console output (human-readable)
- File output (JSON structured, with rotation)
- Error file (JSON, only errors, with rotation)
- Suppression of noisy third-party loggers
"""

import logging
import logging.handlers
import json
from datetime import datetime
from pathlib import Path
from bot.config import settings


class JSONFormatter(logging.Formatter):
    """Format logs as JSON for structured logging."""
    
    def format(self, record):
        """
        Format log record as JSON.
        
        Args:
            record: LogRecord instance
        
        Returns:
            JSON string with log data
        """
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add extra fields if present
        if hasattr(record, 'user_id'):
            log_data["user_id"] = record.user_id
        if hasattr(record, 'username'):
            log_data["username"] = record.username
        if hasattr(record, 'master_id'):
            log_data["master_id"] = record.master_id
        if hasattr(record, 'appointment_id'):
            log_data["appointment_id"] = record.appointment_id
        if hasattr(record, 'duration'):
            log_data["duration"] = record.duration
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, ensure_ascii=False)


def setup_logging():
    """
    Setup application logging with multiple handlers.
    
    Creates:
    - Console handler with INFO level (human-readable format)
    - File handler with DEBUG level (JSON format, rotating)
    - Error file handler with ERROR level (JSON format, rotating)
    
    Suppresses noisy third-party loggers (aiogram, aiohttp, etc.)
    """
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level.upper()))
    
    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # === Console Handler (human-readable) ===
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # === File Handler (JSON, with rotation) ===
    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / "beautyassist.log",
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(file_handler)
    
    # === Error File Handler (JSON, with rotation) ===
    error_handler = logging.handlers.RotatingFileHandler(
        log_dir / "errors.log",
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(error_handler)
    
    # === Suppress noisy loggers ===
    # These libraries are too verbose, reduce their log level
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
    logging.getLogger("aiohttp.server").setLevel(logging.WARNING)
    logging.getLogger("aiohttp.web").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.INFO)
    
    logging.info("Logging configured successfully")
    logging.info(f"Log level: {settings.log_level}")
    logging.info(f"Log directory: {log_dir.absolute()}")
