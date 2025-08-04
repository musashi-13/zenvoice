import logging
import os
import sys

def setup_logger(module_name: str, service_env_var: str):
    """
    Sets up a logger with configurable levels and formats based on environment variables.

    Args:
        module_name: The name of the logger (e.g., '__name__').
        service_env_var: The specific environment variable for this service (e.g., 'EMAIL_MONITOR_LOG').
    """
    # Determine the log mode
    log_mode = os.getenv(service_env_var) or os.getenv("LOG") or "PROD"
    log_mode = log_mode.upper()

    # Get the root logger
    logger = logging.getLogger(module_name)
    
    # Prevent duplicate handlers if already configured
    if logger.hasHandlers():
        logger.handlers.clear()

    # Set logging level
    if log_mode == "DEV":
        logger.setLevel(logging.DEBUG)
        # Define DEV format with file, line number, and function name
        formatter = logging.Formatter(
            '%(levelname)s - %(filename)s:%(lineno)d - %(funcName)s() - %(message)s'
        )
    else: # PROD mode
        logger.setLevel(logging.INFO)
        # Define PROD format with just the filename
        formatter = logging.Formatter('%(levelname)s - %(filename)s - %(message)s')

    # Create handler and set formatter
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    logger.debug(f"Logger for '{module_name}' initialized in {log_mode} mode.")
    return logger

