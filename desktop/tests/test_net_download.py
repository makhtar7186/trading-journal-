import hashlib
import io
import socket

import pytest

from tjlauncher import download as dl
from tjlauncher import net


# --- réseau --------------------------------------------------------------------------------------


def test_free_port_skips_busy_and_avoided_ports():
    with socket.socket() as busy:
        busy.bind(("127.0.0.1", 0))
        port = busy.getsockname()[1]
        assert not net.is_port_free(port)
        chosen = net.find_free_port(port)
        assert chosen != port and net.is_port_free(chosen)
    free = net.find_free_port(47900)
    assert net.find_free_port(free, avoid={free}) != free


def test_wait_until_returns_as_soon_as_ready_and_times_out_otherwise():
    clock = {"t": 0.0}
    calls = {"n": 0}

    def check():
        calls["n"] += 1
        return calls["n"] >= 3

    ok = net.wait_until(check, timeout=10, interval=1, sleep=lambda s: clock.__setitem__("t", clock["t"] + s), clock=lambda: clock["t"])
    assert ok and calls["n"] == 3
    clock["t"] = 0.0
    assert not net.wait_until(lambda: False, timeout=3, interval=1, sleep=lambda s: clock.__setitem__("t", clock["t"] + s), clock=lambda: clock["t"])


# --- téléchargement --------------------------------------------------------------------------------


class FakeResponse(io.BytesIO):
    def __init__(self, data, status=200, total=None):
        super().__init__(data)
        self.status = status
        self.headers = {"Content-Length": str(total if total is not None else len(data))}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def sha(data):
    return hashlib.sha256(data).hexdigest()


def test_download_verifies_hash_and_renames(tmp_path):
    data = b"x" * 700_000
    seen = []
    dest = tmp_path / "setup.exe"
    out = dl.download("https://example.test/setup.exe", dest, expected_sha256=sha(data), opener=lambda req, timeout: FakeResponse(data),
                      progress=lambda done, total: seen.append((done, total)))
    assert out == dest and dest.read_bytes() == data
    assert not dest.with_suffix(".exe.part").exists()
    assert seen[-1] == (len(data), len(data)) and all(a <= b for (a, _), (b, _) in zip(seen, seen[1:]))


def test_tampered_download_is_deleted_and_never_returned(tmp_path):
    dest = tmp_path / "setup.exe"
    with pytest.raises(dl.DownloadError, match="empreinte"):
        dl.download("https://example.test/setup.exe", dest, expected_sha256=sha(b"attendu"), opener=lambda req, timeout: FakeResponse(b"malveillant"))
    assert not dest.exists() and not dest.with_suffix(".exe.part").exists()


def test_only_https_is_accepted(tmp_path):
    with pytest.raises(dl.DownloadError, match="HTTPS"):
        dl.download("http://example.test/setup.exe", tmp_path / "s.exe", expected_sha256="0" * 64, opener=lambda *a, **k: FakeResponse(b""))
    with pytest.raises(dl.DownloadError):
        dl.download("ftp://example.test/setup.exe", tmp_path / "s.exe", expected_sha256="0" * 64, opener=lambda *a, **k: FakeResponse(b""))


def test_valid_existing_file_is_reused_without_network(tmp_path):
    dest = tmp_path / "setup.exe"
    dest.write_bytes(b"deja la")

    def boom(*a, **k):
        raise AssertionError("pas de réseau attendu")

    assert dl.download("https://example.test/setup.exe", dest, expected_sha256=sha(b"deja la"), opener=boom) == dest


def test_corrupt_existing_file_is_downloaded_again(tmp_path):
    dest = tmp_path / "setup.exe"
    dest.write_bytes(b"corrompu")
    good = b"bon contenu"
    dl.download("https://example.test/setup.exe", dest, expected_sha256=sha(good), opener=lambda req, timeout: FakeResponse(good))
    assert dest.read_bytes() == good


def test_interrupted_download_resumes_with_range(tmp_path):
    data = bytes(range(256)) * 1000
    dest = tmp_path / "setup.exe"
    dest.with_suffix(".exe.part").write_bytes(data[:100_000])
    requests = []

    def opener(req, timeout):
        requests.append(req.get_header("Range"))
        return FakeResponse(data[100_000:], status=206)

    dl.download("https://example.test/setup.exe", dest, expected_sha256=sha(data), opener=opener)
    assert requests == ["bytes=100000-"] and dest.read_bytes() == data


def test_server_ignoring_range_restarts_from_zero(tmp_path):
    data = b"abc" * 1000
    dest = tmp_path / "setup.exe"
    dest.with_suffix(".exe.part").write_bytes(b"zzz")
    dl.download("https://example.test/setup.exe", dest, expected_sha256=sha(data), opener=lambda req, timeout: FakeResponse(data, status=200))
    assert dest.read_bytes() == data


def test_network_failure_is_reported_in_french(tmp_path):
    def fail(req, timeout):
        raise OSError("réseau coupé")

    with pytest.raises(dl.DownloadError, match="Téléchargement impossible"):
        dl.download("https://example.test/s.exe", tmp_path / "s.exe", expected_sha256="0" * 64, opener=fail)


# --- signature numérique -----------------------------------------------------------------------------------


class Result:
    def __init__(self, stdout):
        self.stdout = stdout


def test_authenticode_accepts_valid_signature_from_expected_publisher(tmp_path):
    dl.verify_authenticode(tmp_path / "x.exe", "EnterpriseDB", run=lambda *a, **k: Result("Valid|CN=EnterpriseDB Corporation, O=EnterpriseDB"))


@pytest.mark.parametrize(
    ("output", "message"),
    [("NotSigned|", "invalide"), ("HashMismatch|CN=EnterpriseDB", "invalide"), ("UnknownError|", "invalide"), ("Valid|CN=Autre Éditeur", "Éditeur inattendu"), ("", "invalide")],
)
def test_authenticode_rejects_unsigned_altered_or_foreign_files(tmp_path, output, message):
    with pytest.raises(dl.DownloadError, match=message):
        dl.verify_authenticode(tmp_path / "x.exe", "EnterpriseDB", run=lambda *a, **k: Result(output))


def test_authenticode_path_with_quote_cannot_inject_commands(tmp_path):
    captured = {}

    def run(cmd, **kwargs):
        captured["script"] = cmd[-1]
        return Result("Valid|EnterpriseDB")

    dl.verify_authenticode(tmp_path / "a'; Remove-Item C:\\x; '.exe", "EnterpriseDB", run=run)
    assert "a''; Remove-Item" in captured["script"]  # l'apostrophe est doublée : la chaîne reste une seule valeur littérale


def test_real_signature_check_on_a_real_signed_binary():
    import sys
    from pathlib import Path

    signed = Path(sys.executable).with_name("python.exe")
    # python.exe (PSF) est signé : l'éditeur attendu « Python Software Foundation » doit être accepté, un autre refusé.
    try:
        dl.verify_authenticode(signed, "Python Software Foundation")
    except dl.DownloadError:
        pytest.skip("python.exe non signé dans cette distribution")
    with pytest.raises(dl.DownloadError, match="Éditeur inattendu"):
        dl.verify_authenticode(signed, "EnterpriseDB")
