"""
Centralized logging configuration for the EDR Backend.
This module provides a structured, flexible logging system with different log levels,
formatters, and handlers for various components of the application.
"""

import os
import logging
import logging.handlers
import json
from datetime import datetime
from pathlib import Path
from app.config.config import config

# Set up logging directory
log_dir = Path(config.LOG_DIR)
log_dir.mkdir(parents=True, exist_ok=True)

# Define log formatters
STANDARD_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
DETAILED_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(threadName)s - %(filename)s:%(lineno)d - %(message)s'
JSON_FORMAT = '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "name": "%(name)s", "message": "%(message)s", "file": "%(filename)s", "line": %(lineno)d, "thread": "%(threadName)s"}'

# Custom JSON formatter
class JsonFormatter(logging.Formatter):
    """Format logs as JSON objects for better parsing and analysis."""
    
    def format(self, record):
        log_record = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
            "file": record.filename,
            "line": record.lineno,
            "thread": record.threadName
        }
        
        # Add exception info if available
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
            
        # Add any custom attributes added to the LogRecord
        for key, value in record.__dict__.items():
            if key not in ["args", "asctime", "created", "exc_info", "exc_text", 
                          "filename", "funcName", "id", "levelname", "levelno", 
                          "lineno", "module", "msecs", "message", "msg", "name", 
                          "pathname", "process", "processName", "relativeCreated", 
                          "stack_info", "thread", "threadName"]:
                log_record[key] = value
                
        return json.dumps(log_record)

# Configure formatters
standard_formatter = logging.Formatter(STANDARD_FORMAT)
detailed_formatter = logging.Formatter(DETAILED_FORMAT)
json_formatter = JsonFormatter()

# Define log component configuration
COMPONENT_CONFIGS = {
    'app': {
        'level': logging.INFO,
        'format': detailed_formatter,
        'description': 'Main application logs'
    },
    'api': {
        'level': logging.INFO,
        'format': detailed_formatter,
        'description': 'API endpoint access and operations'
    },
    'grpc': {
        'level': logging.INFO,
        'format': detailed_formatter,
        'description': 'gRPC server interactions with agents'
    },
    'elastalert': {
        'level': logging.INFO,
        'format': detailed_formatter,
        'description': 'ElastAlert rule processing and alerts'
    },
    'security': {
        'level': logging.INFO,
        'format': detailed_formatter,
        'description': 'Security-related events and access attempts'
    },
    'performance': {
        'level': logging.DEBUG,
        'format': json_formatter,
        'description': 'Performance metrics and timing information'
    }
}

# Create console handler for development
def create_console_handler(level=logging.INFO):
    """Create a console handler for development purposes."""
    handler = logging.StreamHandler()
    handler.setLevel(level)
    handler.setFormatter(standard_formatter)
    return handler

# Create component-specific file handler
def create_component_handler(component_name, level=None, formatter=None, max_bytes=10485760, backup_count=5):
    """Create a rotating file handler for a specific component."""
    if level is None:
        level = COMPONENT_CONFIGS.get(component_name, {}).get('level', logging.INFO)
        
    if formatter is None:
        formatter = COMPONENT_CONFIGS.get(component_name, {}).get('format', detailed_formatter)
    
    log_file = log_dir / f"{component_name}.log"
    handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=max_bytes, backupCount=backup_count
    )
    handler.setLevel(level)
    handler.setFormatter(formatter)
    return handler

def setup_logging(include_console=True):
    """Set up the logging system for the entire application.
    
    Args:
        include_console (bool): Whether to include console logging (for development)
    """
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, config.LOG_LEVEL))
    
    # Clear any existing handlers (in case this is called multiple times)
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add console handler if requested
    if include_console and config.DEBUG:
        console_handler = create_console_handler()
        root_logger.addHandler(console_handler)
    
    # Silence Flask/Werkzeug HTTP request logs
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    logging.getLogger('flask').setLevel(logging.ERROR)
    
    # Set up component loggers
    components = {
        'app': logging.getLogger('app'),
        'api': logging.getLogger('app.api'),
        'grpc': logging.getLogger('app.grpc'),
        'elastalert': logging.getLogger('app.elastalert'),
        'security': logging.getLogger('app.security'),
        'performance': logging.getLogger('app.performance')
    }
    
    # Add handlers for specific components
    for name, logger in components.items():
        config_dict = COMPONENT_CONFIGS.get(name, {})
        handler = create_component_handler(
            name, 
            level=config_dict.get('level', logging.INFO),
            formatter=config_dict.get('format', detailed_formatter)
        )
        logger.addHandler(handler)
        logger.propagate = False  # Prevent duplicate logs in parent loggers
    
    # Create special handlers for error logs (across all components)
    error_handler = logging.handlers.RotatingFileHandler(
        log_dir / "error.log", maxBytes=10485760, backupCount=5
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(error_handler)
    
    # Log initialization
    app_logger = logging.getLogger('app')
    app_logger.info(f"Logging initialized with level {config.LOG_LEVEL} in directory {log_dir}")
    
    return components

def get_logger(name):
    """Get a logger with the specified name.
    This is a convenience function to ensure consistent logger naming.
    
    Args:
        name (str): Name of the logger (e.g., 'app.api.routes')
        
    Returns:
        logging.Logger: Configured logger object
    """
    return logging.getLogger(name)

# Context manager for performance logging
class PerformanceLogger:
    """Context manager for logging performance metrics."""
    
    def __init__(self, operation_name, additional_info=None):
        """Initialize the performance logger.
        
        Args:
            operation_name (str): Name of the operation being measured
            additional_info (dict): Additional context information to log
        """
        self.operation_name = operation_name
        self.additional_info = additional_info or {}
        self.logger = logging.getLogger('app.performance')
        self.start_time = None
        
    def __enter__(self):
        """Start the timer when entering the context."""
        self.start_time = datetime.now()
        self.logger.debug(f"Starting operation: {self.operation_name}", 
                         extra={"operation": self.operation_name, "event": "start", **self.additional_info})
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Log the elapsed time when exiting the context."""
        if not self.start_time:
            return
            
        end_time = datetime.now()
        duration_ms = (end_time - self.start_time).total_seconds() * 1000
        
        if exc_type:
            # Log error if an exception occurred
            self.logger.error(
                f"Operation {self.operation_name} failed after {duration_ms:.2f}ms", 
                extra={
                    "operation": self.operation_name,
                    "event": "error",
                    "duration_ms": duration_ms,
                    "error": str(exc_val),
                    **self.additional_info
                }
            )
        else:
            # Log success
            self.logger.debug(
                f"Operation {self.operation_name} completed in {duration_ms:.2f}ms", 
                extra={
                    "operation": self.operation_name,
                    "event": "complete",
                    "duration_ms": duration_ms,
                    **self.additional_info
                }
            ) 