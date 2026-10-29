"""
WSGI config for the config project (industrial_safety_invoicing_webapp).
"""

import os

from django.conf import settings
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

_django_app = get_wsgi_application()


def application(environ, start_response):
    """
    Guard against IIS/wfastcgi not stripping the app-alias prefix from
    PATH_INFO (§5.2). core.middleware.ScriptNameFromHeaderMiddleware in
    this project's MIDDLEWARE only fires on an nginx-forwarded
    HTTP_SCRIPT_NAME header, which doesn't exist under a native IIS
    Application (Chapter B/C) — this guard is what actually protects
    this deployment from the doubled-prefix failure in Appendix C.
    """
    prefix = settings.FORCE_SCRIPT_NAME
    if prefix:
        path_info = environ.get("PATH_INFO", "")
        if path_info == prefix or path_info.startswith(prefix + "/"):
            environ["PATH_INFO"] = path_info[len(prefix):] or "/"

    return _django_app(environ, start_response)