"""Point d'entrée des exécutables (TradingJournal.exe et tjlauncher console tjctl.exe)."""
import multiprocessing
import sys

from tjlauncher.main import main

if __name__ == "__main__":
    multiprocessing.freeze_support()  # requis pour les exécutables PyInstaller
    sys.exit(main())
