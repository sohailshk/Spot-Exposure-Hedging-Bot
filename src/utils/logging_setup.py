"""
Logging setup utilities.
"""

import logging
import logging.handlers
import os
from pathlib import Path
from typing import Optional


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    max_size: str = "10MB",
    backup_count: int = 5,
    format_string: Optional[str] = None
) -> logging.Logger:
    """
    Set up logging configuration for the application.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (optional)
        max_size: Maximum log file size before rotation
        backup_count: Number of backup files to keep
        format_string: Custom format string (optional)
    
    Returns:
        Configured logger instance
    """
    # Get log level from environment or parameter
    log_level = os.getenv('LOG_LEVEL', level).upper()
    
    # Convert string level to logging constant
    numeric_level = getattr(logging, log_level, logging.INFO)
    
    # Default format string
    if format_string is None:
        format_string = (
            '%(asctime)s - %(name)s - %(levelname)s - '
            '%(funcName)s:%(lineno)d - %(message)s'
        )
    
    # Create formatter
    formatter = logging.Formatter(format_string)
    
    # Get root logger
    logger = logging.getLogger()
    logger.setLevel(numeric_level)
    
    # Clear any existing handlers
    logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler (if specified)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Parse max_size
        max_bytes = _parse_size(max_size)
        
        # Rotating file handler
        file_handler = logging.handlers.RotatingFileHandler(
            log_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    # Log initial message
    logger.info(f"Logging initialized - Level: {log_level}")
    if log_file:
        logger.info(f"Log file: {log_file}")
    
    return logger


def _parse_size(size_str: str) -> int:
    """
    Parse size string like '10MB' into bytes.
    
    Args:
        size_str: Size string (e.g., '10MB', '1GB', '500KB')
    
    Returns:
        Size in bytes
    """
    size_str = size_str.upper().strip()
    
    if size_str.endswith('KB'):
        return int(size_str[:-2]) * 1024
    elif size_str.endswith('MB'):
        return int(size_str[:-2]) * 1024 * 1024
    elif size_str.endswith('GB'):
        return int(size_str[:-2]) * 1024 * 1024 * 1024
    elif size_str.isdigit():
        return int(size_str)
    else:
        # Default to 10MB if can't parse
        return 10 * 1024 * 1024


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the specified name.
    
    Args:
        name: Logger name (usually __name__)
    
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


def set_log_level(level: str):
    """
    Set the log level for all loggers.
    
    Args:
        level: Log level string
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    for handler in root_logger.handlers:
        handler.setLevel(numeric_level)


def add_file_handler(
    log_file: str,
    level: str = "INFO",
    max_size: str = "10MB",
    backup_count: int = 5
):
    """
    Add a file handler to the root logger.
    
    Args:
        log_file: Path to log file
        level: Log level for this handler
        max_size: Maximum file size before rotation
        backup_count: Number of backup files to keep
    """
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    max_bytes = _parse_size(max_size)
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - '
        '%(funcName)s:%(lineno)d - %(message)s'
    )
    
    file_handler = logging.handlers.RotatingFileHandler(
        log_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(formatter)
    
    logging.getLogger().addHandler(file_handler)
