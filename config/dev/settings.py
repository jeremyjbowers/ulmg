import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    ")(hv#e)wqd-9pwuvd94wq5-snmz+@m(&-g5e74&zg)+geh-xqe+++++sadjklfhlkh7",
)

DEBUG = True

ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.postgres",
    "django.contrib.humanize",
    "django.contrib.staticfiles",
    "ulmg",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "ulmg.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": ["ulmg/templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.request",
            ],
            "libraries": {"ulmg_tags": "ulmg.templatetags.ulmg_tags",},
        },
    },
]

WSGI_APPLICATION = "config.dev.app.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql_psycopg2",
        "NAME": os.environ.get("DB_NAME", "ulmg"),
        "USER": os.environ.get("DB_USER", None),
        "PASSWORD": os.environ.get("DB_PASSWORD", None),
        "HOST": os.environ.get("DB_HOST", None),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",},
]

# LOGIN STUFF
LOGIN_REDIRECT_URL = "/my/team/"
LOGIN_URL = "/accounts/login/"
LOGOUT_REDIRECT_URL = "/"

STATIC_URL = "/static/"

# ULMG SPECIFIC SETTINGS
MLB_ROSTER_SIZE = 30

TEAM_PROTECT_TAB = False
TEAM_ROSTER_TAB = True
TEAM_LIVE_TAB = False

TEAM_SEASON_HALF = "1h"
CURRENT_SEASON = 2021
CURRENT_SEASON_TYPE = "offseason"

ROSTER_TEAM_IDS = [
    ("1", "LAA", "Los Angeles Angels"),
    ("2", "BAL", "Baltimore Orioles"),
    ("3", "BOS", "Boston Red Sox"),
    ("4", "CHW", "Chicago White Sox"),
    ("5", "CLE", "Cleveland Indians"),
    ("6", "DET", "Detroit Tigers"),
    ("7", "KCR", "Kansas City Royals"),
    ("8", "MIN", "Minnesota Twins"),
    ("9", "NYY", "New York Yankees"),
    ("10", "OAK", "Oakland Athletics"),
    ("11", "SEA", "Seattle Mariners"),
    ("12", "TBR", "Tampa Bay Rays"),
    ("13", "TEX", "Texas Rangers"),
    ("14", "TOR", "Toronto Blue Jays"),
    ("15", "ARI", "Arizona Diamondbacks"),
    ("16", "ATL", "Atlanta Braves"),
    ("17", "CHC", "Chicago Cubs"),
    ("18", "CIN", "Cincinatti Reds"),
    ("19", "COL", "Colorado Rockies"),
    ("20", "MIA", "Miami Marlins"),
    ("21", "HOU", "Houston Astros"),
    ("22", "LAD", "Los Angeles Dodgers"),
    ("23", "MIL", "Milwaukee Brewers"),
    ("24", "WAS", "Washington Nationals"),
    ("25", "NYM", "New York Mets"),
    ("26", "PHI", "Philadelphia Phillies"),
    ("27", "PIT", "Pittsburgh Pirates"),
    ("28", "STL", "St. Louis Cardinals"),
    ("29", "SDP", "San Diego Padres"),
    ("30", "SFG", "San Francisco Giants"),
]

CSV_COLUMNS = [
    "last_name",
    "first_name",
    "birthdate",
    "fg_id",
    "level",
    "is_carded",
    "ls_gs",
    "ls_g",
    "ls_plate_appearances",
    "defense",
    "is_reserve",
    "is_2h_p",
    "is_2h_c",
    "is_2h_pos",
    "is_mlb_roster",
    "is_aaa_roster",
    "team__abbreviation",
]

DRAFTS = [
    {"title": "2021 Offseason AA", "url": "/draft/2021/offseason/aa/"},
    {"title": "2021 Offseason Open", "url": "/draft/2021/offseason/open/"},
    {"title": "2020 Midseason AA", "url": "/draft/2020/midseason/aa/"},
    {"title": "2020 Midseason Open", "url": "/draft/2020/midseason/open/"},
    {"title": "2020 Offseason AA", "url": "/draft/2020/offseason/aa/"},
    {"title": "2020 Offseason Open", "url": "/draft/2020/offseason/open/"},
    {"title": "2019 Midseason AA", "url": "/draft/2019/midseason/aa/"},
    {"title": "2019 Midseason Open", "url": "/draft/2019/midseason/open/"},
    {"title": "2019 Offseason AA", "url": "/draft/2019/offseason/aa/"},
    {"title": "2019 Offseason Open", "url": "/draft/2019/offseason/open/"},
    {"title": "2018 Midseason AA", "url": "/draft/2018/midseason/aa/"},
    {"title": "2018 Midseason Open", "url": "/draft/2018/midseason/open/"},
    {"title": "2018 Offseason AA", "url": "/draft/2018/offseason/aa/"},
    {"title": "2018 Offseason Open", "url": "/draft/2018/offseason/open/"},
]

## BOWERS SPECIFIC THINGS
BOWERS_DRAFT_SHEET = "1Wb9f6QrGULjg2qs2Bmq6EWVXXKmw-WdYg-loYvGnpFY"
BOWERS_DRAFT_RANGES = ["TOP80!A1:V1000"]

## MAIL
MAILGUN_API_KEY = os.environ.get('MAILGUN_API_KEY', None)