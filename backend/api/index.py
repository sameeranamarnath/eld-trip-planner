"""Serverless entrypoint for Vercel's Python runtime.

Vercel imports this module and looks for a WSGI callable named ``app`` or
``application``.  The project root (``backend/``) is added to ``sys.path`` so
``config`` and ``eld`` resolve regardless of how the bundle is laid out.
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from config.wsgi import application  # noqa: E402  (import after env setup)

app = application

__all__ = ["app", "application"]
