"""Django settings — MIS Core.

Pontos de atenção para deploy em rede OT:
- FORCE_SCRIPT_NAME permite rodar atrás de hub em /mis-core/
- USE_X_FORWARDED_HOST + SECURE_PROXY_SSL_HEADER respeitam o hub
- WhiteNoise serve /static/ direto do gunicorn (sem nginx separado)
- admin_mis precisa vir ANTES de django.contrib.admin para sobrescrever
  os templates do admin nativo.
"""

from pathlib import Path
from datetime import timedelta

from decouple import config
import pymysql
pymysql.install_as_MySQLdb()

BASE_DIR = Path(__file__).resolve().parent.parent

# =============================================================================
# Core
# =============================================================================
SECRET_KEY = config('DJANGO_SECRET_KEY', default='django-insecure-dev-key')
DEBUG = config('DJANGO_DEBUG', default=True, cast=bool)

# =============================================================================
# Acesso por VPN (Tailscale etc.) — abre hosts/CSRF/CORS para qualquer IP.
# Use ALLOW_ANY_HOST=True quando o servidor for acessado por VPN com IP variável.
# Em rede OT/VPN interna isso é seguro; jamais ative voltado para internet aberta.
# =============================================================================
# Toggle único: ALLOW_ANY_ORIGIN é o nome canônico, ALLOW_ANY_HOST mantido para compat
ALLOW_ANY_ORIGIN = config('ALLOW_ANY_ORIGIN', default=None)
if ALLOW_ANY_ORIGIN is None:
    ALLOW_ANY_ORIGIN = config('ALLOW_ANY_HOST', default=False, cast=bool)
else:
    ALLOW_ANY_ORIGIN = str(ALLOW_ANY_ORIGIN).strip().lower() in ('1', 'true', 'yes', 'on')
ALLOW_ANY_HOST = ALLOW_ANY_ORIGIN  # alias usado pelo middleware abaixo

if ALLOW_ANY_HOST:
    ALLOWED_HOSTS = ['*']
    CSRF_TRUSTED_ORIGINS = [
        'http://*', 'https://*',
        'http://*.*', 'https://*.*',
    ]
else:
    ALLOWED_HOSTS = [
        h.strip() for h in config('DJANGO_ALLOWED_HOSTS', default='*').split(',') if h.strip()
    ]
    CSRF_TRUSTED_ORIGINS = [
        o.strip() for o in config(
            'CSRF_TRUSTED_ORIGINS',
            default='http://localhost:8080,http://127.0.0.1:8080,http://localhost:5173,http://127.0.0.1:5173',
        ).split(',') if o.strip()
    ]

# =============================================================================
# Sub-path / proxy reverso
# =============================================================================
# FORCE_SCRIPT_NAME = "/mis-core" → todas as URLs do Django (admin, api,
# static) ficam prefixadas. Use SOMENTE quando o hub mapear /mis-core/* para
# este Django. Em standalone, deixe vazio.
_force_script = config('FORCE_SCRIPT_NAME', default='').strip()
FORCE_SCRIPT_NAME = _force_script or None

# Confiar no X-Forwarded-* do hub (caso contrário, request.scheme fica HTTP
# mesmo quando o cliente acessou via HTTPS, e cookies SECURE quebram).
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# =============================================================================
# Apps
# =============================================================================
INSTALLED_APPS = [
    # admin_mis: templates customizados — DEVE vir antes do contrib.admin
    'admin_mis',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'django_apscheduler',
    'equipamentos',
    'analytics',
    'import_export',
]

# =============================================================================
# Middleware
# =============================================================================
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    # Quando ALLOW_ANY_HOST=True, este middleware marca /api/* como CSRF-exempt
    # ANTES do CsrfViewMiddleware processar a request.
    *((['config.demo_middleware.DisableCSRFForApiMiddleware'] if ALLOW_ANY_HOST else [])),
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
                # Injeta versão do MIS no contexto do admin
                'admin_mis.context_processors.mis_version',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# =============================================================================
# Database
# =============================================================================
if config('MYSQL_HOST', default=None):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': config('MYSQL_DB', default='mis_core_db'),
            'USER': config('MYSQL_USER', default='root'),
            'PASSWORD': config('MYSQL_PASSWORD', default='root'),
            'HOST': config('MYSQL_HOST', default='mysql'),
            'PORT': config('MYSQL_PORT', default='3306'),
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

# =============================================================================
# Static files — WhiteNoise serve direto pelo gunicorn
# =============================================================================
STATIC_URL = (FORCE_SCRIPT_NAME or '') + '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# WhiteNoise: cache forte para arquivos com hash, sem cache para os outros.
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# =============================================================================
# CORS
# =============================================================================
CORS_ALLOW_ALL_ORIGINS = config('CORS_ALLOW_ALL_ORIGINS', default=False, cast=bool) or ALLOW_ANY_HOST
CORS_ALLOWED_ORIGINS = [
    o.strip() for o in config('CORS_ALLOWED_ORIGINS', default='').split(',') if o.strip()
]
if not CORS_ALLOWED_ORIGINS and not CORS_ALLOW_ALL_ORIGINS:
    CORS_ALLOWED_ORIGINS = [
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
CORS_ALLOW_CREDENTIALS = True

# =============================================================================
# DRF + JWT
# =============================================================================
REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 100,
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'config.authentication.CookieJWTAuthentication',
    ),
    # Em rede OT interna as APIs de métricas e coleta são públicas.
    # Views que exigem autenticação real (ex: modificar dados sensíveis)
    # devem declarar @permission_classes([IsAuthenticated]) individualmente.
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.AllowAny',
    ),
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=12),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': False,
    'AUTH_COOKIE': 'access_token',
    'AUTH_COOKIE_DOMAIN': config('SESSION_COOKIE_DOMAIN', default=None),
    'AUTH_COOKIE_SECURE': not DEBUG,
    'AUTH_COOKIE_HTTP_ONLY': True,
    'AUTH_COOKIE_PATH': (FORCE_SCRIPT_NAME or '') + '/',
    'AUTH_COOKIE_SAMESITE': 'Lax',
    'SIGNING_KEY': config('JWT_SECRET_KEY', default=SECRET_KEY),
}

# =============================================================================
# Sessões e cookies (alinhar com sub-path quando necessário)
# =============================================================================
SESSION_COOKIE_PATH = (FORCE_SCRIPT_NAME or '') + '/'
CSRF_COOKIE_PATH = SESSION_COOKIE_PATH
SESSION_COOKIE_DOMAIN = config('SESSION_COOKIE_DOMAIN', default=None) or None

# =============================================================================
# InfluxDB
# =============================================================================
INFLUXDB_HOST = config('INFLUXDB_HOST', default='mis-core-influxdb')
INFLUXDB_PORT = config('INFLUXDB_PORT', default=8086, cast=int)
INFLUXDB_USER = config('INFLUXDB_USER', default='admin')
INFLUXDB_PASSWORD = config('INFLUXDB_PASSWORD', default='admin123')
INFLUXDB_DATABASE = config('INFLUXDB_DATABASE', default='mis_core_db')

# =============================================================================
# Admin v2 — header / título
# =============================================================================
# Usado por admin_mis/templates/admin/base_site.html
ADMIN_SITE_HEADER = "MIS Core — Backend"
ADMIN_SITE_TITLE = "MIS Core Admin"
ADMIN_INDEX_TITLE = "Painel de gestão"
