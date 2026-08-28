"""Onglet « Calculateur » : saisie du véhicule et calcul du coût de revient.

La page ne contient aucune formule financière : tout est délégué à
``services/calculator.py``.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDateEdit,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from database.db import DatabaseError
from database.repositories import CatalogRepository, SettingsRepository, SimulationRepository
from models.simulation import Simulation
from models.vehicle import Vehicle
from services import vehicle_catalog
from services.calculator import (
    DEVISE_FREIGHT_KEYS,
    DEVISE_RATE_FALLBACKS,
    DEVISE_RATE_KEYS,
    CalculationParams,
    SimulationResult,
    compute_cost,
)
from ui.components import (
    CYLINDER_PATTERN,
    MONEY_PATTERN,
    RATE_PATTERN,
    Panel,
    attach_decimal_validator,
    field_label,
    h_line,
    hint_label,
    section_title,
    show_db_error,
)
from utils.currency import decimal_to_str, format_dzd, format_percent, parse_decimal
from utils.exporter import (
    ExportError,
    export_simulations_csv,
    export_simulations_excel,
    simulation_summary_text,
)
from utils.validators import ValidationError, validate_simulation_input

_RESULT_ROWS = [
    ("prix_dzd", "Prix véhicule (DZD)"),
    ("fret_dzd", "Fret (DZD)"),
    ("valeur_douaniere", "Valeur douanière"),
    ("taux_douane", "Taux douanier appliqué"),
    ("droits_douane", "Droits de douane"),
    ("base_tva", "Base TVA"),
    ("tva", "TVA"),
    ("frais_transitaire", "Frais transitaire"),
    ("frais_portuaires", "Frais portuaires"),
    ("taxe_vehicule", "Taxe véhicule"),
]


class CalculatorPage(QWidget):
    """Partie gauche : saisie — partie droite : résultat détaillé."""

    simulation_saved = Signal()

    def __init__(
        self,
        settings_repo: SettingsRepository,
        catalog_repo: CatalogRepository,
        sim_repo: SimulationRepository,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.settings_repo = settings_repo
        self.catalog_repo = catalog_repo
        self.sim_repo = sim_repo

        self._last_result: SimulationResult | None = None
        self._editing_id: int | None = None
        self._updating = False  # évite les recalcs pendant une programmation de champs
        self._default_taux = parse_decimal("250")
        self._default_taux_fret = parse_decimal("250")
        self._default_taxe = parse_decimal("0")

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)
        root.addWidget(self._build_left_panel(), stretch=0)
        root.addWidget(self._build_right_panel(), stretch=1)

        self._load_catalog(keep_marque="", keep_modele="")
        self.on_settings_changed(first_load=True)
        self.reset_clicked(silent=True)

    # ------------------------------------------------------------------ UI

    def _build_left_panel(self) -> QWidget:
        panel = Panel()
        panel.setFixedWidth(430)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        layout.addWidget(section_title("Informations du véhicule"))

        self.marque_cb = QComboBox()
        self.marque_cb.setEditable(True)
        self.marque_cb.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.marque_cb.setObjectName("ribbon")
        self.marque_cb.lineEdit().setPlaceholderText("ex : Livan, Kia, Geely…")

        self.modele_cb = QComboBox()
        self.modele_cb.setEditable(True)
        self.modele_cb.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.modele_cb.setObjectName("ribbon")
        self.modele_cb.lineEdit().setPlaceholderText("ex : X3 Pro, Picanto…")

        current_year = QDate.currentDate().year()
        self.annee_sp = QSpinBox()
        self.annee_sp.setRange(1950, current_year + 2)
        self.annee_sp.setValue(current_year)

        self.cylindree_edit = QLineEdit()
        self.cylindree_edit.setPlaceholderText("ex : 1.5")
        attach_decimal_validator(self.cylindree_edit, CYLINDER_PATTERN)

        self.devise_cb = QComboBox()
        self.devise_cb.setObjectName("ribbon")
        self.devise_cb.addItems(list(DEVISE_RATE_FALLBACKS))
        self.devise_cb.setCurrentText("USD")

        self.prix_edit = QLineEdit()
        self.prix_edit.setPlaceholderText("ex : 7500")
        attach_decimal_validator(self.prix_edit, MONEY_PATTERN)

        self.fret_edit = QLineEdit()
        self.fret_edit.setPlaceholderText("ex : 1700")
        attach_decimal_validator(self.fret_edit, MONEY_PATTERN)

        self.taux_edit = QLineEdit()
        self.taux_edit.setPlaceholderText("ex : 250 (parallèle)")
        attach_decimal_validator(self.taux_edit, RATE_PATTERN)

        self.taux_fret_edit = QLineEdit()
        self.taux_fret_edit.setPlaceholderText("vide = identique au taux d'achat")
        attach_decimal_validator(self.taux_fret_edit, RATE_PATTERN)

        self.taxe_edit = QLineEdit()
        self.taxe_edit.setPlaceholderText("ex : 25000 — vide ou 0 si aucune")
        attach_decimal_validator(self.taxe_edit, MONEY_PATTERN)

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd/MM/yyyy")

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        form.addRow(field_label("Marque"), self.marque_cb)
        form.addRow(field_label("Modèle"), self.modele_cb)
        form.addRow(field_label("Année"), self.annee_sp)
        form.addRow(field_label("Cylindrée (L)"), self.cylindree_edit)
        self.prix_label = field_label("Prix véhicule (USD)")
        self.fret_label = field_label("Fret (USD)")
        self.taux_label = field_label("Taux achat (DA/USD)")
        self.taux_fret_label = field_label("Taux fret (DA/USD)")
        form.addRow(field_label("Devise"), self.devise_cb)
        form.addRow(self.prix_label, self.prix_edit)
        form.addRow(self.fret_label, self.fret_edit)
        form.addRow(self.taux_label, self.taux_edit)
        form.addRow(self.taux_fret_label, self.taux_fret_edit)
        form.addRow(field_label("Taxe véhicule (DZD)"), self.taxe_edit)
        form.addRow(field_label("Date de la simulation"), self.date_edit)
        layout.addLayout(form)

        self.editing_label = QLabel("")
        self.editing_label.setObjectName("warnLabel")
        self.editing_label.setWordWrap(True)
        self.editing_label.hide()
        layout.addWidget(self.editing_label)

        self.btn_calculer = QPushButton("Calculer")
        self.btn_calculer.setObjectName("primary")
        self.btn_calculer.setMinimumHeight(40)
        self.btn_calculer.clicked.connect(self.compute_clicked)

        self.btn_enregistrer = QPushButton("Enregistrer")
        self.btn_enregistrer.setObjectName("success")
        self.btn_enregistrer.clicked.connect(self.save_clicked)

        self.btn_reinit = QPushButton("Réinitialiser")
        self.btn_reinit.clicked.connect(lambda: self.reset_clicked())

        actions_row = QHBoxLayout()
        actions_row.addWidget(self.btn_enregistrer)
        actions_row.addWidget(self.btn_reinit)
        layout.addWidget(self.btn_calculer)
        layout.addLayout(actions_row)

        export_row = QHBoxLayout()
        self.btn_copy = QPushButton("Copier le résultat")
        self.btn_copy.clicked.connect(self.copy_result)
        self.btn_csv = QPushButton("Export CSV")
        self.btn_csv.clicked.connect(lambda: self._export("csv"))
        self.btn_excel = QPushButton("Export Excel")
        self.btn_excel.clicked.connect(lambda: self._export("excel"))
        export_row.addWidget(self.btn_copy)
        export_row.addWidget(self.btn_csv)
        export_row.addWidget(self.btn_excel)
        layout.addLayout(export_row)

        self.status_label = hint_label("Renseignez les champs puis cliquez sur « Calculer ».")
        self.status_label.setObjectName("statusLabel")
        layout.addSpacing(4)
        layout.addWidget(self.status_label)
        layout.addStretch(1)

        # Raccourcis clavier : Ctrl+Entrée = calculer, Ctrl+S = enregistrer
        self.btn_calculer.setShortcut("Ctrl+Return")
        self.btn_enregistrer.setShortcut("Ctrl+S")

        # Recalcul automatique (silencieux) dès qu'un champ change
        self.marque_cb.currentTextChanged.connect(self._on_brand_changed)
        self.modele_cb.currentTextChanged.connect(self._on_input_changed)
        self.annee_sp.valueChanged.connect(self._on_input_changed)
        self.devise_cb.currentTextChanged.connect(self._on_devise_changed)
        for edit in (self.cylindree_edit, self.prix_edit, self.fret_edit, self.taux_edit,
                     self.taux_fret_edit, self.taxe_edit):
            edit.textChanged.connect(self._on_input_changed)
            edit.returnPressed.connect(self.compute_clicked)  # Entrée = calculer
        self.date_edit.dateChanged.connect(self._on_input_changed)
        return panel

    def _build_right_panel(self) -> QWidget:
        panel = Panel()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(10)

        layout.addWidget(section_title("Résultat de la simulation"))
        self.result_header = QLabel("")
        self.result_header.setObjectName("resultHeader")
        layout.addWidget(self.result_header)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(9)
        self.value_labels: dict[str, QLabel] = {}
        pending_separators_after = {1, 6}  # après Fret et après TVA
        for row_index, (key, label_text) in enumerate(_RESULT_ROWS):
            label = QLabel(label_text)
            label.setObjectName("resultLabel")
            value = QLabel("—")
            value.setObjectName("resultValue")
            value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            grid.addWidget(label, grid.rowCount(), 0)
            grid.addWidget(value, grid.rowCount() - 1, 1)
            self.value_labels[key] = value
            if row_index in pending_separators_after:
                grid.addWidget(h_line(), grid.rowCount(), 0, 1, 2)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)

        layout.addSpacing(6)

        total_card = QFrame()
        total_card.setObjectName("totalCard")
        total_layout = QVBoxLayout(total_card)
        total_layout.setContentsMargins(20, 14, 20, 14)
        total_title = QLabel("COÛT TOTAL ESTIMÉ")
        total_title.setObjectName("totalTitle")
        total_title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.total_value = QLabel("—")
        self.total_value.setObjectName("totalValue")
        self.total_value.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        total_layout.addWidget(total_title)
        total_layout.addWidget(self.total_value)
        layout.addWidget(total_card)

        self.stale_label = QLabel("Champs modifiés — cliquez sur « Calculer » pour actualiser.")
        self.stale_label.setObjectName("warnLabel")
        self.stale_label.hide()
        layout.addWidget(self.stale_label)

        layout.addStretch(1)
        layout.addWidget(
            hint_label(
                "Estimation indicative : les taux utilisés sont ceux définis dans "
                "l'onglet Paramètres (voir l'avertissement en bas de la fenêtre)."
            )
        )
        return panel

    # ------------------------------------------------------- données d'entrée

    def _build_params(self) -> CalculationParams:
        return CalculationParams.from_settings(self.settings_repo.get_all())

    def _collect_inputs(self, require_identity: bool):
        return validate_simulation_input(
            marque=self.marque_cb.currentText(),
            modele=self.modele_cb.currentText(),
            annee=self.annee_sp.value(),
            cylindree=self.cylindree_edit.text(),
            prix_usd=self.prix_edit.text(),
            fret_usd=self.fret_edit.text(),
            taux_change=self.taux_edit.text(),
            taux_fret=self.taux_fret_edit.text(),
            taxe_vehicule=self.taxe_edit.text(),
            devise=self.devise_cb.currentText(),
            date_simulation=self._selected_date(),
            require_identity=require_identity,
        )

    # ---------------------------------------------------------------- actions

    def compute_clicked(self) -> None:
        """Bouton « Calculer » : validation stricte + calcul + affichage."""
        try:
            params = self._build_params()
            inputs = self._collect_inputs(require_identity=False)
        except ValidationError as exc:
            QMessageBox.warning(self, "Saisie incomplète", str(exc))
            return
        except DatabaseError as exc:
            show_db_error(self, exc)
            return

        vehicle = Vehicle(inputs.marque, inputs.modele, inputs.annee, inputs.cylindree)
        result = compute_cost(vehicle, inputs.prix_usd, inputs.fret_usd, inputs.taux_change,
                              params, taxe_vehicule=inputs.taxe_vehicule,
                              devise=inputs.devise, taux_fret=inputs.taux_fret)
        self._last_result = result
        self._apply_result(result)
        self.stale_label.hide()
        self.status_label.setText(
            "✔ Calcul effectué. Cliquez sur « Enregistrer » pour conserver la simulation."
        )

    def save_clicked(self) -> None:
        """Bouton « Enregistrer » : insertion ou mise à jour en base."""
        try:
            params = self._build_params()
            inputs = self._collect_inputs(require_identity=True)
        except ValidationError as exc:
            QMessageBox.warning(self, "Enregistrement impossible", str(exc))
            return
        except DatabaseError as exc:
            show_db_error(self, exc)
            return

        vehicle = Vehicle(inputs.marque, inputs.modele, inputs.annee, inputs.cylindree)
        result = compute_cost(vehicle, inputs.prix_usd, inputs.fret_usd, inputs.taux_change,
                              params, taxe_vehicule=inputs.taxe_vehicule,
                              devise=inputs.devise, taux_fret=inputs.taux_fret)
        sim = Simulation.from_result(result, inputs.date_simulation, sim_id=self._editing_id)

        if self._editing_id is not None:
            answer = self._ask_update_or_new(sim)
            if answer == "cancel":
                return
            if answer == "new":
                sim.id = None
                self._editing_id = None
                self.editing_label.hide()

        try:
            sim_id = self.sim_repo.save(sim)
        except DatabaseError as exc:
            show_db_error(self, exc)
            return

        # Enrichit le catalogue marques / modèles (non bloquant en cas d'erreur)
        try:
            self.catalog_repo.add_brand(inputs.marque)
            self.catalog_repo.add_model(inputs.marque, inputs.modele)
            self._load_catalog(keep_marque=inputs.marque, keep_modele=inputs.modele)
        except DatabaseError:
            pass

        self._last_result = result
        self._apply_result(result)
        self.stale_label.hide()
        if self._editing_id is not None:
            self.status_label.setText(f"✔ Simulation n° {sim_id} mise à jour.")
        else:
            self.status_label.setText(
                f"✔ Simulation enregistrée sous le n° {sim_id} — visible dans l'onglet Historique."
            )
        self.simulation_saved.emit()

    def reset_clicked(self, silent: bool = False) -> None:
        """Bouton « Réinitialiser » : formulaire et résultats remis à zéro."""
        self._updating = True
        try:
            self.marque_cb.setEditText("")
            self._refresh_model_combo("", keep_text="")
            self.annee_sp.setValue(QDate.currentDate().year())
            self.cylindree_edit.clear()
            self.prix_edit.clear()
            self.fret_edit.clear()
            try:
                default_taxe = decimal_to_str(
                    parse_decimal(self.settings_repo.get_all().get("taxe_vehicule", "0"))
                )
            except (ValueError, DatabaseError):
                default_taxe = "0"
            # Taux achat et taux fret par défaut de la devise courante…
            devise = self.devise_cb.currentText() or "USD"
            default_taux = decimal_to_str(self._default_rate_for(devise))
            default_fret = decimal_to_str(self._default_rate_for(devise, freight=True))
            self.taux_edit.setText(default_taux)
            self.taux_fret_edit.setText(default_fret)
            self.taxe_edit.setText(default_taxe)
            self._default_taux = parse_decimal(default_taux)
            self._default_taux_fret = parse_decimal(default_fret)
            self._default_taxe = parse_decimal(default_taxe)
            # …puis retour à l'USD : les deux taux suivent leurs défauts USD
            self.devise_cb.setCurrentText("USD")
            self._update_currency_labels("USD")
            self._default_taux = self._default_rate_for("USD")
            self._default_taux_fret = self._default_rate_for("USD", freight=True)
            self.taux_edit.setText(decimal_to_str(self._default_taux))
            self.taux_fret_edit.setText(decimal_to_str(self._default_taux_fret))
            self.date_edit.setDate(QDate.currentDate())
        finally:
            self._updating = False

        self._last_result = None
        self._editing_id = None
        self._apply_result(None)
        self.stale_label.hide()
        self.editing_label.hide()
        if not silent:
            self.status_label.setText("Formulaire réinitialisé.")

    def copy_result(self) -> None:
        """Copie un résumé textuel du calcul dans le presse-papiers."""
        sim = self._current_simulation()
        if sim is None:
            return
        QApplication.clipboard().setText(simulation_summary_text(sim))
        self.status_label.setText("✔ Résumé copié dans le presse-papiers.")

    def _export(self, kind: str) -> None:
        """Export CSV ou Excel de la simulation en cours."""
        sim = self._current_simulation()
        if sim is None:
            return
        base_name = re.sub(
            r"[^A-Za-z0-9_-]+", "_",
            f"{sim.marque}_{sim.modele}_{sim.annee}_{sim.date:%Y%m%d}",
        ).strip("_") or "simulation"
        if kind == "csv":
            path, _ = QFileDialog.getSaveFileName(
                self, "Exporter la simulation (CSV)", f"{base_name}.csv",
                "Fichier CSV (*.csv)",
            )
        else:
            path, _ = QFileDialog.getSaveFileName(
                self, "Exporter la simulation (Excel)", f"{base_name}.xlsx",
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
                export_simulations_csv(path, [sim])
            else:
                export_simulations_excel(path, [sim])
        except (ExportError, OSError) as exc:
            QMessageBox.critical(self, "Export impossible", str(exc))
            return
        QMessageBox.information(self, "Export réussi", f"La simulation a été exportée vers :\n{path}")

    # ---------------------------------------------------------------- helpers

    def _ask_update_or_new(self, sim: Simulation) -> str:
        """Boîte de choix : mettre à jour la simulation existante ou en créer une nouvelle."""
        box = QMessageBox(self)
        box.setWindowTitle("Enregistrer la simulation")
        box.setIcon(QMessageBox.Icon.Question)
        box.setText(
            f"Vous modifiez la simulation n° {sim.id} ({sim.label}).\n\n"
            "Voulez-vous mettre à jour cette simulation ou créer une nouvelle entrée ?"
        )
        btn_update = box.addButton("Mettre à jour", QMessageBox.ButtonRole.YesRole)
        btn_new = box.addButton("Créer une nouvelle simulation", QMessageBox.ButtonRole.NoRole)
        box.addButton("Annuler", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        if clicked is btn_update:
            return "update"
        if clicked is btn_new:
            return "new"
        return "cancel"

    def _current_simulation(self) -> Simulation | None:
        if self._last_result is None:
            QMessageBox.information(
                self,
                "Aucun calcul disponible",
                "Veuillez d'abord cliquer sur « Calculer ».",
            )
            return None
        return Simulation.from_result(
            self._last_result, self._selected_date(), sim_id=self._editing_id
        )

    def _selected_date(self) -> date:
        """Date choisie dans le formulaire (compatible toutes versions PySide6)."""
        year, month, day = self.date_edit.date().getDate()
        return date(year, month, day)

    def _apply_result(self, result: SimulationResult | None) -> None:
        if result is None:
            for label in self.value_labels.values():
                label.setText("—")
            self.total_value.setText("—")
            self.result_header.setText("")
            return

        identity = f"{result.marque} {result.modele} {result.annee}".upper().strip()
        cyl_label = f" — {decimal_to_str(result.cylindree)} L" if identity else ""
        self.result_header.setText((identity or "Simulation") + cyl_label)

        self.value_labels["prix_dzd"].setText(format_dzd(result.prix_dzd))
        self.value_labels["fret_dzd"].setText(format_dzd(result.fret_dzd))
        self.value_labels["valeur_douaniere"].setText(format_dzd(result.valeur_douaniere))
        self.value_labels["taux_douane"].setText(format_percent(result.taux_douane))
        self.value_labels["droits_douane"].setText(format_dzd(result.droits_douane))
        self.value_labels["base_tva"].setText(format_dzd(result.base_tva))
        self.value_labels["tva"].setText(format_dzd(result.tva))
        self.value_labels["frais_transitaire"].setText(format_dzd(result.frais_transitaire))
        self.value_labels["frais_portuaires"].setText(format_dzd(result.frais_portuaires))
        self.value_labels["taxe_vehicule"].setText(format_dzd(result.taxe_vehicule))
        self.total_value.setText(format_dzd(result.cout_total))

    # ---------------------------------------------------------------- devises

    def _update_currency_labels(self, devise: str | None = None) -> None:
        """Libellés Prix/Fret/taux synchronisés avec la devise choisie."""
        devise = (devise or self.devise_cb.currentText() or "USD").strip() or "USD"
        self.prix_label.setText(f"Prix véhicule ({devise})")
        self.fret_label.setText(f"Fret ({devise})")
        self.taux_label.setText(f"Taux achat (DA/{devise})")
        self.taux_fret_label.setText(f"Taux fret (DA/{devise})")

    def _default_rate_for(self, devise: str, freight: bool = False) -> Decimal:
        """Taux par défaut (achat ou fret) d'une devise selon les Paramètres."""
        keys = DEVISE_FREIGHT_KEYS if freight else DEVISE_RATE_KEYS
        fallbacks = DEVISE_RATE_FALLBACKS
        key = keys.get(devise, "taux_change")
        fallback = parse_decimal(fallbacks.get(devise, "250"))
        try:
            raw = self.settings_repo.get_all().get(key, "")
            return parse_decimal(raw) if raw else fallback
        except (ValueError, DatabaseError):
            return fallback

    def _on_devise_changed(self, devise: str) -> None:
        self._update_currency_labels(devise)
        if self._updating:
            return
        # Taux d'achat : suivre le nouveau défaut s'il suivait encore l'ancien
        try:
            current = parse_decimal(self.taux_edit.text())
        except ValueError:
            current = None
        if current is None or current == self._default_taux:
            new_default = self._default_rate_for(devise)
            self.taux_edit.setText(decimal_to_str(new_default))
            self._default_taux = new_default
        # Taux de fret : même logique avec son propre défaut
        try:
            current_fret = parse_decimal(self.taux_fret_edit.text())
        except ValueError:
            current_fret = None
        if current_fret is None or current_fret == self._default_taux_fret:
            new_fret = self._default_rate_for(devise, freight=True)
            self.taux_fret_edit.setText(decimal_to_str(new_fret))
            self._default_taux_fret = new_fret
        self._on_input_changed()

    # ------------------------------------------------------------- catalogue

    def _load_catalog(self, keep_marque: str, keep_modele: str) -> None:
        """Recharge les marques/modèles (base utilisateur + catalogue embarqué),
        en conservant le texte saisi."""
        self._updating = True
        try:
            self.marque_cb.blockSignals(True)
            self.marque_cb.clear()
            try:
                db_brands = self.catalog_repo.list_brands()
            except DatabaseError:
                db_brands = []
            self.marque_cb.addItems(vehicle_catalog.brands_for_combo(db_brands))
            self.marque_cb.blockSignals(False)
            if keep_marque:
                self.marque_cb.setEditText(keep_marque)
            self._refresh_model_combo(self.marque_cb.currentText(), keep_text=keep_modele)
        finally:
            self._updating = False

    def _refresh_model_combo(self, brand: str, keep_text: str | None = None) -> None:
        combo = self.modele_cb
        current = keep_text if keep_text is not None else combo.currentText()
        combo.blockSignals(True)
        combo.clear()
        if brand.strip():
            try:
                db_models = self.catalog_repo.list_models(brand)
            except DatabaseError:
                db_models = []
            combo.addItems(vehicle_catalog.models_for_combo(brand, db_models))
        combo.blockSignals(False)
        if current:
            combo.setEditText(current)

    # --------------------------------------------------------------- signaux

    def _on_brand_changed(self, brand: str) -> None:
        if self._updating:
            return
        self._refresh_model_combo(brand)
        self._on_input_changed()

    def _on_input_changed(self, *_args) -> None:
        """Recalcul silencieux si un résultat est déjà affiché, sinon alerte de péremption."""
        if self._updating:
            return
        if self._last_result is None:
            return
        if self._recompute_silently():
            self.stale_label.hide()
        else:
            self.stale_label.show()

    def _recompute_silently(self) -> bool:
        try:
            params = self._build_params()
            inputs = self._collect_inputs(require_identity=False)
        except (ValidationError, DatabaseError):
            return False
        vehicle = Vehicle(inputs.marque, inputs.modele, inputs.annee, inputs.cylindree)
        result = compute_cost(vehicle, inputs.prix_usd, inputs.fret_usd, inputs.taux_change,
                              params, taxe_vehicule=inputs.taxe_vehicule,
                              devise=inputs.devise, taux_fret=inputs.taux_fret)
        self._last_result = result
        self._apply_result(result)
        return True

    def on_settings_changed(self, first_load: bool = False) -> None:
        """Appelé quand les paramètres changent (onglet Paramètres)."""
        try:
            settings = self.settings_repo.get_all()
        except DatabaseError:
            settings = {}
        devise_courante = self.devise_cb.currentText() or "USD"
        new_default = self._default_rate_for(devise_courante)
        new_default_fret = self._default_rate_for(devise_courante, freight=True)

        current_text = self.taux_edit.text().strip()
        follows_default = not current_text
        if not follows_default:
            try:
                follows_default = parse_decimal(current_text) == self._default_taux
            except ValueError:
                follows_default = False
        if follows_default:
            self.taux_edit.setText(decimal_to_str(new_default))
        self._default_taux = new_default

        current_fret = self.taux_fret_edit.text().strip()
        follows_fret = not current_fret
        if not follows_fret:
            try:
                follows_fret = parse_decimal(current_fret) == self._default_taux_fret
            except ValueError:
                follows_fret = False
        if follows_fret:
            self.taux_fret_edit.setText(decimal_to_str(new_default_fret))
        self._default_taux_fret = new_default_fret

        try:
            new_default_taxe = parse_decimal(settings.get("taxe_vehicule", "0"))
        except ValueError:
            new_default_taxe = parse_decimal("0")
        current_taxe = self.taxe_edit.text().strip()
        follows_taxe = not current_taxe
        if not follows_taxe:
            try:
                follows_taxe = parse_decimal(current_taxe) == self._default_taxe
            except ValueError:
                follows_taxe = False
        if follows_taxe:
            self.taxe_edit.setText(decimal_to_str(new_default_taxe))
        self._default_taxe = new_default_taxe

        if not first_load and self._last_result is not None:
            self._on_input_changed()

    # ------------------------------------------------------- chargement historique

    def load_for_edit(self, sim: Simulation) -> None:
        """Ouvre une simulation de l'historique pour modification."""
        self._updating = True
        try:
            self.marque_cb.setEditText(sim.marque)
            self._refresh_model_combo(sim.marque, keep_text=sim.modele)
            self.devise_cb.setCurrentText(sim.devise)
            self._update_currency_labels(sim.devise)
            fret_rate = sim.taux_fret if sim.taux_fret > 0 else sim.taux_change
            self.taux_fret_edit.setText(decimal_to_str(fret_rate))
            self._default_taux_fret = fret_rate
            self.annee_sp.setValue(sim.annee)
            self.cylindree_edit.setText(decimal_to_str(sim.cylindree))
            self.prix_edit.setText(decimal_to_str(sim.prix_usd))
            self.fret_edit.setText(decimal_to_str(sim.fret_usd))
            self.taux_edit.setText(decimal_to_str(sim.taux_change))
            self.taxe_edit.setText(decimal_to_str(sim.taxe_vehicule))
            self.date_edit.setDate(QDate(sim.date.year, sim.date.month, sim.date.day))
        finally:
            self._updating = False

        # Affichage direct des valeurs enregistrées (sans recalcul)
        result = SimulationResult(
            marque=sim.marque,
            modele=sim.modele,
            annee=sim.annee,
            cylindree=sim.cylindree,
            prix_usd=sim.prix_usd,
            fret_usd=sim.fret_usd,
            taux_change=sim.taux_change,
            prix_dzd=sim.prix_dzd,
            fret_dzd=sim.fret_dzd,
            valeur_douaniere=sim.valeur_douaniere,
            taux_douane=sim.taux_douane / 100,
            droits_douane=sim.droits_douane,
            base_tva=sim.base_tva,
            tva=sim.tva,
            frais_transitaire=sim.frais_transitaire,
            frais_portuaires=sim.frais_portuaires,
            taxe_vehicule=sim.taxe_vehicule,
            cout_total=sim.cout_total,
        )
        self._last_result = result
        self._editing_id = sim.id
        self._apply_result(result)
        self.stale_label.hide()
        self.editing_label.setText(
            f"Modification de la simulation n° {sim.id} ({sim.label}). "
            "L'enregistrement mettra cette ligne à jour."
        )
        self.editing_label.show()
        self.status_label.setText("Simulation chargée depuis l'historique.")
