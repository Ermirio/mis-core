from pathlib import Path
from decouple import config
import pymysql
pymysql.install_as_MySQLdb()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('DJANGO_SECRET_KEY', default='django-insecure-dev-key')
DEBUG = config('DJANGO_DEBUG', default=True, cast=bool)

# DEFINIÇÃO ÚNICA
# DEFINIÇÃO ÚNICA
ALLOWED_HOSTS = ['*']
import os
print(f"DEBUG: RAW_ENV_VAR={os.environ.get('DJANGO_ALLOWED_HOSTS')}")
print(f"DEBUG: DECOUPLE_CONFIG={config('DJANGO_ALLOWED_HOSTS', default='NOT_FOUND')}")
print(f"DEBUG: ALLOWED_HOSTS={ALLOWED_HOSTS}")

# CSRF Trusted Origins - Lê do ambiente e faz merge com padrões
_default_csrf_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "http://localhost:5000",
    "http://127.0.0.1:5000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:8001",   # Django direto (porta mapeada no host)
    "http://127.0.0.1:8001",
    "http://localhost:8080",   # Proxy Nginx (porta pública do stack)
    "http://127.0.0.1:8080",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
_extra_csrf_origins = config('CSRF_TRUSTED_ORIGINS', default='').split(',')
_extra_csrf_origins = [o.strip() for o in _extra_csrf_origins if o.strip()]
CSRF_TRUSTED_ORIGINS = _default_csrf_origins + _extra_csrf_origins


INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'django_apscheduler',  # Scheduler automático
    'equipamentos',
    'analytics',  # App de perfis de Analytics
    'import_export',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',   # tem que ser o PRIMEIRO
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Serve static files
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

if config('MYSQL_HOST', default=None):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': config('MYSQL_DB', default='mis_core_db'),
            'USER': config('MYSQL_USER', default='root'),
            'PASSWORD': config('MYSQL_PASSWORD', default='root'),
            'HOST': config('MYSQL_HOST', default='mysql'),
            'PORT': config('MYSQL_PORT', default='3307'),
            'OPTIONS': {
                'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
                'charset': 'utf8mb4',
            }
        }
    }

else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- CORS ---
# Permite todas as origens SOMENTE se configurado explicitamente (ex: em dev)
CORS_ALLOW_ALL_ORIGINS = config('CORS_ALLOW_ALL_ORIGINS', default=False, cast=bool)

CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS', default='').split(',')
CORS_ALLOWED_ORIGINS = [origin.strip() for origin in CORS_ALLOWED_ORIGINS if origin.strip()]

if not CORS_ALLOWED_ORIGINS and not CORS_ALLOW_ALL_ORIGINS:
    # Fallback razoável para desenvolvimento local se nada for configurado
    CORS_ALLOWED_ORIGINS = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

CORS_ALLOW_CREDENTIALS = True

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 100,
    'DEFAULT_AUTHENTICATION_CLASSES': (
        # A nova classe customizada buscará o token tanto do header (Bearer) quanto do Cookie (access_token)
        'config.authentication.CookieJWTAuthentication',
    ),
}

from datetime import timedelta
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=12),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': False,
    'AUTH_COOKIE': 'access_token',      # Nome do cookie com access_token
    'AUTH_COOKIE_DOMAIN': config('SESSION_COOKIE_DOMAIN', default=None), # Compartilha o cookie no mesmo host/IP
    'AUTH_COOKIE_SECURE': not DEBUG,    # True se usar HTTPS (False no dev/http local)
    'AUTH_COOKIE_HTTP_ONLY': True,      # Bloqueia leitura do cookie via JS
    'AUTH_COOKIE_PATH': '/',
    'AUTH_COOKIE_SAMESITE': 'Lax',      # Protege contra CSRF mas permite navegação
    
    'SIGNING_KEY': config('JWT_SECRET_KEY', default=SECRET_KEY), # Se houver JWT_SECRET no .env, usa. Senão, herda SECRET_KEY do django
}



# --- InfluxDB ---
INFLUXDB_HOST = config('INFLUXDB_HOST', default='mis-core-influxdb')
INFLUXDB_PORT = config('INFLUXDB_PORT', default=8086, cast=int)
INFLUXDB_USER = config('INFLUXDB_USER', default='admin')
INFLUXDB_PASSWORD = config('INFLUXDB_PASSWORD', default='admin123')
INFLUXDB_DATABASE = config('INFLUXDB_DATABASE', default='mis_core_db')
