"""
Logging configuration for the Bundestag Protocol Extractor.

This module provides standardized logging setup with console and file outputs,
along with colorized formatting to improve readability and debugging.
"""
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Union, List


class ColoredFormatter(logging.Formatter):
    """Custom formatter that adds colors to log output in the console."""

    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',  # cyan
        'INFO': '\033[32m',  # green
        'WARNING': '\033[33m',  # yellow
        'ERROR': '\033[31m',  # red
        'CRITICAL': '\033[41m\033[37m',  # white on red background
        'RESET': '\033[0m'  # reset to default
    }

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors for console output."""
        # Check if the output stream supports colors (e.g., terminal)
        color_supported = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
        
        # Get the original formatted message
        formatted_message = super().format(record)
        
        if color_supported:
            # Add color codes only if the output stream supports them
            level_name = record.levelname
            if level_name in self.COLORS:
                return f"{self.COLORS[level_name]}{formatted_message}{self.COLORS['RESET']}"
        
        return formatted_message


def setup_logging(
    log_file: Optional[Union[str, Path]] = None,
    log_level: int = logging.INFO,
    log_format: str = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    date_format: str = "%Y-%m-%d %H:%M:%S",
    console_level: Optional[int] = None,
    module_levels: Optional[dict] = None,
    create_log_dir: bool = True
) -> logging.Logger:
    """
    Set up logging configuration with file and console handlers.
    
    Args:
        log_file: Path to log file (default: logs/bundestag_extractor_{timestamp}.log)
        log_level: Default logging level for all handlers
        log_format: Format string for log messages
        date_format: Format string for timestamps
        console_level: Optional separate level for console output (defaults to log_level)
        module_levels: Optional dict of logger name to log level for specific modules
        create_log_dir: Whether to create log directory if it doesn't exist
        
    Returns:
        Root logger instance configured with handlers
    """
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Capture all logs, handlers will filter
    
    # Clear any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Use provided console level or fall back to log_level
    if console_level is None:
        console_level = log_level
    
    # Set up console handler with colored output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    colored_formatter = ColoredFormatter(log_format, datefmt=date_format)
    console_handler.setFormatter(colored_formatter)
    root_logger.addHandler(console_handler)
    
    # Set up file handler if log_file is provided or use default
    if log_file is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_dir = Path("logs")
        if create_log_dir:
            log_dir.mkdir(exist_ok=True, parents=True)
        log_file = log_dir / f"bundestag_extractor_{timestamp}.log"
    else:
        log_file = Path(log_file)
        if create_log_dir:
            log_file.parent.mkdir(exist_ok=True, parents=True)
    
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(log_level)
    file_formatter = logging.Formatter(log_format, datefmt=date_format)
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    
    # Set specific log levels for modules if provided
    if module_levels:
        for module_name, level in module_levels.items():
            module_logger = logging.getLogger(module_name)
            module_logger.setLevel(level)
    
    # Create logger for this module
    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized. Log file: {log_file}")
    
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for a specific module.
    
    Args:
        name: Logger name, typically __name__ of the calling module
        
    Returns:
        Logger instance with appropriate namespace
    """
    return logging.getLogger(name)


# Pre-defined logging configurations
def get_production_logger(log_file: Optional[Union[str, Path]] = None) -> logging.Logger:
    """
    Configure logging for production usage with INFO level to console and file.
    
    Args:
        log_file: Optional path to log file
        
    Returns:
        Configured root logger
    """
    module_levels = {
        "bundestag_protocol_extractor.api.client": logging.WARNING,
        "requests": logging.WARNING,
        "urllib3": logging.WARNING,
    }
    return setup_logging(
        log_file=log_file,
        log_level=logging.INFO,
        console_level=logging.INFO,
        module_levels=module_levels
    )


def get_debug_logger(log_file: Optional[Union[str, Path]] = None) -> logging.Logger:
    """
    Configure logging for debugging with DEBUG level to console and file.
    
    Args:
        log_file: Optional path to log file
        
    Returns:
        Configured root logger
    """
    return setup_logging(
        log_file=log_file,
        log_level=logging.DEBUG,
        console_level=logging.DEBUG
    )


def get_verbose_logger(log_file: Optional[Union[str, Path]] = None) -> logging.Logger:
    """
    Configure logging for verbose output with DEBUG level to file
    but INFO level to console to avoid overwhelming output.
    
    Args:
        log_file: Optional path to log file
        
    Returns:
        Configured root logger
    """
    return setup_logging(
        log_file=log_file,
        log_level=logging.DEBUG,
        console_level=logging.INFO
    )


def get_quiet_logger(log_file: Optional[Union[str, Path]] = None) -> logging.Logger:
    """
    Configure logging for quiet operation with WARNING level to console,
    but INFO level to file to maintain decent logs.
    
    Args:
        log_file: Optional path to log file
        
    Returns:
        Configured root logger
    """
    return setup_logging(
        log_file=log_file,
        log_level=logging.INFO,
        console_level=logging.WARNING
    )