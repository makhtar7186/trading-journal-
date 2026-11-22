"""Version desktop (Windows) : un seul poste, serveurs liés à 127.0.0.1, HTTP local.

Configuré par le lanceur via variables d'environnement (voir desktop/launcher/processes.py).
"""
from pathlib import Path

from .base import *  # noqa: F401,F403
from .base import BASE_DIR, env

DEBUG = False

# Base de données : PostgreSQL (défaut, réglée par base.py) ou SQLite en mode de secours, quand PostgreSQL n'a pas pu
# être installé/configuré. Le lanceur migre ensuite les données vers PostgreSQL dès que c'est possible.
if env("DB_ENGINE", default="postgres") == "sqlite":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": env("SQLITE_PATH"),
            "OPTIONS": {
                "timeout": 30,  # l'API et les commandes de gestion peuvent écrire à tour de rôle
                # WAL : lectures pendant une écriture ; synchronous=FULL : pas de perte en cas de coupure de courant.
                "init_command": "PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL;",
                "transaction_mode": "IMMEDIATE",
            },
        }
    }

ALLOWED_HOSTS = ["127.0.0.1", "localhost", "[::1]"]

# Création de compte depuis l'interface : activée ici, mais réservée aux requêtes locales
# (voir apps/accounts/registration.py).
ALLOW_REGISTRATION = env.bool("ALLOW_REGISTRATION", default=True)

# L'application est servie en HTTP sur la machine locale : pas de redirection HTTPS ni de cookie « Secure »
# (le navigateur les refuserait). Les cookies restent HttpOnly + SameSite=Lax, et n'écoutent que 127.0.0.1.
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_AGE = 60 * 60 * 24 * 30  # 30 jours : poste personnel

# Journalisation dans un fichier tournant (jamais de secrets ni de mots de passe dans les journaux).
LOG_DIR = Path(env("LOG_DIR", default=str(BASE_DIR / "logs")))
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"standard": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"}},
    "handlers": {
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / "backend.log"),
            "maxBytes": 1_000_000,
            "backupCount": 5,
            "encoding": "utf-8",
            "formatter": "standard",
        },
    },
    "root": {"handlers": ["file"], "level": "INFO"},
    "loggers": {"django.server": {"level": "WARNING"}},
}
