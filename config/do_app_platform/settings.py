from django.core.management.utils import get_random_secret_key
from pathlib import Path
import os
import sys
import dj_database_url

from config.dev.settings import *

WSGI_APPLICATION = "config.do_app_platform.app.application"

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "8b78cd4a-85a1-4d48-b419-f2b4b62e2bc3")

DEBUG = True

ALLOWED_HOSTS = ["*"]

DEVELOPMENT_MODE = True

DATABASE_URL = os.environ.get("DATABASE_URL", None)

DATABASES = {
    "default": dj_database_url.parse(DATABASE_URL),
}

STATIC_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/{AWS_LOCATION}/"
STATICFILES_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"

INSTALLED_APPS = INSTALLED_APPS + ["storages"]

# Long-lived sessions (6 months), sliding expiration
SESSION_COOKIE_AGE = 60 * 60 * 24 * 180
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# Cookie/security for DO App Platform (served behind HTTPS proxy)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_DOMAIN = os.getenv('SESSION_COOKIE_DOMAIN', None)
