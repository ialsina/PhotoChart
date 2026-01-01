# pylint: disable=W0401,W0614
"""
Base settings module - imports from production (most restrictive).

This module provides a common import point for other environments.
All base settings are defined in production.py.
"""
from .production import *
