"""WSGI entrypoint (used by Render / Gunicorn / Vercel's Python runtime)."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()
