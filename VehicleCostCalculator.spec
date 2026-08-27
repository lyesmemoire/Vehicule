# -*- mode: python ; coding: utf-8 -*-
# Fichier .spec PyInstaller pour VehicleCostCalculator.
#
# Utilisation (Windows, depuis la racine du projet) :
#     pip install pyinstaller
#     pyinstaller VehicleCostCalculator.spec
#
# Ou simplement :  python scripts/build_windows.py

import os
from pathlib import Path

ROOT = Path(SPECPATH)  # racine du projet (dossier du .spec)

block_cipher = None


a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        # Ressources embarquées : icônes + catalogue véhicules (marques/modèles)
        (str(ROOT / "assets" / "icons"), "assets/icons"),
        (str(ROOT / "assets" / "data"), "assets/data"),
    ],
    hiddenimports=[
        # Openpyxl : sous-modules parfois non détectés automatiquement
        "openpyxl",
        "openpyxl.styles",
        "openpyxl.utils",
        # QtCharts fait partie de PySide6 mais n'est pas toujours détecté
        "PySide6.QtCharts",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "numpy",
        "pytest",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="VehicleCostCalculator",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(ROOT / "assets" / "icons" / "app.ico")
    if (ROOT / "assets" / "icons" / "app.ico").exists()
    else None,
    version=str(ROOT / "assets" / "version_info.txt")
    if (ROOT / "assets" / "version_info.txt").exists()
    else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="VehicleCostCalculator",
)
