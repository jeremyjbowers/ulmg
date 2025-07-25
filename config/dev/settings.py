import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    ")(hv#e)wqd-9pwuvd94wq5-snmz+@m(&-g5e74&zg)+geh-xqe+++++sadjklfhlkh7",
)

DEBUG = os.environ.get("DEBUG", True)

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
    "ulmg.middleware.LoginRequiredMiddleware",  # Site-wide login required
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

SESSION_ENGINE = "django.contrib.sessions.backends.db"

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
            "libraries": {
                "ulmg_tags": "ulmg.templatetags.ulmg_tags",
            },
        },
    },
]

WSGI_APPLICATION = "config.dev.app.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql_psycopg2",
        "NAME": os.environ.get("DB_NAME", "ulmg"),
        "USER": os.environ.get("DB_USER", "ulmg"),
        "PASSWORD": os.environ.get("DB_PASSWORD", "ulmg"),
        "HOST": os.environ.get("DB_HOST", "127.0.0.1"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

# LOGIN STUFF
LOGIN_REDIRECT_URL = "/"
LOGIN_URL = "/accounts/login/"
LOGOUT_REDIRECT_URL = "/"

# STATICFILES
STATIC_URL = "/static/"
STATIC_ROOT = "static/"

AWS_S3_REGION_NAME = "nyc3"
AWS_S3_ENDPOINT_URL = f"https://{AWS_S3_REGION_NAME}.digitaloceanspaces.com"
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", None)
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", None)
AWS_DEFAULT_ACL = "public-read"
AWS_STORAGE_BUCKET_NAME = "static-theulmg"
AWS_S3_CUSTOM_DOMAIN = "static-theulmg.nyc3.cdn.digitaloceanspaces.com"
AWS_LOCATION = "static"

# ULMG SPECIFIC SETTINGS
MLB_ROSTER_SIZE = 30
PROTECT_ROSTER_SIZE = 40

TEAM_PROTECT_TAB = False
TEAM_ROSTER_TAB = True
TEAM_LIVE_TAB = False
TEAM_WISHLIST_TAB = False

TEAM_SEASON_HALF = "2h"
CURRENT_SEASON = 2025
CURRENT_SEASON_TYPE = "midseason"

ROSTER_TEAM_IDS = [
    ("1", "LAA", "Los Angeles Angels"),
    ("2", "BAL", "Baltimore Orioles"),
    ("3", "BOS", "Boston Red Sox"),
    ("4", "CHW", "Chicago White Sox"),
    ("5", "CLE", "Cleveland Guardians"),
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
    ("24", "WSN", "Washington Nationals"),
    ("25", "NYM", "New York Mets"),
    ("26", "PHI", "Philadelphia Phillies"),
    ("27", "PIT", "Pittsburgh Pirates"),
    ("28", "STL", "St. Louis Cardinals"),
    ("29", "SDP", "San Diego Padres"),
    ("30", "SFG", "San Francisco Giants"),
]

MLB_URL_TO_ORG_NAME = {
    "orioles": "BAL",
    "whitesox": "CWS",
    "astros": "HOU",
    "redsox": "BOS",
    "guardians": "CLE",
    "indians": "CLE",
    "angels": "LAA",
    "athletics": "OAK",
    "yankees": "NYY",
    "tigers": "DET",
    "rays": "TB",
    "royals": "KC",
    "mariners": "SEA",
    "bluejays": "TOR",
    "twins": "MIN",
    "rangers": "TEX",
    "braves": "ATL",
    "cubs": "CHC",
    "dbacks": "AZ",
    "marlins": "MIA",
    "reds": "CIN",
    "rockies": "COL",
    "mets": "NYM",
    "brewers": "MIL",
    "dodgers": "LAD",
    "phillies": "PHI",
    "pirates": "PIT",
    "padres": "SD",
    "nationals": "WSH",
    "cardinals": "STL",
    "giants": "SF"
}

LEVELS = [
    (16,"R"),
    (14,"A"),
    (13,"A+"),
    (12,'AA'),
    (11,"AAA"),
    (1,"MLB"),
]

CSV_COLUMNS = [
    "last_name",
    "first_name",
    "birthdate",
    "position",
    "level",
    "defense",
    "team__abbreviation",
    "is_ulmg_reserve",
    "is_ulmg_1h_p",
    "is_ulmg_1h_c",
    "is_ulmg_1h_pos",
    "is_ulmg_2h_p",
    "is_ulmg_2h_c",
    "is_ulmg_2h_pos",
    "is_ulmg_2h_draft",
    "is_ulmg_protected",
    "is_ulmg_35man_roster",
    "is_ulmg_mlb_roster",
    "is_ulmg_aaa_roster",
    "is_ulmg_midseason_unprotected",
]

DRAFTS = [
    {"title": "2025 Midseason AA", "url": "/draft/2025/midseason/aa/"},
    {"title": "2025 Midseason Open", "url": "/draft/2025/midseason/open/"},
    {"title": "2025 Offseason AA", "url": "/draft/2025/offseason/aa/"},
    {"title": "2025 Offseason Open", "url": "/draft/2025/offseason/open/"},
    {"title": "2024 Midseason AA", "url": "/draft/2024/midseason/aa/"},
    {"title": "2024 Midseason Open", "url": "/draft/2024/midseason/open/"},
    {"title": "2024 Offseason AA", "url": "/draft/2024/offseason/aa/"},
    {"title": "2024 Offseason Open", "url": "/draft/2024/offseason/open/"},
    {"title": "2023 Midseason AA", "url": "/draft/2023/midseason/aa/"},
    {"title": "2023 Midseason Open", "url": "/draft/2023/midseason/open/"},
    {"title": "2023 Offseason AA", "url": "/draft/2023/offseason/aa/"},
    {"title": "2023 Offseason Open", "url": "/draft/2023/offseason/open/"},
    {"title": "2022 Midseason AA", "url": "/draft/2022/midseason/aa/"},
    {"title": "2022 Midseason Open", "url": "/draft/2022/midseason/open/"},
    {"title": "2022 Offseason AA", "url": "/draft/2022/offseason/aa/"},
    {"title": "2022 Offseason Open", "url": "/draft/2022/offseason/open/"},
    {"title": "2021 Midseason AA", "url": "/draft/2021/midseason/aa/"},
    {"title": "2021 Midseason Open", "url": "/draft/2021/midseason/open/"},
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
MAILGUN_API_KEY = os.environ.get("MAILGUN_API_KEY", None)
