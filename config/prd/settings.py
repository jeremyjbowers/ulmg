import os

from config.dev.settings import *

DEBUG = False

WSGI_APPLICATION = 'config.prd.app.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': os.environ.get('ULMG_DB_NAME', 'ulmg'),
        'USER': os.environ.get('ULMG_DB_USER', 'ubuntu'),
        'PASSWORD': os.environ.get('ULMG_DB_PASS', ''),
        'HOST': os.environ.get('ULMG_DB_HOST', ''),
    }
}

STATIC_ROOT = '/var/www/theulmg.com/static'
STATIC_URL = '/static/'

ALLOWED_HOSTS = ['*']