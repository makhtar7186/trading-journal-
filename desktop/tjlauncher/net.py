"""Utilitaires réseau : ports libres, attente d'un service HTTP."""
import socket
import time
import urllib.error
import urllib.request
from collections.abc import Callable


def is_port_free(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1) if hasattr(socket, "SO_EXCLUSIVEADDRUSE") else None
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def find_free_port(preferred: int, avoid: set[int] | None = None, tries: int = 200) -> int:
    """`preferred` s'il est libre, sinon le premier port libre qui suit (jamais un port de `avoid`)."""
    avoid = avoid or set()
    for port in range(preferred, preferred + tries):
        if port not in avoid and is_port_free(port):
            return port
    raise OSError(f"Aucun port libre trouvé à partir de {preferred}.")


def tcp_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def internet_available(host: str, port: int = 443, timeout: float = 4.0) -> bool:
    """Connexion Internet utilisable pour joindre `host` (résolution DNS + connexion TCP)."""
    return tcp_open(host, port, timeout)


def http_ok(url: str, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310 (URL locale construite par nous)
            return 200 <= response.status < 400
    except (urllib.error.URLError, OSError, ValueError):
        return False


def wait_until(check: Callable[[], bool], timeout: float, interval: float = 0.4, sleep=time.sleep, clock=time.monotonic) -> bool:
    deadline = clock() + timeout
    while clock() < deadline:
        if check():
            return True
        sleep(interval)
    return check()
