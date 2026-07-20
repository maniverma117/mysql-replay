"""
Configuration for MySQL Buffer Pool Warmer
"""

import os


# -----------------------------------------------------------------------------
# Loki Configuration
# -----------------------------------------------------------------------------

LOKI_URL = os.getenv(
    "LOKI_URL",
    "http://52.38.38.220:3100"
)

# Promtail label
LOKI_QUERY = os.getenv(
    "LOKI_QUERY",
    '{job="mysql-general"}'
)

# Poll Loki every 5 minutes
POLL_INTERVAL = int(
    os.getenv("POLL_INTERVAL", "300")
)

# Maximum log entries fetched per request
LOKI_LIMIT = int(
    os.getenv("LOKI_LIMIT", "5000")
)

# -----------------------------------------------------------------------------
# MySQL Configuration
# -----------------------------------------------------------------------------

MYSQL_HOST = os.getenv(
    "MYSQL_HOST",
    ""
)

MYSQL_PORT = int(
    os.getenv(
        "MYSQL_PORT",
        "3306"
    )
)

MYSQL_DATABASE = os.getenv(
    "MYSQL_DATABASE",
    ""
)

MYSQL_USER = os.getenv(
    "MYSQL_USER",
    ""
)

MYSQL_PASSWORD = os.getenv(
    "MYSQL_PASSWORD",
    ""
)

MYSQL_CONNECT_TIMEOUT = int(
    os.getenv(
        "MYSQL_CONNECT_TIMEOUT",
        "20"
    )
)

MYSQL_READ_TIMEOUT = int(
    os.getenv(
        "MYSQL_READ_TIMEOUT",
        "600"
    )
)

MYSQL_WRITE_TIMEOUT = int(
    os.getenv(
        "MYSQL_WRITE_TIMEOUT",
        "600"
    )
)

MYSQL_QUERY_MAX_SECONDS = int(
    os.getenv(
        "MYSQL_QUERY_MAX_SECONDS",
        "60"
    )
)

LOKI_LOOKBACK_HOURS = int(
    os.getenv(
        "LOKI_LOOKBACK_HOURS",
        "3"
    )
)

# -----------------------------------------------------------------------------
# Replay Workers
# -----------------------------------------------------------------------------

WORKERS = int(
    os.getenv(
        "WORKERS",
        "10"
    )
)

# -----------------------------------------------------------------------------
# Flask
# -----------------------------------------------------------------------------

FLASK_HOST = os.getenv(
    "FLASK_HOST",
    "0.0.0.0"
)

FLASK_PORT = int(
    os.getenv(
        "FLASK_PORT",
        "5000"
    )
)

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------

LOG_LEVEL = os.getenv(
    "LOG_LEVEL",
    "INFO"
)

LOG_FILE = os.getenv(
    "LOG_FILE",
    "/logs/replay.log"
)

# -----------------------------------------------------------------------------
# Replay Queue
# -----------------------------------------------------------------------------

QUEUE_SIZE_WARNING = int(
    os.getenv(
        "QUEUE_SIZE_WARNING",
        "50000"
    )
)

# -----------------------------------------------------------------------------
# Application
# -----------------------------------------------------------------------------

APP_NAME = "mysql-bufferpool-warmer"

VERSION = "1.0.0"