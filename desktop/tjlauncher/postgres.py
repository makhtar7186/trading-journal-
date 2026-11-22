"""PostgreSQL : détection, démarrage, installation officielle silencieuse, création de la base et du rôle.

Principes :
- On N'INSTALLE PAS si un PostgreSQL est déjà présent (on le réutilise) ;
- l'application utilise un rôle dédié, SANS droits de superutilisateur, propriétaire de sa seule base ;
- le mot de passe superutilisateur n'est conservé que si c'est NOUS qui avons installé PostgreSQL ;
- l'installateur n'est lancé qu'après contrôle de son empreinte SHA-256 ET de sa signature numérique.
"""
from __future__ import annotations

import os
import re
import secrets
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from . import download as dl
from . import elevation, net, paths
from .config import Config
from .ui import UI, SetupCancelled
from .version import PG_INSTALLER

CREATE_NO_WINDOW = 0x08000000
PG_PORT_CANDIDATES = range(5432, 5440)
INSTALL_TIMEOUT_MS = 25 * 60 * 1000


class PostgresError(Exception):
    """Erreur affichable telle quelle à l'utilisateur."""


# --------------------------------------------------------------------------------------------- détection


@dataclass(frozen=True)
class PgInstall:
    version: str
    bin_dir: Path
    service: str | None = None
    data_dir: Path | None = None


def _version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", version)) or (0,)


def _registry_installs() -> list[dict]:
    """Installations enregistrées par l'installateur officiel : HKLM\\SOFTWARE\\PostgreSQL\\Installations."""
    if sys.platform != "win32":
        return []
    import winreg

    found: list[dict] = []
    for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
        try:
            root = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\PostgreSQL\Installations", 0, winreg.KEY_READ | view)
        except OSError:
            continue
        with root:
            index = 0
            while True:
                try:
                    name = winreg.EnumKey(root, index)
                except OSError:
                    break
                index += 1
                values = {}
                try:
                    with winreg.OpenKey(root, name) as sub:
                        for key in ("Base Directory", "Data Directory", "Service ID", "Version"):
                            try:
                                values[key] = str(winreg.QueryValueEx(sub, key)[0])
                            except OSError:
                                pass
                except OSError:
                    continue
                values["name"] = name
                found.append(values)
    return found


def _program_files_installs() -> list[Path]:
    bases = {os.environ.get("ProgramFiles"), os.environ.get("ProgramW6432"), os.environ.get("ProgramFiles(x86)")}
    result = []
    for base in filter(None, bases):
        root = Path(base) / "PostgreSQL"
        if root.is_dir():
            result.extend(p for p in root.iterdir() if (p / "bin" / "pg_dump.exe").exists())
    return result


def detect_installs(
    registry: Callable[[], list[dict]] = _registry_installs,
    scan: Callable[[], list[Path]] = _program_files_installs,
    which: Callable[[str], str | None] = shutil.which,
) -> list[PgInstall]:
    """Installations PostgreSQL de la machine, la plus récente d'abord. Lecture seule."""
    installs: dict[str, PgInstall] = {}

    def add(install: PgInstall) -> None:
        if (install.bin_dir / "pg_dump.exe").exists() or (install.bin_dir / "psql.exe").exists():
            installs.setdefault(str(install.bin_dir).lower(), install)

    for entry in registry():
        base = entry.get("Base Directory")
        if not base:
            continue
        version = entry.get("Version") or Path(base).name
        data = entry.get("Data Directory")
        add(PgInstall(version, Path(base) / "bin", entry.get("Service ID") or entry.get("name"), Path(data) if data else None))
    for base in scan():
        add(PgInstall(base.name, base / "bin", None, None))
    psql = which("psql")
    if psql:
        bin_dir = Path(psql).parent
        add(PgInstall(bin_dir.parent.name, bin_dir, None, None))
    return sorted(installs.values(), key=lambda i: _version_key(i.version), reverse=True)


def service_state(name: str, run=subprocess.run) -> str | None:
    """RUNNING / STOPPED / START_PENDING… ou None si le service n'existe pas."""
    result = run(["sc", "query", name], capture_output=True, text=True, creationflags=CREATE_NO_WINDOW)
    match = re.search(r"STATE\s*:\s*\d+\s+(\w+)", result.stdout or "")
    return match.group(1) if match else None


_SSL_REQUEST = bytes([0, 0, 0, 8, 4, 210, 22, 47])  # SSLRequest du protocole PostgreSQL (longueur 8, code 80877103)


def looks_like_postgres(host: str, port: int, timeout: float = 2.0) -> bool:
    """Vrai si un serveur PostgreSQL répond sur ce port.

    Sondage au niveau du protocole : on envoie une SSLRequest et un vrai serveur répond « S » ou « N ».
    Indépendant de la langue des messages d'erreur, et SANS tentative d'authentification (rien dans ses journaux).
    """
    import socket

    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.settimeout(timeout)
            sock.sendall(_SSL_REQUEST)
            return sock.recv(1) in (b"S", b"N")
    except OSError:
        return False


def find_server_port(host: str = "127.0.0.1", candidates=PG_PORT_CANDIDATES, probe=looks_like_postgres) -> int | None:
    for port in candidates:
        if probe(host, port):
            return port
    return None


# --------------------------------------------------------------------------------------- connexion et base


def can_login(host: str, port: int, user: str, password: str, database: str = "postgres") -> bool:
    import psycopg

    try:
        psycopg.connect(host=host, port=port, dbname=database, user=user, password=password, connect_timeout=6).close()
    except psycopg.Error:
        return False
    return True


def provision_database(host: str, port: int, super_user: str, super_password: str, database: str, role: str, role_password: str) -> None:
    """Crée (ou remet en état) le rôle applicatif et sa base. Idempotent : peut être relancé sans danger.

    Si la base existe déjà (ex. réinstallation de l'application), ses DONNÉES SONT CONSERVÉES ;
    seul le mot de passe du rôle est renouvelé.
    """
    import psycopg
    from psycopg import sql

    try:
        conn = psycopg.connect(host=host, port=port, dbname="postgres", user=super_user, password=super_password,
                               connect_timeout=8, autocommit=True)
    except psycopg.Error as exc:
        raise PostgresError(f"Connexion au serveur PostgreSQL refusée : {exc}") from exc
    with conn:
        role_sql = sql.SQL("{} WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD {}").format(
            sql.Identifier(role), sql.Literal(role_password)
        )
        if conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,)).fetchone():
            conn.execute(sql.SQL("ALTER ROLE ") + role_sql)
        else:
            conn.execute(sql.SQL("CREATE ROLE ") + role_sql)
        if conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (database,)).fetchone():
            conn.execute(sql.SQL("ALTER DATABASE {} OWNER TO {}").format(sql.Identifier(database), sql.Identifier(role)))
        else:
            # template0 : permet UTF8 quelle que soit la locale/l'encodage par défaut du serveur (cas fréquent sous Windows).
            conn.execute(sql.SQL("CREATE DATABASE {} OWNER {} ENCODING 'UTF8' TEMPLATE template0").format(
                sql.Identifier(database), sql.Identifier(role)))
        conn.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(sql.Identifier(database)))
        conn.execute(sql.SQL("GRANT ALL ON DATABASE {} TO {}").format(sql.Identifier(database), sql.Identifier(role)))


# ------------------------------------------------------------------------------------------- installation


def ensure_installer(ui: UI, downloader=dl.download, verifier=dl.verify_authenticode, spec: dict = PG_INSTALLER) -> Path:
    """Installateur officiel téléchargé ET contrôlé (empreinte + signature). Réutilise un fichier déjà valide."""
    dest = paths.downloads_dir() / Path(spec["url"]).name
    mb = spec["size"] / (1024 * 1024)
    ui.status(f"Téléchargement de PostgreSQL {spec['version']} ({mb:.0f} Mo)…")

    def progress(done: int, total: int | None) -> None:
        ui.progress(done / total if total else None)

    try:
        downloader(spec["url"], dest, expected_sha256=spec["sha256"], progress=progress)
        ui.progress(None)
        ui.status("Vérification de la signature numérique de l'installateur…")
        verifier(dest, spec["signer"])
    except dl.DownloadError as exc:
        dest.unlink(missing_ok=True)
        raise PostgresError(str(exc)) from exc
    return dest


def write_option_file(directory: Path, *, super_password: str, port: int, service: str) -> Path:
    """Options de l'installateur dans un fichier (et non en argument) : le mot de passe n'apparaît pas dans la
    liste des processus. Le fichier est supprimé juste après l'installation."""
    path = directory / f"pg-options-{secrets.token_hex(4)}.ini"
    lines = [
        "mode=unattended",
        "unattendedmodeui=none",
        f"superpassword={super_password}",
        f"serverport={port}",
        f"servicename={service}",
        "disable-components=pgAdmin,stackbuilder",
        "install_runtimes=1",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="ascii")
    return path


def _shred(path: Path) -> None:
    try:
        path.write_bytes(b"\0" * max(1, path.stat().st_size))
    except OSError:
        pass
    path.unlink(missing_ok=True)


@dataclass
class InstallResult:
    install: PgInstall | None
    port: int
    super_password: str
    service: str


def install_postgres(
    ui: UI,
    *,
    fetch_installer: Callable[[UI], Path] = ensure_installer,
    run_installer: Callable[[str, str, int], int] = lambda exe, args, wait: elevation.run_elevated(exe, args, wait_ms=wait),
    detect: Callable[[], list[PgInstall]] = detect_installs,
    spec: dict = PG_INSTALLER,
    sleep: Callable[[float], None] | None = None,
) -> InstallResult:
    """Télécharge puis installe PostgreSQL en silence (une seule demande de droits administrateur)."""
    port = net.find_free_port(5432)
    super_password = secrets.token_urlsafe(18)
    service = spec["service_name"]
    installer = fetch_installer(ui)

    option_file = write_option_file(paths.downloads_dir(), super_password=super_password, port=port, service=service)
    ui.status("Installation de PostgreSQL (quelques minutes). Acceptez la demande de droits administrateur de Windows.")
    ui.progress(None)
    try:
        code = run_installer(str(installer), f'--optionfile "{option_file}"', INSTALL_TIMEOUT_MS)
    except elevation.ElevationRefused as exc:
        raise PostgresError(
            "Les droits administrateur sont nécessaires pour installer PostgreSQL. Relancez l'application et acceptez la demande."
        ) from exc
    finally:
        _shred(option_file)
    if code != 0:
        raise PostgresError(
            f"L'installation de PostgreSQL a échoué (code {code}). Journal : %TEMP%\\install-postgresql.log. "
            "Vous pouvez aussi installer PostgreSQL manuellement depuis postgresql.org puis relancer l'application."
        )

    ui.status("Démarrage de PostgreSQL…")
    ready = net.wait_until(lambda: looks_like_postgres("127.0.0.1", port), timeout=180, interval=2.0, **({"sleep": sleep} if sleep else {}))
    if not ready:
        raise PostgresError("PostgreSQL est installé mais ne répond pas. Redémarrez l'ordinateur puis relancez l'application.")
    installs = detect()
    return InstallResult(installs[0] if installs else None, port, super_password, service)


# ------------------------------------------------------------------------------ orchestration (testable)


@dataclass
class PgDeps:
    """Dépendances injectables : permettent de tester toute la logique sans toucher au système."""

    detect: Callable[[], list[PgInstall]] = detect_installs
    service_state: Callable[[str], str | None] = service_state
    start_service: Callable[[str], None] = lambda name: _start_service(name)
    find_port: Callable[[], int | None] = find_server_port
    can_login: Callable[..., bool] = can_login
    provision: Callable[..., None] = provision_database
    install: Callable[[UI], InstallResult] = install_postgres
    sleep: Callable[[float], None] | None = None
    created: list[str] = field(default_factory=list)


def _start_service(name: str) -> None:
    code = elevation.run_elevated("cmd.exe", f"/c net start {name}", wait_ms=120_000)
    if code not in (0, 2):  # 2 = déjà démarré
        raise PostgresError(f"Le service PostgreSQL « {name} » n'a pas pu être démarré (code {code}).")


def database_reachable(cfg: Config, deps: PgDeps) -> bool:
    pg = cfg.postgres
    return bool(pg.password) and deps.can_login(pg.host, pg.port, pg.user, pg.password, pg.database)


def _ask_superuser(ui: UI, deps: PgDeps, host: str, port: int, cfg: Config) -> tuple[str, str]:
    """Identifiants superutilisateur : mémorisés si NOUS avons installé le serveur, sinon demandés (3 essais)."""
    pg = cfg.postgres
    if pg.managed and pg.superuser_password and deps.can_login(host, port, "postgres", pg.superuser_password):
        return "postgres", pg.superuser_password
    error = None
    for _ in range(3):
        secret = ui.ask_secret(
            "PostgreSQL est déjà installé",
            f"Pour créer la base « {pg.database} », saisissez le mot de passe de l'utilisateur « postgres » "
            f"de votre PostgreSQL (port {port}). Il n'est PAS enregistré par l'application.",
            error,
        )
        if secret is None:
            raise SetupCancelled()
        if deps.can_login(host, port, "postgres", secret):
            return "postgres", secret
        error = "Mot de passe incorrect."
    raise PostgresError("Mot de passe PostgreSQL incorrect (3 essais). Relancez l'application.")


def ensure_database(cfg: Config, ui: UI, deps: PgDeps | None = None) -> None:
    """Garantit une base PostgreSQL utilisable et renseigne cfg.postgres. Appelé à CHAQUE lancement (chemin rapide
    si tout est déjà en place) ; ne réinstalle jamais un serveur existant."""
    deps = deps or PgDeps()
    pg = cfg.postgres
    ui.status("Vérification de PostgreSQL…")
    if database_reachable(cfg, deps):
        return

    # Déjà configuré mais serveur arrêté ? On tente de le démarrer avant de tout reprendre.
    if pg.password and pg.service and deps.service_state(pg.service) not in (None, "RUNNING"):
        ui.status("Démarrage du service PostgreSQL…")
        deps.start_service(pg.service)
        net.wait_until(lambda: database_reachable(cfg, deps), timeout=60, interval=2.0, **({"sleep": deps.sleep} if deps.sleep else {}))
        if database_reachable(cfg, deps):
            return

    installs = deps.detect()
    super_user, super_password = "postgres", ""
    service = pg.service

    if installs:
        install = installs[0]
        service = install.service or service
        port = deps.find_port()
        if port is None and service and deps.service_state(service) not in (None, "RUNNING"):
            ui.status(f"Démarrage du service PostgreSQL « {service} »…")
            deps.start_service(service)
            net.wait_until(lambda: deps.find_port() is not None, timeout=60, interval=2.0, **({"sleep": deps.sleep} if deps.sleep else {}))
            port = deps.find_port()
        if port is None:
            raise PostgresError(
                f"PostgreSQL {install.version} est installé mais ne répond pas. Démarrez le service Windows « {service or 'postgresql'} » "
                "puis relancez l'application."
            )
        ui.status(f"PostgreSQL {install.version} détecté (port {port}).")
        super_user, super_password = _ask_superuser(ui, deps, "127.0.0.1", port, cfg)
        pg.bin_dir, pg.managed = str(install.bin_dir), pg.managed
    else:
        choice = ui.choose(
            "PostgreSQL n'est pas installé",
            f"Trading Journal stocke vos données dans PostgreSQL. Voulez-vous installer PostgreSQL {PG_INSTALLER['version']} maintenant ? "
            f"Téléchargement d'environ {PG_INSTALLER['size'] // (1024 * 1024)} Mo (connexion Internet) puis installation "
            "(une demande de droits administrateur Windows).",
            ["Installer PostgreSQL", "Utiliser un serveur PostgreSQL existant", "Quitter"],
        )
        if choice is None or choice == 2:
            raise SetupCancelled()
        if choice == 1:
            params = ui.ask_connection()
            if not params:
                raise SetupCancelled()
            host, port = params.get("host", "127.0.0.1"), int(params.get("port", 5432))
            super_user, super_password = params["user"], params["password"]
            if not deps.can_login(host, port, super_user, super_password):
                raise PostgresError("Connexion refusée par le serveur PostgreSQL indiqué (hôte, port, utilisateur ou mot de passe).")
            pg.host = host
        else:
            result = deps.install(ui)
            port, super_password, service = result.port, result.super_password, result.service
            pg.managed, pg.superuser_password = True, result.super_password
            pg.bin_dir = str(result.install.bin_dir) if result.install else pg.bin_dir

    ui.status("Création de la base de données de l'application…")
    role_password = secrets.token_urlsafe(24)
    host = pg.host or "127.0.0.1"
    deps.provision(host, port, super_user, super_password, pg.database, pg.user, role_password)
    if not deps.can_login(host, port, pg.user, role_password, pg.database):
        raise PostgresError("La base a été créée mais la connexion avec le compte de l'application échoue.")
    pg.host, pg.port, pg.password, pg.service = host, port, role_password, service or ""
    if not pg.managed:
        pg.superuser_password = ""  # jamais conservé pour un serveur qui n'est pas le nôtre
