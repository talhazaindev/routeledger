"""
WSGI config for config project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()

# Ensure schema exists for ephemeral /tmp SQLite on Vercel cold starts
if os.environ.get("VERCEL") and not os.environ.get("DATABASE_URL"):
    from django.core.management import call_command

    call_command("migrate", interactive=False, run_syncdb=True, verbosity=0)
