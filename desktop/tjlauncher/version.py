"""Version de l'application et installateur PostgreSQL officiel attendu."""

__version__ = "1.0.0"
APP_NAME = "Trading Journal"
APP_ID = "TradingJournal"

PG_MAJOR = 17

# Installateur officiel EnterpriseDB (le même que celui du site postgresql.org). L'empreinte a été relevée au
# téléchargement (HTTPS) et la signature Authenticode vérifiée (éditeur « EnterpriseDB Corporation », DigiCert).
# Au lancement, le fichier téléchargé est de nouveau contrôlé (empreinte ET signature) AVANT toute élévation.
PG_INSTALLER = {
    "version": "17.12",
    "url": "https://get.enterprisedb.com/postgresql/postgresql-17.12-1-windows-x64.exe",
    "sha256": "23bc416a9fee380f0d9ba1969647e374b43c4f37ce8ae5762f2ea59350f49fbc",
    "size": 416_659_176,
    "signer": "EnterpriseDB Corporation",
    "service_name": "postgresql-x64-17",
}
