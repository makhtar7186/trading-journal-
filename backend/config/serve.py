"""Serveur WSGI pour Windows (waitress). Lancé par le lanceur desktop : `TradingJournal.exe serve-api`.

Écoute uniquement sur l'adresse demandée (127.0.0.1 par défaut), jamais sur toutes les interfaces.
"""
import os


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.desktop")

    from django.conf import settings
    from django.core.wsgi import get_wsgi_application
    from waitress import serve

    application = get_wsgi_application()
    host = os.environ.get("API_HOST", "127.0.0.1")
    port = int(os.environ.get("API_PORT", "8000"))
    # Corps de requête plafonné (défense en profondeur) : un envoi complet de captures + marge.
    body_limit = settings.SCREENSHOT_MAX_BYTES * settings.SCREENSHOT_MAX_FILES_PER_REQUEST + 1024 * 1024
    serve(application, host=host, port=port, threads=8, max_request_body_size=body_limit, ident="TradingJournal")


if __name__ == "__main__":
    main()
