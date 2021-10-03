import os

from config.prd.settings import *

WSGI_APPLICATION = "config.dockerprod.app.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql_psycopg2",
        "NAME": os.environ.get("DB_NAME", "ulmg"),
        "USER": os.environ.get("DB_USER", "ulmg"),
        "PASSWORD": os.environ.get("DB_PASSWORD", "ulmg"),
        "HOST": os.environ.get("DB_HOST", "127.0.0.1"),
    }
}

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR + "/staticfiles"
