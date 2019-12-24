import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', ')(hv#e)wqd-9pwuvd94wq5-snmz+@m(&-g5e74&zg)+geh-xqe+++++sadjklfhlkh7')

DEBUG = True

ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.postgres',
    'django.contrib.humanize',
    'django.contrib.staticfiles',
    'ulmg',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'ulmg.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': ['ulmg/templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.request',
            ],
            'libraries':{
                'ulmg_tags': 'ulmg.templatetags.ulmg_tags',
            }
        },
    },
]

WSGI_APPLICATION = 'config.dev.app.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': os.environ.get('DB_NAME', 'ulmg'),
        'USER': os.environ.get('DB_USER', None),
        'PASSWORD': os.environ.get('DB_PASSWORD', None),
        'HOST': os.environ.get('DB_HOST', None),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

STATIC_URL = '/static/'

"""
Section for site-specific settings, e.g., controlling tabs, current draft year, etc.
"""
TEAM_PROTECT_TAB = True
TEAM_ROSTER_TAB = False
TEAM_SEASON_HALF = "1h"
CURRENT_SEASON = 2020
CURRENT_SEASON_TYPE = "offseason"
CSV_COLUMNS = [
    'last_name', 
    'first_name', 
    'fg_id',
    'level', 
    'is_carded', 
    'ls_gs',
    'ls_g',
    'ls_plate_appearances', 
    'defense',
    'is_reserve',
    'is_1h_p',
    'is_1h_c',
    'is_1h_pos',
    'is_mlb_roster',
    'is_aaa_roster',
    'team__abbreviation'
]
DRAFTS = [
    {"title": "2019 Offseason Open", "url": "/draft/2019/offseason/open/"},
    {"title": "2019 Offseason AA", "url": "/draft/2019/offseason/aa/"},
    {"title": "2019 Midseason Open", "url": "/draft/2019/midseason/open/"},
    {"title": "2019 Midseason AA", "url": "/draft/2019/midseason/aa/"},
    {"title": "2018 Offseason Open", "url": "/draft/2018/offseason/open/"},
    {"title": "2018 Offseason AA", "url": "/draft/2018/offseason/aa/"},
    {"title": "2018 Midseason Open", "url": "/draft/2018/midseason/open/"},
    {"title": "2018 Midseason AA", "url": "/draft/2018/midseason/aa/"},
]