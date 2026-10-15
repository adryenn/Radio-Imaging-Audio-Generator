import os
from pathlib import Path
import dj_database_url

ROOT = Path(__file__).resolve().parents[2]
PRODUCTION = os.environ.get('APP_ENV') == 'production'
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', '')
if PRODUCTION and (len(SECRET_KEY) < 50 or not os.environ.get('DATABASE_URL') or not os.environ.get('REDIS_URL')):
    raise RuntimeError('Production requires a strong secret, DATABASE_URL and REDIS_URL.')
if not SECRET_KEY:
    # Dev-only: random per-process sessions, never a committed production key.
    import secrets
    SECRET_KEY = secrets.token_urlsafe(50)
DEBUG = False
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1,testserver').split(',')
SITE_URL = os.environ.get('SITE_URL', 'http://localhost:4173').rstrip('/')
if PRODUCTION and not SITE_URL.startswith('https://'):
    raise RuntimeError('Production SITE_URL must use HTTPS.')
CSRF_TRUSTED_ORIGINS = [SITE_URL]
TRUSTED_PROXY_IPS = set(filter(None, os.environ.get('TRUSTED_PROXY_IPS', '').split(',')))
if os.environ.get('TRUST_PROXY_TLS') == '1':
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
INSTALLED_APPS = ['django.contrib.auth', 'django.contrib.contenttypes', 'django.contrib.sessions', 'studio']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware', 'studio.middleware.PrivateAPIResponses', 'whitenoise.middleware.WhiteNoiseMiddleware',
              'django.contrib.sessions.middleware.SessionMiddleware', 'django.middleware.common.CommonMiddleware',
              'django.middleware.csrf.CsrfViewMiddleware', 'django.contrib.auth.middleware.AuthenticationMiddleware']
ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'
DATABASES = {'default': dj_database_url.parse(os.environ.get('DATABASE_URL', 'sqlite:///' + str(ROOT / 'server/db.sqlite3')), conn_max_age=60)}
if PRODUCTION and DATABASES['default']['ENGINE'] != 'django.db.backends.postgresql':
    raise RuntimeError('Production requires PostgreSQL for billing transaction locks.')
CACHES = {'default': {'BACKEND': 'django.core.cache.backends.redis.RedisCache', 'LOCATION': os.environ['REDIS_URL']}} if os.environ.get('REDIS_URL') else {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 12}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
]
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = PRODUCTION
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SECURE = PRODUCTION
SESSION_COOKIE_AGE = 60 * 60 * 12
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SECURE_SSL_REDIRECT = PRODUCTION
SECURE_HSTS_SECONDS = 31536000 if PRODUCTION else 0
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
DATA_UPLOAD_MAX_MEMORY_SIZE = 128 * 1024
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
USE_TZ = True
WHITENOISE_ROOT = ROOT / 'website/dist/client'
WHITENOISE_INDEX_FILE = True
STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', '')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '')
# No published prices or credits until deliberately configured by the operator.
PLANS = {slug: {'name': name, 'price': os.environ.get('STRIPE_PRICE_' + slug.upper(), ''),
                'credits': int(os.environ.get('PLAN_CREDITS_' + slug.upper(), '0'))}
         for slug, name in [('creator', 'Creator'), ('studio', 'Studio'), ('team', 'Team')]}
COMMERCIAL_MODELS = set(filter(None, os.environ.get('COMMERCIAL_MODEL_IDS', 'gpt-4o-mini-tts').split(',')))
PROVIDER_KEYS = {'OpenAI': os.environ.get('OPENAI_API_KEY', ''), 'ElevenLabs': os.environ.get('ELEVENLABS_API_KEY', ''),
                 'Google': os.environ.get('GEMINI_API_KEY', ''), 'Cartesia': os.environ.get('CARTESIA_API_KEY', '')}
