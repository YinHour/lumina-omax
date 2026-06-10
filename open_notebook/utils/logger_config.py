import os
import sys
from pathlib import Path

from loguru import logger

# Import content_core first because it calls logger.remove() in its __init__
try:
    import content_core.logging
except ImportError:
    pass

_logging_configured = False

def setup_logging():
    global _logging_configured
    if _logging_configured:
        return
        
    # Remove all existing handlers, including content_core's
    logger.remove()
    
    log_level = os.environ.get("LOG_LEVEL", "DEBUG")
    service_name = os.environ.get("LOG_SERVICE", "open_notebook")
    log_filename = f"{service_name}.log"
    
    # Add console handler
    logger.add(
        sys.stderr, 
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )
    
    # Add file handler
    try:
        # Find project root (assuming this file is in open_notebook/utils/)
        project_root = Path(__file__).parent.parent.parent
        log_dir = project_root / "logs"
        log_dir.mkdir(exist_ok=True)
        
        logger.add(
            str(log_dir / log_filename),
            rotation="10 MB",
            retention="30 days",
            level=log_level,
            enqueue=True,  # Important for multiprocess/async safety
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"
        )
        logger.info(f"File logging configured: {log_dir / log_filename}")
    except Exception as e:
        logger.error(f"Failed to configure file logging: {e}")
        
    _logging_configured = True
