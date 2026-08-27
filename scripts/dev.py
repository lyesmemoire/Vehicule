#!/usr/bin/env python3
"""Aide au développement quotidien — point d'entrée unique des tâches courantes.

Utilisation (depuis la racine du projet) :

    python scripts/dev.py run         # lancer l'application
    python scripts/dev.py test        # tests de la logique métier
    python scripts/dev.py ui-test     # test d'intégration de l'interface + captures
    python scripts/dev.py lint        # analyse statique (ruff)
    python scripts/dev.py check       # lint + tests + test d'intégration
    python scripts/dev.py catalog     # rafraîchir le catalogue marques/modèles (Internet)
    python scripts/dev.py build       # construire l'exécutable Windows (PyInstaller)
    python scripts/dev.py version     # afficher la version courante

Tout est optionnel : chaque commande reste lançable individuellement
(voir docs/DEVELOPPEMENT.md pour le détail et les recettes d'évolution).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run(cmd: list[str], env_extra: dict[str, str] | None = None) -> int:
    print("▶", " ".join(cmd))
    import os

    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    try:
        return subprocess.run(cmd, cwd=ROOT, env=env, check=False).returncode
    except FileNotFoundError as exc:
        print(f"Outil introuvable : {exc.filename}. Installez-le d'abord (voir README).")
        return 1


def cmd_test() -> int:
    return run([sys.executable, "tests/test_calculator.py"])


def cmd_ui_test() -> int:
    # Mode offscreen : fonctionne même sans écran (CI, bureau à distance…)
    return run([sys.executable, "scripts/generate_screenshots.py"],
               env_extra={"QT_QPA_PLATFORM": "offscreen"})


def cmd_lint() -> int:
    return run([sys.executable, "-m", "ruff", "check", "."])


def cmd_run() -> int:
    return run([sys.executable, "main.py"])


def cmd_catalog() -> int:
    return run([sys.executable, "scripts/update_vehicle_catalog.py"])


def cmd_build() -> int:
    return run([sys.executable, "scripts/build_windows.py"])


def cmd_version() -> int:
    from main import APP_VERSION

    print(f"VehicleCostCalculator v{APP_VERSION}")
    return 0


def cmd_check() -> int:
    code = cmd_lint()
    if code:
        return code
    code = cmd_test()
    if code:
        return code
    return cmd_ui_test()


COMMANDS = {
    "run": cmd_run,
    "test": cmd_test,
    "ui-test": cmd_ui_test,
    "lint": cmd_lint,
    "check": cmd_check,
    "catalog": cmd_catalog,
    "build": cmd_build,
    "version": cmd_version,
}


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] in {"-h", "--help", "help"}:
        print(__doc__)
        return 0
    command = COMMANDS.get(sys.argv[1])
    if command is None:
        print(f"Commande inconnue : {sys.argv[1]!r}\n")
        print(__doc__)
        return 1
    return command()


if __name__ == "__main__":
    raise SystemExit(main())
