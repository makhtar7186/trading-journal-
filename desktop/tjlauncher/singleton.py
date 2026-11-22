"""Instance unique : une seconde exécution ouvre simplement le navigateur au lieu de relancer les serveurs."""
import ctypes
import sys

ERROR_ALREADY_EXISTS = 183


class SingleInstance:
    def __init__(self, name: str = "Local\\TradingJournalLauncher") -> None:
        self.already_running = False
        self._handle = None
        if sys.platform != "win32":
            return
        kernel32 = ctypes.windll.kernel32
        kernel32.SetLastError(0)
        self._handle = kernel32.CreateMutexW(None, False, name)
        self.already_running = ctypes.GetLastError() == ERROR_ALREADY_EXISTS

    def release(self) -> None:
        if self._handle:
            ctypes.windll.kernel32.CloseHandle(self._handle)
            self._handle = None
