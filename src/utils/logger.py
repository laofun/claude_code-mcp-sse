"""
Logging configuration for the Enhanced MCP Server
"""

import logging
import sys
import os
from datetime import datetime
from typing import Optional

import structlog
from structlog.stdlib import LoggerFactory


def setup_logger(name: str, log_level: Optional[str] = None) -> logging.Logger:
    """
    Set up a structured logger with proper formatting
    
    Args:
        name: Logger name (usually __name__)
        log_level: Override log level (defaults to LOG_LEVEL env var)
    
    Returns:
        Configured logger instance
    """
    # Get log level from environment or parameter
    if log_level is None:
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.CallsiteParameterAdder(
                parameters=[
                    structlog.processors.CallsiteParameter.FILENAME,
                    structlog.processors.CallsiteParameter.LINENO,
                ]
            ),
            structlog.dev.ConsoleRenderer() if os.getenv("PYTHON_ENV") == "development" 
            else structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Get the logger
    logger = structlog.get_logger(name)
    
    # Set log level
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level)
    )
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get an existing logger or create a new one
    
    Args:
        name: Logger name
        
    Returns:
        Logger instance
    """
    return structlog.get_logger(name)


class LogContext:
    """Context manager for adding temporary log context"""
    
    def __init__(self, logger: logging.Logger, **kwargs):
        self.logger = logger
        self.context = kwargs
        self.original_context = None
    
    def __enter__(self):
        self.original_context = self.logger.context
        self.logger = self.logger.bind(**self.context)
        return self.logger
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore original context
        if self.original_context:
            self.logger.context = self.original_context