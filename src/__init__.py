"""
Web package for PUML Comparator

Expose small helpers without heavy imports during package import
"""

from importlib.metadata import version as _get_version

__all__ = ["__version__"]

try:
    __version__ = _get_version("ocr-plantuml-web")
except Exception:
    __version__ = "0.1.0"

# we don't import web.main or uvicorn at package import time to keep lightweight
