"""
Logger configuration for the Spotify Album Downloader and Burner.
Provides standardized logging setup across the application.
"""

import logging
import logging.handlers
import os
import sys
from pathlib import Path

# Define log levels
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

def setup_logger(
    name="spotify_burner",
    log_file="spotify_burner.log", 
    level="INFO",
    log_format=None,
    rotate=True
):
    """
    Configure and return a logger instance.
    
    Args:
        name: Logger name
        log_file: Path to the log file
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Custom log format string
        rotate: Whether to use a rotating file handler
        
    Returns:
        logging.Logger: Configured logger
    """
    # Get log level from environment or use default
    level = os.environ.get("LOG_LEVEL", level).upper()
    log_level = LOG_LEVELS.get(level, logging.INFO)
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    
    # Clear existing handlers to avoid duplicates
    if logger.hasHandlers():
        logger.handlers.clear()
    
    # Define log format
    if not log_format:
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    formatter = logging.Formatter(log_format)
    
    # Create directory for log file if it doesn't exist
    log_path = Path(log_file)
    if log_path.parent and not log_path.parent.exists():
        log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Add a file handler
    if rotate:
        # Use rotating file handler for production (limits file size)
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=10*1024*1024, backupCount=5
        )
    else:
        # Use regular file handler
        file_handler = logging.FileHandler(log_file)
        
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger

# Default logger instance
logger = setup_logger()