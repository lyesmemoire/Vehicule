"""Résolution des chemins de ressources, compatible mode compilé PyInstaller."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def asset_path(*parts: str) -> Path:
    """Chemin absolu d'une ressource du dossier ``assets/``.

    En mode exécutable (PyInstaller), les ressources sont extraites dans
    ``sys._MEIPASS`` ; en mode source, on repart de la racine du projet.
    """
    base = (
        Path(getattr(sys, "_MEIPASS", PROJECT_ROOT))
        if getattr(sys, "frozen", False)
        else PROJECT_ROOT
    )
    return base.joinpath("assets", *parts)
