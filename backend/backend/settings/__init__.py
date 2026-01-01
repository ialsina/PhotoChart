"""
Django settings module selector.

This module selects the appropriate settings based on the DJANGO_ENV environment variable.
Valid values are: development, production, selfhost
Defaults to development if not set.
"""

import os
from decouple import config

# Get the environment from environment variable or config
ENV = config("DJANGO_ENV", default="development").lower()

if ENV == "production":
    from .production import *  # pylint: disable=W0401,W0614
elif ENV == "selfhost":
    from .selfhost import *  # pylint: disable=W0401,W0614
else:
    # Default to development
    from .development import *  # pylint: disable=W0401,W0614
