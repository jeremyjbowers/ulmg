from django.core.management.utils import get_random_secret_key
from pathlib import Path
import os
import sys
import dj_database_url

from config.dev.settings import *

DEBUG = os.getenv("DEBUG", "False") == "True"

WSGI_APPLICATION = "config.prd.app.application"

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", get_random_secret_key())

DEBUG = os.getenv("DEBUG", "False") == "True"

ALLOWED_HOSTS = ['*']

DEVELOPMENT_MODE = os.getenv("DEVELOPMENT_MODE", "False") == "True"

DATABASE_URL = os.environ.get("DATABASE_URL", None)

DATABASES = {
    "default": dj_database_url.parse(DATABASE_URL),
}

STATIC_ROOT = "/workspace/config/staticfiles/"
STATIC_URL = "/static/"