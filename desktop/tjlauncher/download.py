"""Téléchargement vérifié : empreinte SHA-256 et signature Authenticode, contrôlées avant toute exécution."""
from __future__ import annotations

import hashlib
import subprocess
import urllib.request
from collections.abc import Callable
from pathlib import Path

CHUNK = 1024 * 256


class DownloadError(Exception):
    pass


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(CHUNK * 4), b""):
            digest.update(block)
    return digest.hexdigest()


def download(
    url: str,
    dest: Path,
    *,
    expected_sha256: str,
    progress: Callable[[int, int | None], None] | None = None,
    opener=urllib.request.urlopen,
) -> Path:
    """Télécharge `url` vers `dest` (reprise possible via un fichier .part), vérifie l'empreinte, puis renomme.

    Un fichier dont l'empreinte ne correspond pas est SUPPRIMÉ et jamais retourné.
    """
    if not url.lower().startswith("https://"):
        raise DownloadError("Seul HTTPS est accepté.")
    if dest.exists() and sha256_of(dest) == expected_sha256.lower():
        return dest  # déjà téléchargé et intègre

    part = dest.with_suffix(dest.suffix + ".part")
    offset = part.stat().st_size if part.exists() else 0
    request = urllib.request.Request(url, headers={"User-Agent": "TradingJournal-Setup"})
    if offset:
        request.add_header("Range", f"bytes={offset}-")
    try:
        with opener(request, timeout=30) as response:  # noqa: S310 (https imposé plus haut)
            resumed = offset > 0 and getattr(response, "status", 200) == 206
            if offset and not resumed:
                offset = 0  # le serveur ignore Range : on repart de zéro
            total_header = response.headers.get("Content-Length")
            total = int(total_header) + offset if total_header else None
            done = offset
            with part.open("ab" if resumed else "wb") as out:
                for block in iter(lambda: response.read(CHUNK), b""):
                    out.write(block)
                    done += len(block)
                    if progress:
                        progress(done, total)
    except OSError as exc:  # URLError, timeout, disque plein…
        raise DownloadError(f"Téléchargement impossible : {exc}") from exc

    if sha256_of(part) != expected_sha256.lower():
        part.unlink(missing_ok=True)
        raise DownloadError("L'empreinte du fichier téléchargé ne correspond pas : fichier supprimé.")
    part.replace(dest)
    return dest


def verify_authenticode(path: Path, signer_contains: str, run=subprocess.run) -> None:
    """Exige une signature Authenticode VALIDE dont le sujet contient `signer_contains` (ex. « EnterpriseDB »)."""
    safe = str(path).replace("'", "''")
    script = (
        f"$s = Get-AuthenticodeSignature -LiteralPath '{safe}'; "
        "[Console]::Out.Write($s.Status.ToString() + '|' + $(if ($s.SignerCertificate) { $s.SignerCertificate.Subject } else { '' }))"
    )
    result = run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], capture_output=True, text=True, timeout=60,
                 creationflags=0x08000000)  # CREATE_NO_WINDOW
    status, _, subject = result.stdout.strip().partition("|")
    if status != "Valid":
        raise DownloadError(f"Signature numérique invalide ({status or 'inconnue'}).")
    if signer_contains.lower() not in subject.lower():
        raise DownloadError(f"Éditeur inattendu : {subject or 'inconnu'}.")
