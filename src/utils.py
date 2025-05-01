"""
Utility functions for the Twitter automation pipeline.

This module provides utility functions for logging, retry logic, etc.
"""
import logging
import time
import functools
import os
from pathlib import Path


def setup_logging(log_file=None, log_level=None):
    """
    Set up logging configuration.
    
    Args:
        log_file (str, optional): Path to the log file.
        log_level (str, optional): Logging level (DEBUG, INFO, etc.).
            Defaults to INFO.
    
    Returns:
        logging.Logger: Configured logger instance.
    """
    # Determine project root
    project_root = Path(__file__).resolve().parent.parent
    
    # Set defaults if not provided
    if log_file is None:
        log_file = Path(__file__).resolve().parent / 'log' / 'pipeline.log'
    else:
        log_file = Path(log_file)
        
    # Create log directory if it doesn't exist
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Set default log level if not provided or invalid
    if log_level is None:
        log_level = os.getenv('LOG_LEVEL', 'INFO')
        
    # Convert string level to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Configure logging
    logging.basicConfig(
        level=numeric_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger('twitter_automation')


def retry(max_tries=3, delay=1, backoff=2, exceptions=(Exception,), logger=None):
    """
    Retry decorator with exponential backoff.
    
    Args:
        max_tries (int): Maximum number of retry attempts.
        delay (int): Initial delay between retries in seconds.
        backoff (int): Backoff multiplier.
        exceptions (tuple): Exceptions to catch and retry on.
        logger (logging.Logger, optional): Logger to use for logging retries.
    
    Returns:
        function: Decorated function with retry logic.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            mtries, mdelay = max_tries, delay
            
            # Use default logger if not provided
            nonlocal logger
            if logger is None:
                logger = logging.getLogger('twitter_automation')
                
            while mtries > 0:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    mtries -= 1
                    if mtries == 0:
                        logger.error(f"{func.__name__} failed after {max_tries} tries: {str(e)}")
                        raise
                    
                    logger.warning(f"{func.__name__} failed, retrying in {mdelay}s... ({max_tries - mtries}/{max_tries})")
                    time.sleep(mdelay)
                    mdelay *= backoff
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


def create_file_if_not_exists(file_path):
    """
    Create a file if it doesn't exist.
    
    Args:
        file_path (str or Path): Path to the file to create.
    """
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    if not file_path.exists():
        file_path.touch()


if __name__ == "__main__":
    # Test logging setup
    logger = setup_logging()
    logger.debug("Debug message")
    logger.info("Info message")
    logger.warning("Warning message")
    logger.error("Error message") 