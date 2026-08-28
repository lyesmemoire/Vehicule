"""Onglet « Paramètres » : taux et frais fixes modifiables, stockés en SQLite."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from database.backup import backup_dir, create_backup, list_backups, restore_backup
from database.db import DatabaseError
from database.repositories import SettingsRepository
from ui.components import (
    MONEY_PATTERN,
    RATE_PATTERN,
    Panel,
    attach_decimal_validator,
    field_label,
    h_line,
    hint_label,
    page_title,
    section_title,
    show_db_error,
)
from utils.currency import decimal_to_str, parse_decimal
from utils.validators import ValidationError, validate_settings_input

# (clé, libellé, unité, exemple)
_FIELDS = [
    ("taux_change", "Taux de change USD/DZD", "DA pour 1 USD", "ex : 250", RATE_PATTERN),
    ("taux_eur", "Taux de change EUR/DZD", "DA pour 1 EUR", "ex : 270", RATE_PATTERN),
    ("taux_cny", "Taux de change CNY/DZD", "DA pour 1 CNY", "ex : 35", RATE_PATTERN),
    ("tva", "Taux de TVA", "%", "ex : 19", RATE_PATTERN),
    ("douane_le_seuil", "Droits de douane — cylindrée ≤ seuil", "%", "ex : 15", RATE_PATTERN),
    ("douane_sup_seuil", "Droits de douane — cylindrée > seuil", "%", "ex : 30", RATE_PATTERN),
    ("seuil_cylindree", "Seuil de cylindrée douanière", "litres", "ex : 1.8", RATE_PATTERN),
    ("frais_transitaire", "Prestation transitaire", "DZD", "ex : 70000", MONEY_PATTERN),
    ("frais_portuaires", "Frais portuaires", "DZD", "ex : 130000", MONEY_PATTERN),
    ("taxe_vehicule", "Taxe véhicule", "DZD", "ex : 0", MONEY_PATTERN),
]


class SettingsPage(QWidget):
    """Paramètres de calcul — valeurs par défaut restaurables + sauvegardes."""

    settings_saved = Signal()
    database_restored = Signal()

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

        # --- Section sauvegarde / restauration de la base -------------------
        layout.addWidget(h_line())
        layout.addSpacing(4)
        layout.addWidget(section_title("Sauvegarde des données"))
        self.backup_hint = hint_label("")
        layout.addWidget(self.backup_hint)
        self._update_backup_hint()

        backup_row = QHBoxLayout()
        self.btn_backup = QPushButton("Créer une sauvegarde")
        self.btn_backup.clicked.connect(self.create_backup_clicked)
        self.btn_restore = QPushButton("Restaurer une sauvegarde…")
        self.btn_restore.clicked.connect(self.restore_backup_clicked)
        self.btn_open_folder = QPushButton("Ouvrir le dossier")
        self.btn_open_folder.clicked.connect(self.open_backup_folder)
        backup_row.addWidget(self.btn_backup)
        backup_row.addWidget(self.btn_restore)
        backup_row.addWidget(self.btn_open_folder)
        backup_row.addStretch(1)
        layout.addLayout(backup_row)

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
                taux_eur=self.fields["taux_eur"].text(),
                taux_cny=self.fields["taux_cny"].text(),
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

    # ------------------------------------------------------------- sauvegardes

    def _update_backup_hint(self) -> None:
        """Affiche le dossier de sauvegardes et le nombre de copies présentes."""
        count = len(list_backups())
        self.backup_hint.setText(
            f"Dossier : {backup_dir()}"
            + (f" — {count} sauvegarde(s) présente(s)" if count else "")
            + "\nUne sauvegarde automatique est créée à chaque démarrage "
            "(les 10 dernières sont conservées)."
        )

    def create_backup_clicked(self) -> None:
        try:
            path = create_backup("manual")
        except DatabaseError as exc:
            show_db_error(self, exc)
            return
        self._update_backup_hint()
        self.feedback.setText(f"✔ Sauvegarde créée : {path.name}")
        self._feedback_timer.start(6000)

    def restore_backup_clicked(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choisir la sauvegarde à restaurer",
            backup_dir().as_posix(),
            "Sauvegardes (*.bak *.db);;Tous les fichiers (*)",
        )
        if not path:
            return
        box = QMessageBox(self)
        box.setWindowTitle("Restaurer une sauvegarde")
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText(
            "Remplacer TOUTES les données actuelles par cette sauvegarde ?\n\n"
            f"{path}\n\nLa base actuelle sera d'abord sauvegardée automatiquement."
        )
        btn_ok = box.addButton("Restaurer", QMessageBox.ButtonRole.DestructiveRole)
        box.addButton("Annuler", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is not btn_ok:
            return
        try:
            restore_backup(path)
        except DatabaseError as exc:
            show_db_error(self, exc)
            return
        self.load()
        self._update_backup_hint()
        self.feedback.setText("✔ Base de données restaurée avec succès.")
        self._feedback_timer.start(6000)
        self.database_restored.emit()

    def open_backup_folder(self) -> None:
        backup_dir().mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(backup_dir().as_posix()))
