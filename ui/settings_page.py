"""Onglet « Paramètres » : taux et frais fixes modifiables, stockés en SQLite."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from database.db import DatabaseError
from database.repositories import SettingsRepository
from ui.components import (
    MONEY_PATTERN,
    RATE_PATTERN,
    Panel,
    attach_decimal_validator,
    field_label,
    hint_label,
    page_title,
    show_db_error,
)
from utils.currency import decimal_to_str, parse_decimal
from utils.validators import ValidationError, validate_settings_input

# (clé, libellé, unité, exemple)
_FIELDS = [
    ("taux_change", "Taux de change USD/DZD", "DA pour 1 USD", "ex : 250", RATE_PATTERN),
    ("tva", "Taux de TVA", "%", "ex : 19", RATE_PATTERN),
    ("douane_le_seuil", "Droits de douane — cylindrée ≤ seuil", "%", "ex : 15", RATE_PATTERN),
    ("douane_sup_seuil", "Droits de douane — cylindrée > seuil", "%", "ex : 30", RATE_PATTERN),
    ("seuil_cylindree", "Seuil de cylindrée douanière", "litres", "ex : 1.8", RATE_PATTERN),
    ("frais_transitaire", "Prestation transitaire", "DZD", "ex : 70000", MONEY_PATTERN),
    ("frais_portuaires", "Frais portuaires", "DZD", "ex : 130000", MONEY_PATTERN),
    ("taxe_vehicule", "Taxe véhicule", "DZD", "ex : 0", MONEY_PATTERN),
]


class SettingsPage(QWidget):
    """Paramètres de calcul — valeurs par défaut restaurables."""

    settings_saved = Signal()

    def __init__(self, settings_repo: SettingsRepository, parent=None):
        super().__init__(parent)
        self.settings_repo = settings_repo
        self.fields: dict[str, QLineEdit] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addStretch(1)

        panel = Panel()
        panel.setMaximumWidth(620)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        layout.addWidget(page_title("Paramètres de calcul"))
        layout.addWidget(
            hint_label(
                "Ces valeurs sont des paramètres de travail définis par l'utilisateur. "
                "Elles ne constituent pas une garantie de conformité réglementaire."
            )
        )
        layout.addSpacing(4)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(11)
        for row, (key, label_text, unit, placeholder, pattern) in enumerate(_FIELDS):
            label = field_label(label_text)
            field = QLineEdit()
            field.setPlaceholderText(placeholder)
            attach_decimal_validator(field, pattern)
            field.setMinimumWidth(150)
            unit_label = QLabel(unit)
            unit_label.setObjectName("hintLabel")
            grid.addWidget(label, row, 0)
            grid.addWidget(field, row, 1)
            grid.addWidget(unit_label, row, 2)
            self.fields[key] = field
        grid.setColumnStretch(0, 1)
        layout.addLayout(grid)

        buttons = QHBoxLayout()
        self.btn_save = QPushButton("Enregistrer les paramètres")
        self.btn_save.setObjectName("primary")
        self.btn_save.clicked.connect(self.save_clicked)
        self.btn_reset = QPushButton("Restaurer les valeurs par défaut")
        self.btn_reset.setObjectName("danger")
        self.btn_reset.clicked.connect(self.reset_defaults_clicked)
        buttons.addWidget(self.btn_save)
        buttons.addWidget(self.btn_reset)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.feedback = hint_label("")
        self.feedback.setObjectName("statusLabel")
        layout.addWidget(self.feedback)

        root.addWidget(panel, stretch=0, alignment=Qt.AlignmentFlag.AlignTop)
        root.addStretch(2)

        self._feedback_timer = QTimer(self)
        self._feedback_timer.setSingleShot(True)
        self._feedback_timer.timeout.connect(lambda: self.feedback.setText(""))

        self.load(quiet=True)  # à l'ouverture : pas de dialogue modal

    # ------------------------------------------------------------------ actions

    def load(self, quiet: bool = False) -> None:
        """Affiche les paramètres actuellement stockés.

        ``quiet=True`` (à l'ouverture de la fenêtre) : en cas d'erreur de base
        de données, les champs restent vides au lieu d'ouvrir une boîte modale.
        """
        try:
            settings = self.settings_repo.get_all()
        except DatabaseError as exc:
            if not quiet:
                show_db_error(self, exc)
            return
        for key, field in self.fields.items():
            try:
                field.setText(decimal_to_str(parse_decimal(settings.get(key, ""))))
            except ValueError:
                field.setText("")

    def save_clicked(self) -> None:
        try:
            validated = validate_settings_input(
                taux_change=self.fields["taux_change"].text(),
                tva=self.fields["tva"].text(),
                douane_le_seuil=self.fields["douane_le_seuil"].text(),
                douane_sup_seuil=self.fields["douane_sup_seuil"].text(),
                seuil_cylindree=self.fields["seuil_cylindree"].text(),
                frais_transitaire=self.fields["frais_transitaire"].text(),
                frais_portuaires=self.fields["frais_portuaires"].text(),
                taxe_vehicule=self.fields["taxe_vehicule"].text(),
            )
        except ValidationError as exc:
            QMessageBox.warning(self, "Paramètres invalides", str(exc))
            return
        except DatabaseError as exc:
            show_db_error(self, exc)
            return

        try:
            self.settings_repo.save(validated.as_dict())
        except DatabaseError as exc:
            show_db_error(self, exc)
            return
        self.load()
        self.feedback.setText("✔ Paramètres enregistrés.")
        self._feedback_timer.start(4000)
        self.settings_saved.emit()

    def reset_defaults_clicked(self) -> None:
        box = QMessageBox(self)
        box.setWindowTitle("Restaurer les valeurs par défaut")
        box.setIcon(QMessageBox.Icon.Question)
        box.setText(
            "Restaurer toutes les valeurs par défaut ?\n\n"
            "Taux USD/DZD : 250 — TVA : 19 % — Douane : 15 % / 30 % (seuil 1.8 L)\n"
            "Transitaire : 70 000 DA — Frais portuaires : 130 000 DA — Taxe véhicule : 0 DA"
        )
        btn_ok = box.addButton("Restaurer", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Annuler", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is not btn_ok:
            return
        try:
            self.settings_repo.reset_defaults()
        except DatabaseError as exc:
            show_db_error(self, exc)
            return
        self.load()
        self.feedback.setText("✔ Valeurs par défaut restaurées.")
        self._feedback_timer.start(4000)
        self.settings_saved.emit()
