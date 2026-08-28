"""Fenêtre principale : onglets + avertissement permanent."""

from __future__ import annotations

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QFrame, QLabel, QMainWindow, QTabWidget, QVBoxLayout, QWidget

from database.db import DatabaseError, get_db_path
from database.repositories import CatalogRepository, SettingsRepository, SimulationRepository
from ui.calculator_page import CalculatorPage
from ui.components import DISCLAIMER_TEXT, show_db_error
from ui.history_page import HistoryPage
from ui.price_history_page import PriceHistoryPage
from ui.settings_page import SettingsPage

TAB_CALC = 0
TAB_HISTORY = 1
TAB_EVOLUTION = 2
TAB_SETTINGS = 3


class MainWindow(QMainWindow):
    """Fenêtre principale 1200 × 750 (taille minimale 1024 × 660)."""

    def __init__(self, version: str = "1.0.0", parent=None):
        super().__init__(parent)
        self.setWindowTitle(
            f"Calculateur de coût de revient — Véhicules importés (Algérie)   v{version}"
        )
        self.resize(1200, 750)
        self.setMinimumSize(1024, 660)

        self.settings_repo = SettingsRepository()
        self.catalog_repo = CatalogRepository()
        self.sim_repo = SimulationRepository()

        central = QWidget()
        central.setObjectName("pageRoot")
        layout = QVBoxLayout(central)
        layout.setContentsMargins(12, 12, 12, 10)
        layout.setSpacing(10)

        self.tabs = QTabWidget()
        self.calc_page = CalculatorPage(self.settings_repo, self.catalog_repo, self.sim_repo)
        self.history_page = HistoryPage(self.sim_repo)
        self.evolution_page = PriceHistoryPage(self.sim_repo)
        self.settings_page = SettingsPage(self.settings_repo)
        self.tabs.addTab(self.calc_page, "Calculateur")
        self.tabs.addTab(self.history_page, "Historique")
        self.tabs.addTab(self.evolution_page, "Évolution des prix")
        self.tabs.addTab(self.settings_page, "Paramètres")
        layout.addWidget(self.tabs, stretch=1)

        # Avertissement permanent (règles fiscales = paramètres utilisateur)
        disclaimer = QFrame()
        disclaimer.setObjectName("disclaimerBar")
        disclaimer_layout = QVBoxLayout(disclaimer)
        disclaimer_layout.setContentsMargins(12, 6, 12, 6)
        disclaimer_label = QLabel(DISCLAIMER_TEXT)
        disclaimer_label.setObjectName("disclaimerLabel")
        disclaimer_label.setWordWrap(True)
        disclaimer_layout.addWidget(disclaimer_label)
        layout.addWidget(disclaimer)

        self.setCentralWidget(central)

        # Barre d'état : rappel de l'emplacement des données locales
        self.statusBar().showMessage(f"Base de données locale : {get_db_path()}")

        # Restauration de la géométrie de fenêtre et du dernier onglet utilisé
        self.app_settings = QSettings("VehicleCostCalculator", "VehicleCostCalculator")
        geometry = self.app_settings.value("window/geometry")
        if geometry:
            self.restoreGeometry(geometry)
        last_tab = self.app_settings.value("window/last_tab", TAB_CALC, type=int)
        if 0 <= last_tab < self.tabs.count():
            self.tabs.setCurrentIndex(last_tab)

        # --- Câblage des pages -----------------------------------------------
        self.calc_page.simulation_saved.connect(self._refresh_data_pages)
        self.history_page.simulation_activated.connect(self._open_simulation)
        self.settings_page.settings_saved.connect(self.calc_page.on_settings_changed)
        self.settings_page.database_restored.connect(self._on_database_restored)
        self.tabs.currentChanged.connect(self._on_tab_changed)

    # ------------------------------------------------------------------ actions

    def _open_simulation(self, sim_id: int) -> None:
        """Réouvre une simulation de l'historique dans le calculateur."""
        try:
            sim = self.sim_repo.get(sim_id)
        except DatabaseError as exc:
            show_db_error(self, exc)
            return
        if sim is None:
            show_db_error(self, DatabaseError(f"La simulation n° {sim_id} est introuvable."))
            return
        self.calc_page.load_for_edit(sim)
        self.tabs.setCurrentIndex(TAB_CALC)

    def _refresh_data_pages(self) -> None:
        """Met à jour Historique et Évolution après enregistrement."""
        self.history_page.refresh()
        self.evolution_page.refresh()

    def _on_database_restored(self) -> None:
        """Après restauration d'une sauvegarde : réaligne toute l'interface."""
        self.calc_page.reset_clicked(silent=True)  # contexte de données changé
        self.calc_page.on_settings_changed()
        self.history_page.refresh()
        self.evolution_page.refresh()

    def _on_tab_changed(self, index: int) -> None:
        widget = self.tabs.widget(index)
        if widget is self.history_page:
            self.history_page.refresh()
        elif widget is self.evolution_page:
            self.evolution_page.refresh()

    def closeEvent(self, event) -> None:
        """Mémorise la géométrie et l'onglet courant avant fermeture."""
        self.app_settings.setValue("window/geometry", self.saveGeometry())
        self.app_settings.setValue("window/last_tab", self.tabs.currentIndex())
        super().closeEvent(event)
