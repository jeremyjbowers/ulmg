import os

from config.dev.settings import *

DEBUG = True

WSGI_APPLICATION = "config.prd.app.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql_psycopg2",
        "NAME": os.environ.get("ULMG_DB_NAME", "ulmg"),
        "USER": os.environ.get("ULMG_DB_USER", "ubuntu"),
        "PASSWORD": os.environ.get("ULMG_DB_PASS", ""),
        "HOST": os.environ.get("ULMG_DB_HOST", ""),
    }
}

STATIC_ROOT = "/var/www/theulmg.com/static"
STATIC_URL = "/static/"

# Cookie/security hardening for production
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
# Optionally scope across subdomains if you use multiple hosts
SESSION_COOKIE_DOMAIN = os.getenv('SESSION_COOKIE_DOMAIN', None)
# Long-lived sessions (6 months), sliding expiration
SESSION_COOKIE_AGE = 60 * 60 * 24 * 180
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
