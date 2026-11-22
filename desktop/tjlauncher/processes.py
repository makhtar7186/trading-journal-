"""Processus enfants (API Django + interface Next.js) : démarrage, surveillance, arrêt propre.

Les enfants sont placés dans un « job » Windows : si le lanceur est fermé de force ou plante, Windows les termine
aussi (aucun serveur orphelin qui garderait un port occupé).
"""
from __future__ import annotations

import ctypes
import subprocess
import sys
from ctypes import wintypes
from pathlib import Path

from . import net, paths, runtime
from .config import Config

CREATE_NO_WINDOW = 0x08000000
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
JobObjectExtendedLimitInformation = 9


class _BasicLimit(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class _IoCounters(ctypes.Structure):
    _fields_ = [(n, ctypes.c_uint64) for n in ("ReadOps", "WriteOps", "OtherOps", "ReadBytes", "WriteBytes", "OtherBytes")]


class _ExtendedLimit(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _BasicLimit),
        ("IoInfo", _IoCounters),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


class KillOnCloseJob:
    """Job Windows qui termine tous ses processus quand le lanceur disparaît (même brutalement)."""

    def __init__(self) -> None:
        self.handle = None
        if sys.platform != "win32":
            return
        kernel32 = ctypes.windll.kernel32
        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        self.handle = kernel32.CreateJobObjectW(None, None)
        if not self.handle:
            return
        info = _ExtendedLimit()
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        kernel32.SetInformationJobObject(self.handle, JobObjectExtendedLimitInformation, ctypes.byref(info), ctypes.sizeof(info))

    def add(self, process: subprocess.Popen) -> bool:
        if not self.handle:
            return False
        return bool(ctypes.windll.kernel32.AssignProcessToJobObject(self.handle, wintypes.HANDLE(int(process._handle))))  # noqa: SLF001


class StackError(Exception):
    pass


class Stack:
    """Les deux serveurs de l'application."""

    def __init__(self, cfg: Config, popen=subprocess.Popen, job: KillOnCloseJob | None = None) -> None:
        self.cfg = cfg
        self._popen = popen
        self.job = job or KillOnCloseJob()
        self.api: subprocess.Popen | None = None
        self.ui: subprocess.Popen | None = None

    # -- commandes ---------------------------------------------------------------------------------
    def api_command(self) -> list[str]:
        return [*paths.cli_exe(), "serve-api"]

    def ui_command(self) -> list[str]:
        return [str(paths.node_exe()), str(paths.frontend_dir() / "server.js")]

    def ui_env(self, base: dict | None = None) -> dict:
        import os

        env = dict(base if base is not None else os.environ)
        env.update(
            {
                "PORT": str(self.cfg.ui_port),
                "HOSTNAME": "127.0.0.1",  # jamais 0.0.0.0 : l'application n'est pas exposée au réseau
                "BACKEND_INTERNAL_URL": self.cfg.api_url,
                "NODE_ENV": "production",
                "NEXT_TELEMETRY_DISABLED": "1",
            }
        )
        # Aucun secret du backend n'est transmis à l'interface.
        for name in list(env):
            if name.startswith(("DJANGO_", "POSTGRES_", "DB_ENGINE", "SQLITE_")):
                env.pop(name)
        return env

    # -- cycle de vie ------------------------------------------------------------------------------
    def _spawn(self, command: list[str], env: dict, log_name: str, cwd: Path | None) -> subprocess.Popen:
        log = open(paths.logs_dir() / log_name, "ab")  # noqa: SIM115 (fermé à l'arrêt du processus)
        process = self._popen(command, env=env, cwd=str(cwd) if cwd else None, stdout=log, stderr=subprocess.STDOUT,
                              stdin=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
        self.job.add(process)
        return process

    def start(self) -> None:
        if not paths.frontend_dir().joinpath("server.js").exists():
            raise StackError(f"Interface introuvable : {paths.frontend_dir() / 'server.js'}")
        self.api = self._spawn(self.api_command(), runtime.backend_env(self.cfg), "api-process.log", None)
        self.ui = self._spawn(self.ui_command(), self.ui_env(), "ui-process.log", paths.frontend_dir())

    def wait_healthy(self, timeout: float = 90.0) -> None:
        api_ok = net.wait_until(lambda: self._alive(self.api) and net.http_ok(f"{self.cfg.api_url}/api/v1/health/"), timeout)
        if not api_ok:
            raise StackError(self._failure("Le serveur de l'application ne répond pas", self.api, "api-process.log"))
        ui_ok = net.wait_until(lambda: self._alive(self.ui) and net.http_ok(f"{self.cfg.ui_url}/login"), timeout)
        if not ui_ok:
            raise StackError(self._failure("L'interface ne répond pas", self.ui, "ui-process.log"))

    @staticmethod
    def _alive(process: subprocess.Popen | None) -> bool:
        return process is not None and process.poll() is None

    @staticmethod
    def _failure(message: str, process: subprocess.Popen | None, log_name: str) -> str:
        code = process.poll() if process else None
        detail = f" (le processus s'est arrêté, code {code})" if code is not None else ""
        return f"{message}{detail}. Journal : {paths.logs_dir() / log_name}"

    def is_running(self) -> bool:
        return self._alive(self.api) and self._alive(self.ui)

    def stop(self, grace: float = 6.0) -> None:
        for process in (self.ui, self.api):
            if process is None or process.poll() is not None:
                continue
            process.terminate()
        for process in (self.ui, self.api):
            if process is None:
                continue
            try:
                process.wait(timeout=grace)
            except subprocess.TimeoutExpired:
                process.kill()
        self.api = self.ui = None
