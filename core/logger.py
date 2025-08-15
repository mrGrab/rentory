import logging

LOG_LEVELS = {
    "critical": logging.CRITICAL,
    "error": logging.ERROR,
    "warning": logging.WARNING,
    "info": logging.INFO,
    "debug": logging.DEBUG,
    "trace": logging.DEBUG,
}

# Custom Logging Configuration
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "()": "uvicorn.logging.DefaultFormatter",
            "fmt": "%(levelprefix)s %(funcName)s - %(message)s",
            "use_colors": None,
        },
        "access": {
            "()":
                "uvicorn.logging.AccessFormatter",
            "fmt":
                '%(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s',  # noqa: E501
        },
        "journal": {
            "()": "logging.Formatter",
            "fmt": "%(message)s",
        },
    },
    "handlers": {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
        },
        "access": {
            "formatter": "access",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
        "journal": {
            "class": "systemd.journal.JournalHandler",
            "formatter": "journal",
            "SYSLOG_IDENTIFIER": "Rentory",
        },
    },
    "loggers": {
        "uvicorn": {
            "handlers": ["default", "journal"],
            "level": "INFO",
            "propagate": False
        },
        "uvicorn.error": {
            "level": "INFO"
        },
        "uvicorn.access": {
            "handlers": ["access"],
            "level": "INFO",
            "propagate": False
        },
    },
}

logger = logging.getLogger("uvicorn")
