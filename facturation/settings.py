"""
Django settings for facturation project.
"""
#import pymysql
#pymysql.install_as_MySQLdb()


from pathlib import Path
import os

# ═══════════════════════════════════════════════════════════════
#  CHEMINS
# ═══════════════════════════════════════════════════════════════

BASE_DIR = Path(__file__).resolve().parent.parent

LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)


# ═══════════════════════════════════════════════════════════════
#  SÉCURITÉ DE BASE
# ═══════════════════════════════════════════════════════════════

SECRET_KEY = 'django-insecure-ovya$oc&=ta*$40t556#1f2kh$c6ubnjfcfs!$2z=-6a*e-d$+'
# ⚠️ À CHANGER EN PRODUCTION :
#    python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

DEBUG = False
# ⚠️ METTRE À False EN PRODUCTION

ALLOWED_HOSTS = ['app.facturation.bi', 'www.app.facturation.bi']

#ALLOWED_HOSTS = ['127.0.0.1', 'localhost']
# En production : ALLOWED_HOSTS = ['votre-domaine.bi', 'www.votre-domaine.bi']


# ═══════════════════════════════════════════════════════════════
#  APPLICATIONS INSTALLÉES
#  ✅ 'societe' DOIT être avant 'superadmin'
#     superadmin/models.py importe depuis societe.models (FK)
# ═══════════════════════════════════════════════════════════════

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',

    # ── Modules socle ─────────────────────────────────────────────
    'societe',      # ✅ AVANT superadmin (FK dependency)
    'superadmin',
    'accounts',

    # ── Modules métier créés ──────────────────────────────────────
    'categories',
    'clients',

    # ── Modules en cours de création (décommenter au fur et à mesure)
    'taux',
    'fournisseurs',
    'produits',
    'services',
    'stock',
    'facturer',
    'rapports',
    'equipe',
]


# ═══════════════════════════════════════════════════════════════
#  MIDDLEWARE
# ═══════════════════════════════════════════════════════════════

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'superadmin.middleware.SecurityHeadersMiddleware',   # En-têtes HTTP sécurité
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'superadmin.middleware.LicenceMiddleware',           # Vérif licence à chaque requête
    'superadmin.middleware.RateLimitMiddleware',         # Anti brute-force
    'superadmin.middleware.AuditLogMiddleware',          # Journal sécurité
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


# ═══════════════════════════════════════════════════════════════
#  URLS & AUTH
# ═══════════════════════════════════════════════════════════════

ROOT_URLCONF = 'facturation.urls'

AUTH_USER_MODEL    = 'superadmin.Utilisateur'
LOGIN_URL          = '/accounts/login/'
LOGIN_REDIRECT_URL = '/accueil/'

# URL de redirection quand la licence est expirée (LicenceMiddleware)
LICENCE_EXPIRED_URL = '/superadmin/licence-expiree/'


# ═══════════════════════════════════════════════════════════════
#  TEMPLATES
# ═══════════════════════════════════════════════════════════════

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],   # ✅ Dossier templates/ à la racine du projet
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

WSGI_APPLICATION = 'facturation.wsgi.application'


# ═══════════════════════════════════════════════════════════════
#  BASE DE DONNÉES
# ═══════════════════════════════════════════════════════════════

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'gcbvghdlauy_app_wibabi',           # Nom de ta base de données (minuscule recommandé)
        'USER': 'gcbvghdlauy',               # Change en production par un utilisateur dédié
        'PASSWORD': '28rAQhMqp66Gk5',               # Mets ton mot de passe MySQL ici
        'HOST': '127.0.0.1',
        'PORT': '3306',
        'OPTIONS': {
            'charset': 'utf8mb4',
        },
        # Options recommandées pour éviter les problèmes de connexion
        'CONN_MAX_AGE': 300,          # Garde la connexion ouverte 5 minutes
        'ATOMIC_REQUESTS': True,      # Transactions automatiques par requête
    }
}

# ═══════════════════════════════════════════════════════════════gcbvghdlauy
#  CACHE  (requis pour le Rate Limiting)
# ═══════════════════════════════════════════════════════════════

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "facturation-ratelimit",
    }
}
# ── Option Redis (plus robuste en production) :
# pip install django-redis
# CACHES = {
#     "default": {
#         "BACKEND": "django_redis.cache.RedisCache",
#         "LOCATION": "redis://127.0.0.1:6379/1",
#     }
# }


# ═══════════════════════════════════════════════════════════════
#  RATE LIMITING (RateLimitMiddleware)
# ═══════════════════════════════════════════════════════════════

RATELIMIT_SETUP_MAX    = 5    # Max 5 tentatives POST sur /setup/ en 5 minutes
RATELIMIT_SETUP_WINDOW = 300

RATELIMIT_LOGIN_MAX    = 10   # Max 10 tentatives POST sur /accounts/login/ en 5 minutes
RATELIMIT_LOGIN_WINDOW = 300

SUPERADMIN_WHITELIST_IPS = ['127.0.0.1', '::1']


# ═══════════════════════════════════════════════════════════════
#  SESSIONS
# ═══════════════════════════════════════════════════════════════

SESSION_COOKIE_HTTPONLY         = True
SESSION_COOKIE_SAMESITE         = 'Lax'
SESSION_COOKIE_AGE              = 28800   # 8 heures
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# À activer en production (HTTPS uniquement) :
# SESSION_COOKIE_SECURE = True
# CSRF_COOKIE_SECURE    = True
# SECURE_SSL_REDIRECT   = True


# ═══════════════════════════════════════════════════════════════
#  SÉCURITÉ DJANGO NATIVE
# ═══════════════════════════════════════════════════════════════

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS             = 'DENY'


# ═══════════════════════════════════════════════════════════════
#  VALIDATION MOTS DE PASSE
# ═══════════════════════════════════════════════════════════════

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# ═══════════════════════════════════════════════════════════════
#  INTERNATIONALISATION
# ═══════════════════════════════════════════════════════════════

LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'Africa/Bujumbura'

USE_I18N = True
USE_L10N = True          # ← Important pour les formats français
USE_TZ = True            # ← Très important (ne pas commenter !)

# Devise par défaut pour le Burundi
DEFAULT_CURRENCY = 'BIF'

# ==============================================================
# Configuration des formats de date et heure (recommandé)
# ==============================================================

# Formats d'affichage par défaut (format français)
DATE_FORMAT = 'd/m/Y'                    # jj/mm/aaaa
TIME_FORMAT = 'H:i'                      # 14:30
DATETIME_FORMAT = 'd/m/Y H:i'            # 25/03/2026 14:30

# Formats acceptés en saisie
DATE_INPUT_FORMATS = [
    '%d/%m/%Y',     # 25/03/2026
    '%d-%m-%Y',     # 25-03-2026
    '%Y-%m-%d',     # 2026-03-25
]

# Formats courts (utiles pour les listes et admin)
SHORT_DATE_FORMAT = 'd/m/Y'
SHORT_DATETIME_FORMAT = 'd/m/Y H:i'

# Optionnel : format avec secondes si tu en as besoin
# TIME_FORMAT = 'H:i:s'

# ═══════════════════════════════════════════════════════════════
#  FICHIERS STATIQUES & MEDIA
# ═══════════════════════════════════════════════════════════════

STATIC_URL  = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / 'static',                         # Dossier static à la racine du projet
]

STATIC_ROOT = BASE_DIR / 'staticfiles' 
MEDIA_URL   = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# ═══════════════════════════════════════════════════════════════
#  LOGGING
# ═══════════════════════════════════════════════════════════════

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'security': {
            'format': '[{asctime}] [{levelname}] {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'security_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': str(LOGS_DIR / 'security.log'),
            'maxBytes': 5 * 1024 * 1024,
            'backupCount': 10,
            'formatter': 'security',
            'encoding': 'utf-8',
        },
        'app_file': {
            'level': 'WARNING',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': str(LOGS_DIR / 'app.log'),
            'maxBytes': 10 * 1024 * 1024,
            'backupCount': 5,
            'formatter': 'verbose',
            'encoding': 'utf-8',
        },
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'security',
        },
    },
    'loggers': {
        'superadmin.security': {
            'handlers': ['security_file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
        'django': {
            'handlers': ['console', 'app_file'],
            'level': 'WARNING',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console','app_file'],
            'level': 'ERROR',
            'propagate': True,
        },
    },
}
