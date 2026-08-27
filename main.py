"""Point d'entrée de l'application VehicleCostCalculator.

Lancement en mode source (depuis le dossier du projet) :
    python main.py
"""

from __future__ import annotations

import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

APP_VERSION = "1.2.0"  # v1.2 : rubans marque/modèle + catalogue téléchargé


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("VehicleCostCalculator")
    app.setOrganizationName("VehicleCostCalculator")
    app.setApplicationDisplayName("Calculateur de coût de revient")

    # Icône + style (imports après création de QApplication)
    from utils.paths import asset_path

    icon_file = asset_path("icons", "app.png")
    if icon_file.exists():
        app.setWindowIcon(QIcon(str(icon_file)))

    from ui.styles import APP_STYLESHEET

    app.setStyleSheet(APP_STYLESHEET)

    # Base de données locale (créée automatiquement au premier démarrage)
    from database.db import DatabaseError, init_database

    try:
        init_database()
    except DatabaseError as exc:
        QMessageBox.critical(
            None,
            "Erreur de base de données",
            "Impossible d'initialiser la base de données locale.\n\n"
            f"{exc}\n\nL'application va se fermer.",
        )
        return 1

    from ui.main_window import MainWindow

    window = MainWindow(version=APP_VERSION)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
