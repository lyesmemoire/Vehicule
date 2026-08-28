#!/usr/bin/env python3
"""Construction de l'exécutable Windows avec PyInstaller.

Utilisation (depuis la racine du projet, environnement Python 3.12+ actif) :

    pip install -r requirements.txt pyinstaller
    python scripts/build_windows.py

Résultat :
    dist/VehicleCostCalculator/VehicleCostCalculator.exe   (dossier autonome)
    ou dist/VehicleCostCalculator.exe                       (fichier unique, --onefile)

Options :
    --onefile   produit un fichier .exe unique (démarrage un peu plus lent)
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_NAME = "VehicleCostCalculator"
APP_VERSION = "1.3.0"


def check_pyinstaller() -> None:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("PyInstaller est requis :  pip install pyinstaller")
        sys.exit(1)


def build(onefile: bool) -> int:
    check_pyinstaller()
    icon = ROOT / "assets" / "icons" / "app.ico"
    version_file = ROOT / "assets" / "version_info.txt"

    args = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",                 # pas de console derrière l'interface
        f"--name={APP_NAME}",
        f"--paths={ROOT}",
        "--add-data", str(ROOT / "assets" / "icons") + ";assets/icons",
        "--add-data", str(ROOT / "assets" / "data") + ";assets/data",
        # Openpyxl est détecté automatiquement ; QtCharts fait partie de PySide6.
    ]
    if icon.exists():
        args.append(f"--icon={icon}")
    else:
        print("⚠ Icône introuvable (assets/icons/app.ico) : build sans icône.")
    if version_file.exists():
        args.append(f"--version-file={version_file}")
    if onefile:
        args.append("--onefile")
    args.append(str(ROOT / "main.py"))

    print("Exécution :", " ".join(str(a) for a in args), "\n")
    result = subprocess.run(args, cwd=ROOT, check=False)
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Windows PyInstaller")
    parser.add_argument("--onefile", action="store_true", help="fichier .exe unique")
    args = parser.parse_args()

    code = build(args.onefile)
    if code == 0:
        output = (
            ROOT / "dist" / f"{APP_NAME}.exe"
            if args.onefile
            else ROOT / "dist" / APP_NAME / f"{APP_NAME}.exe"
        )
        print(f"\n✔ Build terminé : {output}")
        print("  L'exécutable est autonome : aucun Python à installer sur le poste cible.")
        print(f"  Les données (SQLite) sont créées dans %APPDATA%\\{APP_NAME}\\ au premier lancement.")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
