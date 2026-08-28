"""Onglet « Historique » : tableau des simulations avec tri, filtres et actions."""

from __future__ import annotations

from datetime import date
from typing import ClassVar

from PySide6.QtCore import QAbstractTableModel, QSortFilterProxyModel, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from database.db import DatabaseError
from database.repositories import SimulationRepository
from models.simulation import Simulation
from ui.components import Panel, field_label, page_title, show_db_error
from utils.currency import format_dzd, format_money, format_number
from utils.exporter import ExportError, export_simulations_csv, export_simulations_excel


class SimulationTableModel(QAbstractTableModel):
    """Modèle de l'historique (une ligne = une simulation)."""

    SORT_ROLE = Qt.ItemDataRole.UserRole + 1

    HEADERS: ClassVar[list[str]] = [
        "Date",
        "Marque",
        "Modèle",
        "Année",
        "Prix",
        "Fret",
        "Taux",
        "Coût total (DZD)",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sims: list[Simulation] = []

    # --- données -----------------------------------------------------------
    @property
    def simulations(self) -> list[Simulation]:
        return self._sims

    def update_sims(self, sims: list[Simulation]) -> None:
        self.beginResetModel()
        self._sims = list(sims)
        self.endResetModel()

    def sim_at(self, row: int) -> Simulation | None:
        return self._sims[row] if 0 <= row < len(self._sims) else None

    # --- API Qt ------------------------------------------------------------
    def rowCount(self, parent=None):
        return 0 if parent and parent.isValid() else len(self._sims)

    def columnCount(self, parent=None):
        return len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if (
            role == Qt.ItemDataRole.DisplayRole
            and orientation == Qt.Orientation.Horizontal
            and 0 <= section < len(self.HEADERS)
        ):
            return self.HEADERS[section]
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        sim = self._sims[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            return self._display_text(sim, col)
        if role == self.SORT_ROLE:
            return self._sort_key(sim, col)
        if role == Qt.ItemDataRole.TextAlignmentRole and col in (3, 4, 5, 6, 7):
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if role == Qt.ItemDataRole.ForegroundRole and col == 7:
            return QColor("#15803d")
        return None

    @staticmethod
    def _display_text(sim: Simulation, col: int) -> str:
        # Harmonisation : tous les montants du tableau à 2 décimales ;
        # prix/fret affichés dans la devise de la simulation.
        if col == 0:
            return sim.date.strftime("%d/%m/%Y")
        if col == 1:
            return sim.marque
        if col == 2:
            return sim.modele
        if col == 3:
            return str(sim.annee)
        if col == 4:
            return format_money(sim.prix_usd, sim.devise, 2)
        if col == 5:
            return format_money(sim.fret_usd, sim.devise, 2)
        if col == 6:
            return format_number(sim.taux_change, 2)
        if col == 7:
            return format_dzd(sim.cout_total, 2)
        return ""

    @staticmethod
    def _sort_key(sim: Simulation, col: int):
        if col == 0:
            return sim.date.isoformat()
        if col == 1:
            return sim.marque.lower()
        if col == 2:
            return sim.modele.lower()
        if col == 3:
            return sim.annee
        if col == 4:
            return float(sim.prix_usd)
        if col == 5:
            return float(sim.fret_usd)
        if col == 6:
            return float(sim.taux_change)
        return float(sim.cout_total)


class SimulationFilterProxy(QSortFilterProxyModel):
    """Filtre : recherche marque / modèle (contient) + filtre année exacte."""

    def __init__(self, source: SimulationTableModel, parent=None):
        super().__init__(parent)
        self.setSourceModel(source)
        self.setSortRole(SimulationTableModel.SORT_ROLE)
        self._marque = ""
        self._modele = ""
        self._annee: int | None = None

    def set_filters(self, marque: str, modele: str, annee: int | None) -> None:
        self._marque = marque.strip().lower()
        self._modele = modele.strip().lower()
        self._annee = annee
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent) -> bool:
        sims = self.sourceModel().simulations
        if not (0 <= source_row < len(sims)):
            return False
        sim = sims[source_row]
        if self._marque and self._marque not in sim.marque.lower():
            return False
        if self._modele and self._modele not in sim.modele.lower():
            return False
        return self._annee is None or sim.annee == self._annee


class HistoryPage(QWidget):
    """Onglet « Historique »."""

    simulation_activated = Signal(int)  # id de la simulation à ouvrir

    def __init__(self, sim_repo: SimulationRepository, parent=None):
        super().__init__(parent)
        self.sim_repo = sim_repo

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        # --- En-tête -----------------------------------------------------
        header = QHBoxLayout()
        header.addWidget(page_title("Historique des simulations"))
        header.addStretch(1)
        root.addLayout(header)

        # --- Barre de filtres --------------------------------------------
        filter_panel = Panel()
        filter_layout = QHBoxLayout(filter_panel)
        filter_layout.setContentsMargins(14, 10, 14, 10)
        filter_layout.setSpacing(10)

        filter_layout.addWidget(field_label("Marque contient :"))
        self.search_marque = QLineEdit()
        self.search_marque.setPlaceholderText("ex : Livan")
        self.search_marque.setClearButtonEnabled(True)
        filter_layout.addWidget(self.search_marque, stretch=2)

        filter_layout.addWidget(field_label("Modèle contient :"))
        self.search_modele = QLineEdit()
        self.search_modele.setPlaceholderText("ex : X3 Pro")
        self.search_modele.setClearButtonEnabled(True)
        filter_layout.addWidget(self.search_modele, stretch=2)

        filter_layout.addWidget(field_label("Année :"))
        self.filter_annee = QComboBox()
        self.filter_annee.setMinimumWidth(150)
        filter_layout.addWidget(self.filter_annee, stretch=1)

        self.btn_refresh = QPushButton("Actualiser")
        self.btn_refresh.clicked.connect(self.refresh)
        filter_layout.addWidget(self.btn_refresh)
        root.addWidget(filter_panel)

        # --- Barre d'actions ----------------------------------------------
        actions = QHBoxLayout()
        self.btn_open = QPushButton("Ouvrir / Modifier")
        self.btn_open.setObjectName("primary")
        self.btn_open.clicked.connect(self._open_selected)

        self.btn_duplicate = QPushButton("Dupliquer")
        self.btn_duplicate.clicked.connect(self._duplicate_selected)

        self.btn_delete = QPushButton("Supprimer")
        self.btn_delete.setObjectName("danger")
        self.btn_delete.clicked.connect(self._delete_selected)

        self.btn_export_csv = QPushButton("Export CSV")
        self.btn_export_csv.setToolTip("Exporte les lignes actuellement affichées.")
        self.btn_export_csv.clicked.connect(lambda: self._export("csv"))

        self.btn_export_excel = QPushButton("Export Excel")
        self.btn_export_excel.setToolTip("Exporte les lignes actuellement affichées.")
        self.btn_export_excel.clicked.connect(lambda: self._export("excel"))

        actions.addWidget(self.btn_open)
        actions.addWidget(self.btn_duplicate)
        actions.addWidget(self.btn_delete)
        actions.addSpacing(12)
        actions.addWidget(self.btn_export_csv)
        actions.addWidget(self.btn_export_excel)
        actions.addStretch(1)
        self.count_label = QLabel("")
        self.count_label.setObjectName("countLabel")
        actions.addWidget(self.count_label)
        root.addLayout(actions)

        # --- Tableau ---------------------------------------------------------
        self.model = SimulationTableModel(self)
        self.proxy = SimulationFilterProxy(self.model)
        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header_view.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        for col, width in ((0, 110), (3, 70), (4, 105), (5, 105), (6, 120), (7, 165)):
            header_view.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
            self.table.setColumnWidth(col, width)
        header_view.setStretchLastSection(False)
        self.table.sortByColumn(0, Qt.SortOrder.DescendingOrder)
        self.table.doubleClicked.connect(lambda _index: self._open_selected())
        root.addWidget(self.table, stretch=1)

        # --- Signaux ------------------------------------------------------
        self.search_marque.textChanged.connect(self._apply_filters)
        self.search_modele.textChanged.connect(self._apply_filters)
        self.filter_annee.currentIndexChanged.connect(self._apply_filters)
        self.table.selectionModel().selectionChanged.connect(lambda *_: self._update_buttons())

        self._update_buttons()
        self.refresh(quiet=True)  # à l'ouverture : pas de dialogue modal

    # ------------------------------------------------------------------ filtres

    def _apply_filters(self) -> None:
        annee = self.filter_annee.currentData()
        self.proxy.set_filters(
            marque=self.search_marque.text(),
            modele=self.search_modele.text(),
            annee=annee,
        )
        self._update_count()
        self._update_buttons()

    # ------------------------------------------------------------------ actions

    def refresh(self, quiet: bool = False) -> None:
        """Recharge l'historique depuis la base (conserve filtres et tri).

        ``quiet=True`` (utilisé à l'ouverture de la fenêtre) : une erreur de
        base de données n'ouvre pas de boîte de dialogue modale, elle se
        contente d'afficher l'état vide.
        """
        try:
            sims = self.sim_repo.list_all()
        except DatabaseError as exc:
            if quiet:
                self.count_label.setText("Base de données indisponible")
                return
            show_db_error(self, exc)
            return
        self.model.update_sims(sims)

        # Recharge les années disponibles en conservant la sélection
        current = self.filter_annee.currentData()
        self.filter_annee.blockSignals(True)
        self.filter_annee.clear()
        self.filter_annee.addItem("Toutes les années", None)
        for year in sorted({sim.annee for sim in sims}, reverse=True):
            self.filter_annee.addItem(str(year), year)
        if current is not None:
            index = self.filter_annee.findData(current)
            if index >= 0:
                self.filter_annee.setCurrentIndex(index)
        self.filter_annee.blockSignals(False)

        self._apply_filters()

    def _selected_sim(self) -> Simulation | None:
        indexes = self.table.selectionModel().selectedRows()
        if not indexes:
            return None
        source_index = self.proxy.mapToSource(indexes[0])
        return self.model.sim_at(source_index.row())

    def _open_selected(self) -> None:
        sim = self._selected_sim()
        if sim is None:
            QMessageBox.information(
                self, "Aucune sélection", "Veuillez sélectionner une simulation dans le tableau."
            )
            return
        self.simulation_activated.emit(sim.id)

    def _duplicate_selected(self) -> None:
        sim = self._selected_sim()
        if sim is None:
            QMessageBox.information(
                self, "Aucune sélection", "Veuillez sélectionner une simulation à dupliquer."
            )
            return
        copy = sim.duplicate(date.today())
        try:
            new_id = self.sim_repo.save(copy)
        except DatabaseError as exc:
            show_db_error(self, exc)
            return
        self.refresh()
        QMessageBox.information(
            self,
            "Simulation dupliquée",
            f"La simulation {sim.label} a été dupliquée.\n"
            f"Nouvelle entrée n° {new_id} (date du jour).",
        )

    def _delete_selected(self) -> None:
        sim = self._selected_sim()
        if sim is None:
            QMessageBox.information(
                self, "Aucune sélection", "Veuillez sélectionner une simulation à supprimer."
            )
            return
        box = QMessageBox(self)
        box.setWindowTitle("Confirmer la suppression")
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText(
            f"Supprimer définitivement la simulation n° {sim.id} ?\n\n"
            f"{sim.label} — {sim.date.strftime('%d/%m/%Y')} — {format_dzd(sim.cout_total)}"
        )
        btn_delete = box.addButton("Supprimer", QMessageBox.ButtonRole.DestructiveRole)
        box.addButton("Annuler", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is not btn_delete:
            return
        try:
            self.sim_repo.delete(sim.id)
        except DatabaseError as exc:
            show_db_error(self, exc)
            return
        self.refresh()

    def _export(self, kind: str) -> None:
        sims = [
            self.model.sim_at(self.proxy.mapToSource(self.proxy.index(row, 0)).row())
            for row in range(self.proxy.rowCount())
        ]
        sims = [sim for sim in sims if sim is not None]
        if not sims:
            QMessageBox.information(
                self, "Rien à exporter", "Aucune simulation ne correspond aux filtres actuels."
            )
            return
        if kind == "csv":
            path, _ = QFileDialog.getSaveFileName(
                self, "Exporter l'historique (CSV)", "historique_simulations.csv",
                "Fichier CSV (*.csv)",
            )
        else:
            path, _ = QFileDialog.getSaveFileName(
                self, "Exporter l'historique (Excel)", "historique_simulations.xlsx",
                "Classeur Excel (*.xlsx)",
            )
        if not path:
            return
        try:
            if kind == "csv" and not path.lower().endswith(".csv"):
                path += ".csv"
            if kind == "excel" and not path.lower().endswith(".xlsx"):
                path += ".xlsx"
            if kind == "csv":
                export_simulations_csv(path, sims)
            else:
                export_simulations_excel(path, sims)
        except (ExportError, OSError) as exc:
            QMessageBox.critical(self, "Export impossible", str(exc))
            return
        QMessageBox.information(
            self, "Export réussi",
            f"{len(sims)} simulation(s) exportée(s) vers :\n{path}",
        )

    # ------------------------------------------------------------------ affichage

    def _update_count(self) -> None:
        visible = self.proxy.rowCount()
        total = self.model.rowCount()
        self.count_label.setText(
            f"{visible} simulation(s) affichée(s) — {total} au total"
            if visible != total
            else f"{total} simulation(s)"
        )

    def _update_buttons(self) -> None:
        has_selection = self._selected_sim() is not None
        for button in (self.btn_open, self.btn_duplicate, self.btn_delete):
            button.setEnabled(has_selection)
