"""Point d'entrée : `TradingJournal.exe` (interface graphique) et `tjctl.exe` (ligne de commande, serveurs enfants).

Sous-commandes :
  (aucune)       assistant graphique puis application
  run            démarre sans fenêtre (--no-browser) ; Ctrl+C pour arrêter
  serve-api      serveur de l'API (processus enfant du lanceur)
  manage ...     commandes Django (migrate, register_user…)
  backup [FICHIER] / restore FICHIER / verify FICHIER
  status | self-test | --version
"""
from __future__ import annotations

import argparse
import logging
import logging.handlers
import os
import sys
from pathlib import Path

from . import paths
from .version import __version__


def _setup_logging() -> None:
    handler = logging.handlers.RotatingFileHandler(paths.logs_dir() / "launcher.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.INFO)


def _prepare_backend_path() -> None:
    if not paths.is_frozen():
        sys.path.insert(0, str(paths.backend_dir()))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.desktop")


def _out(text: str = "") -> None:
    stream = sys.stdout or sys.stderr
    if stream:
        stream.write(text + "\n")
        stream.flush()


def cmd_serve_api() -> int:
    _prepare_backend_path()
    from config.serve import main

    main()
    return 0


def cmd_manage(args: list[str]) -> int:
    _prepare_backend_path()
    from django.core.management import execute_from_command_line

    execute_from_command_line(["manage.py", *args])
    return 0


def cmd_self_test() -> int:
    """Contrôle rapide d'un build : modules, ressources embarquées, Django. Code 0 si tout est présent."""
    problems: list[str] = []
    _prepare_backend_path()
    try:
        import django
        import psycopg
        import waitress  # noqa: F401
        from django.conf import settings

        os.environ.setdefault("DJANGO_SECRET_KEY", "self-test")
        os.environ.setdefault("POSTGRES_DB", "x")
        os.environ.setdefault("POSTGRES_USER", "x")
        os.environ.setdefault("POSTGRES_PASSWORD", "x")
        django.setup()
        _ = settings.INSTALLED_APPS, psycopg.__version__
    except Exception as exc:  # noqa: BLE001
        problems.append(f"Django : {exc!r}")
    if not (paths.frontend_dir() / "server.js").exists():
        problems.append(f"interface absente : {paths.frontend_dir() / 'server.js'}")
    node = paths.node_exe()
    if paths.is_frozen() and not node.exists():
        problems.append(f"node.exe absent : {node}")
    _out(f"Trading Journal {__version__} — " + ("OK" if not problems else "PROBLÈMES"))
    for problem in problems:
        _out(f"  - {problem}")
    return 1 if problems else 0


def cmd_run(args: argparse.Namespace) -> int:
    import time

    from .app import Launcher, LauncherError
    from .ui import HeadlessUI

    ui = HeadlessUI(
        confirm=True,
        choice=0,
        secret=os.environ.get("TJ_PG_SUPERPASSWORD"),
        account=(
            {"username": os.environ["TJ_ACCOUNT_USER"], "password": os.environ.get("TJ_ACCOUNT_PASSWORD", "")}
            if os.environ.get("TJ_ACCOUNT_USER") else None
        ),
        log=_out,
    )
    launcher = Launcher(ui)
    try:
        launcher.prepare()
        launcher.start()
        launcher.ensure_account()
    except LauncherError as exc:
        _out(f"ERREUR : {exc}")
        launcher.stop()
        return 1
    _out(f"Trading Journal est prêt : {launcher.cfg.ui_url}")
    if not args.no_browser:
        launcher.open_browser()
    try:
        while launcher.stack and launcher.stack.is_running():
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        launcher.stop()
    return 0


def cmd_backup(args: argparse.Namespace) -> int:
    from . import backup, config

    cfg = config.load()
    if not cfg.configured:
        _out("Application non configurée : lancez-la d'abord une fois.")
        return 1
    dest = Path(args.file) if args.file else paths.backups_dir() / backup.default_name()
    try:
        _out(f"Sauvegarde créée : {backup.create_backup(cfg, dest)}")
    except backup.BackupError as exc:
        _out(f"ERREUR : {exc}")
        return 1
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    from . import backup

    try:
        manifest = backup.verify_backup(Path(args.file))
    except backup.BackupError as exc:
        _out(f"INVALIDE : {exc}")
        return 1
    _out(f"Sauvegarde valide (version {manifest['app_version']}, {manifest['created_at']}, {manifest['storage_files']} capture(s)).")
    return 0


def cmd_restore(args: argparse.Namespace) -> int:
    from . import backup, config
    from .net import http_ok

    cfg = config.load()
    if not cfg.configured:
        _out("Application non configurée.")
        return 1
    if http_ok(f"{cfg.api_url}/api/v1/health/", timeout=1.0):
        _out("Fermez d'abord Trading Journal avant de restaurer.")
        return 1
    if not args.yes:
        _out("La restauration REMPLACE vos données actuelles (une sauvegarde de sécurité est créée avant). Relancez avec --yes pour confirmer.")
        return 1
    try:
        safety = backup.restore_backup(cfg, Path(args.file))
    except backup.BackupError as exc:
        _out(f"ERREUR : {exc}")
        return 1
    _out(f"Restauration terminée. Sauvegarde de sécurité : {safety}")
    return 0


def cmd_status() -> int:
    from . import config, net

    cfg = config.load()
    _out(f"Version : {__version__}")
    _out(f"Données : {paths.data_dir()}")
    _out(f"Configurée : {'oui' if cfg.configured else 'non'}")
    if cfg.configured:
        if cfg.uses_sqlite:
            _out(f"Base de données : SQLite (mode de secours) — {paths.sqlite_path()}")
            if cfg.fallback_reason:
                _out(f"Raison : {cfg.fallback_reason}")
        else:
            _out(f"PostgreSQL : {cfg.postgres.host}:{cfg.postgres.port} / {cfg.postgres.database} ({'installé par l\'application' if cfg.postgres.managed else 'existant'})")
        _out(f"Application : {'en cours' if net.http_ok(cfg.api_url + '/api/v1/health/', 1.0) else 'arrêtée'} — {cfg.ui_url}")
    return 0


def _utf8_streams() -> None:
    """Sortie toujours en UTF-8 (sinon cp1252 sous Windows : accents illisibles dès que la sortie est redirigée)."""
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def main(argv: list[str] | None = None) -> int:
    _utf8_streams()
    argv = list(sys.argv[1:] if argv is None else argv)
    # Sous-commandes « enfant » : traitées avant argparse (arguments Django transmis tels quels).
    if argv and argv[0] == "serve-api":
        return cmd_serve_api()
    if argv and argv[0] == "manage":
        return cmd_manage(argv[1:])

    _setup_logging()
    parser = argparse.ArgumentParser(prog="TradingJournal", description="Trading Journal — lanceur desktop")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command")
    run = sub.add_parser("run", help="démarre sans fenêtre")
    run.add_argument("--no-browser", action="store_true")
    backup_p = sub.add_parser("backup", help="crée une sauvegarde")
    backup_p.add_argument("file", nargs="?")
    sub.add_parser("verify", help="vérifie une sauvegarde").add_argument("file")
    restore_p = sub.add_parser("restore", help="restaure une sauvegarde (application fermée)")
    restore_p.add_argument("file")
    restore_p.add_argument("--yes", action="store_true")
    sub.add_parser("status")
    sub.add_parser("self-test")
    args = parser.parse_args(argv)

    if args.command == "run":
        return cmd_run(args)
    if args.command == "backup":
        return cmd_backup(args)
    if args.command == "verify":
        return cmd_verify(args)
    if args.command == "restore":
        return cmd_restore(args)
    if args.command == "status":
        return cmd_status()
    if args.command == "self-test":
        return cmd_self_test()

    from .gui import run_gui

    return run_gui()


if __name__ == "__main__":
    sys.exit(main())
