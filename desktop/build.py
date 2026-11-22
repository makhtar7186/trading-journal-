"""Construit la version desktop : frontend Next.js, exécutables PyInstaller, assemblage, puis installateur Inno Setup.

Usage (depuis le dossier desktop/, avec l'environnement .venv Python 3.13) :
    .venv\\Scripts\\python.exe build.py            # tout
    .venv\\Scripts\\python.exe build.py --no-installer
Prérequis : Node 22, npm. L'installateur exige Inno Setup (voir tools/ ou --iscc).
"""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FRONTEND = ROOT / "frontend"
BUILD = HERE / "build"
DIST = HERE / "dist"
APP_DIST = DIST / "TradingJournal"
sys.path.insert(0, str(HERE))

from tjlauncher.version import APP_NAME, __version__  # noqa: E402


def run(cmd: list[str], cwd: Path | None = None, env: dict | None = None) -> None:
    print("  $", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run(cmd, cwd=cwd, env=env, check=True, shell=False)


def step(title: str) -> None:
    print(f"\n=== {title}", flush=True)


def make_icon() -> Path:
    """Icône générée (courbe de performance sur fond sombre) : aucune ressource externe."""
    from PIL import Image, ImageDraw

    target = HERE / "assets" / "icon.ico"
    target.parent.mkdir(exist_ok=True)
    size = 512
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((16, 16, size - 16, size - 16), radius=96, fill=(11, 15, 23, 255))
    draw.rounded_rectangle((16, 16, size - 16, size - 16), radius=96, outline=(79, 70, 229, 255), width=14)
    points = [(90, 380), (190, 300), (260, 335), (350, 190), (425, 130)]
    draw.line(points, fill=(129, 140, 248, 255), width=34, joint="curve")
    for x, y in points:
        draw.ellipse((x - 17, y - 17, x + 17, y + 17), fill=(129, 140, 248, 255))
    x, y = points[-1]
    draw.ellipse((x - 30, y - 30, x + 30, y + 30), fill=(52, 211, 153, 255), outline=(11, 15, 23, 255), width=8)
    image.save(target, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    return target


def write_version_info() -> Path:
    BUILD.mkdir(exist_ok=True)
    a, b, c = (__version__.split(".") + ["0", "0"])[:3]
    nums = f"({int(a)}, {int(b)}, {int(c)}, 0)"
    text = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={nums}, prodvers={nums}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040C04B0', [
      StringStruct('CompanyName', ''),
      StringStruct('FileDescription', '{APP_NAME}'),
      StringStruct('FileVersion', '{__version__}'),
      StringStruct('InternalName', 'TradingJournal'),
      StringStruct('OriginalFilename', 'TradingJournal.exe'),
      StringStruct('ProductName', '{APP_NAME}'),
      StringStruct('ProductVersion', '{__version__}')])]),
    VarFileInfo([VarStruct('Translation', [1036, 1200])])
  ]
)
"""
    path = BUILD / "version_info.txt"
    path.write_text(text, encoding="utf-8")
    return path


def build_frontend() -> Path:
    npm = shutil.which("npm") or "npm.cmd"
    run([npm, "ci"], cwd=FRONTEND)
    run([npm, "run", "build"], cwd=FRONTEND)
    standalone = FRONTEND / ".next" / "standalone"
    if not (standalone / "server.js").exists():
        raise SystemExit("Build Next.js standalone introuvable (output: 'standalone' dans next.config.ts).")
    target = BUILD / "frontend"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(standalone, target, ignore=shutil.ignore_patterns(".env*"))
    shutil.copytree(FRONTEND / ".next" / "static", target / ".next" / "static")
    if (FRONTEND / "public").exists():
        shutil.copytree(FRONTEND / "public", target / "public")
    return target


def find_node() -> Path:
    node = shutil.which("node")
    if not node:
        raise SystemExit("node.exe introuvable (Node 22 requis pour embarquer l'interface).")
    version = subprocess.run([node, "--version"], capture_output=True, text=True, check=True).stdout.strip()
    major = int(version.lstrip("v").split(".")[0])
    if major < 20:
        raise SystemExit(f"Node {version} trop ancien (Next.js 16 exige Node 20.9 ou plus).")
    print(f"  node {version} : {node}")
    return Path(node)


def build_executables() -> None:
    if DIST.exists():
        shutil.rmtree(DIST)
    run([sys.executable, "-m", "PyInstaller", str(HERE / "TradingJournal.spec"), "--noconfirm", "--clean",
         "--distpath", str(DIST), "--workpath", str(BUILD / "pyinstaller")], cwd=HERE)


def assemble(frontend: Path, node: Path) -> None:
    shutil.copytree(frontend, APP_DIST / "frontend")
    (APP_DIST / "node").mkdir()
    shutil.copy2(node, APP_DIST / "node" / "node.exe")
    notice = HERE / "THIRD_PARTY_NOTICES.txt"
    if notice.exists():
        shutil.copy2(notice, APP_DIST / notice.name)


def dir_size(path: Path) -> float:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) / (1024 * 1024)


def find_iscc(explicit: str | None) -> Path | None:
    candidates = [explicit, os.environ.get("ISCC"), shutil.which("iscc"), str(HERE / "tools" / "InnoSetup" / "ISCC.exe"),
                  r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe", str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe")]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return Path(candidate)
    return None


def build_installer(iscc: Path) -> Path:
    run([str(iscc), f"/DAppVersion={__version__}", f"/DSourceDir={APP_DIST}", f"/DOutputDir={DIST}", str(HERE / "installer.iss")])
    setup = DIST / f"TradingJournal-Setup-{__version__}.exe"
    digest = hashlib.sha256(setup.read_bytes()).hexdigest()
    (DIST / f"{setup.name}.sha256").write_text(f"{digest} *{setup.name}\n", encoding="ascii")
    return setup


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-installer", action="store_true")
    parser.add_argument("--iscc")
    parser.add_argument("--skip-frontend", action="store_true", help="réutilise build/frontend")
    args = parser.parse_args()

    step("Icône et informations de version")
    make_icon()
    write_version_info()
    step("Interface (Next.js standalone)")
    frontend = BUILD / "frontend" if args.skip_frontend and (BUILD / "frontend").exists() else build_frontend()
    step("Node.js embarqué")
    node = find_node()
    step("Exécutables (PyInstaller)")
    build_executables()
    step("Assemblage")
    assemble(frontend, node)
    print(f"  dossier : {APP_DIST} ({dir_size(APP_DIST):.0f} Mo)")
    if args.no_installer:
        return 0
    step("Installateur (Inno Setup)")
    iscc = find_iscc(args.iscc)
    if not iscc:
        print("  Inno Setup (ISCC.exe) introuvable : installateur non généré (voir docs/desktop.md).")
        return 0
    setup = build_installer(iscc)
    print(f"  installateur : {setup} ({setup.stat().st_size / (1024 * 1024):.0f} Mo)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
