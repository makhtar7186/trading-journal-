"""Élévation de droits Windows (UAC) pour les seules opérations qui l'exigent (installer/démarrer PostgreSQL).

Le lanceur lui-même reste un programme ordinaire (sans droits administrateur).
"""
import ctypes
import sys
from ctypes import wintypes

ERROR_CANCELLED = 1223  # l'utilisateur a refusé la fenêtre UAC
SEE_MASK_NOCLOSEPROCESS = 0x00000040
SW_HIDE = 0
INFINITE = 0xFFFFFFFF


class ElevationRefused(Exception):
    """L'utilisateur a refusé la demande de droits administrateur."""


class _ShellExecuteInfo(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("fMask", ctypes.c_ulong),
        ("hwnd", wintypes.HWND),
        ("lpVerb", wintypes.LPCWSTR),
        ("lpFile", wintypes.LPCWSTR),
        ("lpParameters", wintypes.LPCWSTR),
        ("lpDirectory", wintypes.LPCWSTR),
        ("nShow", ctypes.c_int),
        ("hInstApp", wintypes.HINSTANCE),
        ("lpIDList", ctypes.c_void_p),
        ("lpClass", wintypes.LPCWSTR),
        ("hkeyClass", wintypes.HKEY),
        ("dwHotKey", wintypes.DWORD),
        ("hIcon", wintypes.HANDLE),
        ("hProcess", wintypes.HANDLE),
    ]


def is_admin() -> bool:
    if sys.platform != "win32":
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except OSError:
        return False


def run_elevated(executable: str, parameters: str = "", wait_ms: int = INFINITE, show: int = SW_HIDE) -> int:
    """Lance `executable` avec droits administrateur (fenêtre UAC) et retourne son code de sortie.

    Lève ElevationRefused si l'utilisateur refuse. Si on est déjà administrateur, aucune fenêtre n'apparaît.
    """
    info = _ShellExecuteInfo()
    info.cbSize = ctypes.sizeof(info)
    info.fMask = SEE_MASK_NOCLOSEPROCESS
    info.lpVerb = "runas"
    info.lpFile = executable
    info.lpParameters = parameters
    info.nShow = show
    if not ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(info)):
        if ctypes.GetLastError() == ERROR_CANCELLED:
            raise ElevationRefused("Demande de droits administrateur refusée.")
        raise OSError(f"Impossible de lancer {executable} (erreur {ctypes.GetLastError()}).")
    try:
        ctypes.windll.kernel32.WaitForSingleObject(info.hProcess, wait_ms)
        code = wintypes.DWORD()
        ctypes.windll.kernel32.GetExitCodeProcess(info.hProcess, ctypes.byref(code))
        return int(code.value)
    finally:
        ctypes.windll.kernel32.CloseHandle(info.hProcess)
