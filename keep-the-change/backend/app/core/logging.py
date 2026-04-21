"""
Logging configuration for KEEPTHECHANGE.com
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.core.config import settings


def setup_logging():
    """Setup logging configuration"""
    
    # Create logs directory if it doesn't exist
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Configure root logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
    console_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)
    
    # File handler for general logs
    file_handler = RotatingFileHandler(
        logs_dir / "app.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(logging.INFO)
    file_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)
    
    # File handler for error logs
    error_handler = RotatingFileHandler(
        logs_dir / "error.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(file_format)
    logger.addHandler(error_handler)
    
    # File handler for audit logs
    audit_handler = RotatingFileHandler(
        logs_dir / "audit.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    audit_handler.setLevel(logging.INFO)
    audit_format = logging.Formatter(
        '%(asctime)s - AUDIT - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    audit_handler.setFormatter(audit_format)
    logger.addHandler(audit_handler)
    
    # Set levels for specific loggers
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING if settings.DEBUG else logging.ERROR)
    
    # Log startup message
    logger.info(f"Logging configured for {settings.APP_NAME}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Debug mode: {settings.DEBUG}")
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """Get logger with specific name"""
    return logging.getLogger(name)


def log_audit_event(event_type: str, user_id: str = None, details: dict = None):
    """Log audit event"""
    logger = logging.getLogger("audit")
    
    log_message = f"EVENT={event_type}"
    
    if user_id:
        log_message += f" USER={user_id}"
    
    if details:
        import json
        log_message += f" DETAILS={json.dumps(details)}"
    
    logger.info(log_message)


def log_security_event(event_type: str, severity: str, details: dict):
    """Log security event"""
    logger = logging.getLogger("security")
    
    log_message = f"SECURITY - {severity.upper()} - {event_type}"
    
    import json
    log_message += f" - {json.dumps(details)}"
    
    if severity == "critical":
        logger.critical(log_message)
    elif severity == "error":
        logger.error(log_message)
    elif severity == "warning":
        logger.warning(log_message)
    else:
        logger.info(log_message)


def log_performance_metric(metric_name: str, value: float, tags: dict = None):
    """Log performance metric"""
    logger = logging.getLogger("performance")
    
    log_message = f"METRIC={metric_name} VALUE={value}"
    
    if tags:
        import json
        log_message += f" TAGS={json.dumps(tags)}"
    
    logger.info(log_message)


def log_business_event(event_type: str, user_id: str = None, transaction_id: str = None, details: dict = None):
    """Log business event (purchases, investments, etc.)"""
    logger = logging.getLogger("business")
    
    log_message = f"BUSINESS - {event_type}"
    
    if user_id:
        log_message += f" - USER={user_id}"
    
    if transaction_id:
        log_message += f" - TX={transaction_id}"
    
    if details:
        import json
        # Mask sensitive data
        safe_details = details.copy()
        for key in ["password", "token", "secret", "key", "card_number", "cvv"]:
            if key in safe_details:
                safe_details[key] = "[MASKED]"
        
        log_message += f" - {json.dumps(safe_details)}"
    
    logger.info(log_message)


# Export
__all__ = [
    "setup_logging",
    "get_logger",
    "log_audit_event",
    "log_security_event",
    "log_performance_metric",
    "log_business_event"
]