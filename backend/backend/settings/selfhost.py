# pylint: disable=W0401,W0614
from .production import *
from decouple import config, UndefinedValueError

DEBUG = config("DEBUG", default=False, cast=bool)

# ALLOWED_HOSTS: derive from DOMAIN if not explicitly set
# DOMAIN can be a single domain or comma-separated list
# Default to localhost for selfhost if nothing is set
domain = config("DOMAIN", default="")
if domain:
    ALLOWED_HOSTS = [d.strip() for d in domain.split(",") if d.strip()]
else:
    # Fallback to explicit ALLOWED_HOSTS, or default to localhost for selfhost
    explicit_hosts = config(
        "ALLOWED_HOSTS",
        default="",
        cast=lambda v: [s.strip() for s in v.split(",") if s.strip()],
    )
    ALLOWED_HOSTS = explicit_hosts if explicit_hosts else ["localhost", "127.0.0.1"]

# Database - determine engine based on whether DB credentials are provided
# If DB_USER is explicitly set, use MySQL; otherwise use SQLite
# Check if DB_USER is set in config (without default to detect if it exists)
try:
    db_user = config("DB_USER")
    # MySQL configuration (if DB_USER is explicitly set)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": config("DB_NAME", default="photochart"),
            "USER": db_user,
            "PASSWORD": config("DB_PASSWORD", default=""),
            "HOST": config("DB_HOST", default="localhost"),
            "PORT": config("DB_PORT", default="3306"),
        }
    }
except UndefinedValueError:
    # SQLite configuration (if DB_USER is not set)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": config("DB_NAME", default=str(BASE_DIR / "db.sqlite3")),
        }
    }

# CORS settings for selfhost - always derive from ALLOWED_HOSTS
CORS_ALLOWED_ORIGINS = (
    [f"https://{host}" for host in ALLOWED_HOSTS]
    + [f"http://{host}" for host in ALLOWED_HOSTS]
    if ALLOWED_HOSTS
    else []
)

# Also allow localhost origins for selfhosting scenarios
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^http://localhost:\d+$",
    r"^http://127\.0\.0\.1:\d+$",
    r"^https://localhost:\d+$",
    r"^https://127\.0\.0\.1:\d+$",
]

# Allow all common HTTP methods
CORS_ALLOW_METHODS = [
    "DELETE",
    "GET",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
]

# Allow more headers than production
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
]

CORS_ALLOW_CREDENTIALS = True

# Expose headers that the frontend might need to read
CORS_EXPOSE_HEADERS = [
    "content-type",
    "x-csrftoken",
]

CSRF_TRUSTED_ORIGINS = (
    [cors_origin.replace("http://", "https://") for cors_origin in CORS_ALLOWED_ORIGINS]
    + CORS_ALLOWED_ORIGINS
    + [
        "http://localhost",
        "https://localhost",
        "http://127.0.0.1",
        "https://127.0.0.1",
    ]
)

# HTTPS settings - can be disabled for selfhosting
SESSION_COOKIE_SECURE = config("SSL_CERTIFICATE", default=False, cast=bool)
CSRF_COOKIE_SECURE = config("SSL_CERTIFICATE", default=False, cast=bool)
SECURE_SSL_REDIRECT = config("SSL_CERTIFICATE", default=False, cast=bool)

# HSTS settings - can be disabled for selfhosting
SECURE_HSTS_SECONDS = (
    0 if not config("SSL_CERTIFICATE", default=False, cast=bool) else 31536000
)
SECURE_HSTS_PRELOAD = config("SSL_CERTIFICATE", default=False, cast=bool)
SECURE_HSTS_INCLUDE_SUBDOMAINS = config("SSL_CERTIFICATE", default=False, cast=bool)

# Logging
if config("LOGGING", default=True, cast=bool):
    LOGGING = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "verbose": {
                "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
                "style": "{",
            },
        },
        "handlers": {
            "console": {
                "level": config("LOG_LEVEL", default="INFO"),
                "class": "logging.StreamHandler",
                "formatter": "verbose",
            },
            "file": {
                "level": config("LOG_LEVEL", default="INFO"),
                "class": "logging.handlers.RotatingFileHandler",
                "filename": config(
                    "LOG_FILE", default=BASE_DIR / "logs" / "django.log"
                ),
                "maxBytes": 1024 * 1024 * 5,  # 5 MB
                "backupCount": 5,
                "formatter": "verbose",
                "delay": True,  # Don't create the file until it's needed
            },
        },
        "loggers": {
            "django": {
                "handlers": ["file", "console"],
                "level": config("LOG_LEVEL", default="INFO"),
                "propagate": True,
            },
        },
    }
