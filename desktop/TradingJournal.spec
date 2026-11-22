# -*- mode: python ; coding: utf-8 -*-
"""Spécification PyInstaller. Deux exécutables partageant le même dossier (onedir) :
- TradingJournal.exe : sans console (interface graphique)
- tjctl.exe          : avec console (sous-commandes, serveurs enfants du lanceur)
Le frontend (Next.js standalone) et node.exe sont ajoutés à côté par build.py.
"""
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

HERE = Path(SPECPATH)
BACKEND = HERE.parent / "backend"
# collect_submodules() importe réellement les paquets : le backend et le lanceur doivent être sur sys.path
# AVANT la collecte (pathex d'Analysis n'agit qu'après).
sys.path[:0] = [str(HERE), str(BACKEND)]

datas, binaries, hiddenimports = [], [], []

# Code Django du projet : chargé par NOM (INSTALLED_APPS, ROOT_URLCONF, migrations) donc invisible pour l'analyse statique.
for package in ("config", "apps", "core", "tjlauncher"):
    hiddenimports += collect_submodules(package)

# Dépendances dotées de modèles HTML, fichiers statiques, locales ou bibliothèques natives.
for package in ("rest_framework", "drf_spectacular", "django_filters", "corsheaders", "psycopg", "psycopg_binary", "waitress"):
    d, b, h = collect_all(package)
    datas += d
    binaries += b
    hiddenimports += h
datas += collect_data_files("django")
datas += collect_data_files("tzdata")  # indispensable sous Windows : zoneinfo n'a pas de base de fuseaux système
hiddenimports += ["django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions",
                  "django.contrib.messages", "django.contrib.staticfiles", "django.db.backends.postgresql", "zoneinfo"]

a = Analysis(
    ["launcher_entry.py"],
    pathex=[str(HERE), str(BACKEND)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["boto3", "botocore", "moto", "pytest", "factory", "unittest.mock_unused", "IPython", "matplotlib", "numpy", "pandas"],
    noarchive=False,
)
pyz = PYZ(a.pure)

gui = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="TradingJournal",
    console=False,
    icon=str(HERE / "assets" / "icon.ico"),
    version=str(HERE / "build" / "version_info.txt"),
    upx=False,  # UPX augmente les faux positifs antivirus
)
cli = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="tjctl",
    console=True,
    icon=str(HERE / "assets" / "icon.ico"),
    version=str(HERE / "build" / "version_info.txt"),
    upx=False,
)
coll = COLLECT(gui, cli, a.binaries, a.datas, strip=False, upx=False, name="TradingJournal")
