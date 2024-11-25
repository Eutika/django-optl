import logging
import sys

def configure_logging():
    """
    Comprehensive logging configuration
    """
    # Basic logging configuration
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

    # Configure specific loggers
    loggers = [
        'django',
        'django.request',
        'django.db.backends',
        'notes_app',
        'opentelemetry',
    ]

    for logger_name in loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.INFO)

    return logging.getLogger(__name__)

# Create a logger
logger = configure_logging()
