"""Petits composants réutilisables pour l'interface."""

from __future__ import annotations

from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import QFrame, QLabel, QLineEdit, QMessageBox, QWidget

# Motifs de saisie tolérants : chiffres + séparateur décimal point ou virgule.
MONEY_PATTERN = r"[0-9]{1,12}(?:[.,][0-9]{0,2})?"
CYLINDER_PATTERN = r"[0-9]{1,2}(?:[.,][0-9]{0,2})?"
RATE_PATTERN = r"[0-9]{1,6}(?:[.,][0-9]{0,2})?"


def attach_decimal_validator(field: QLineEdit, pattern: str = MONEY_PATTERN) -> None:
    """Empêche la saisie de caractères non numériques à la frappe
    (le contrôle métier final reste assuré par ``utils/validators.py``)."""
    field.setValidator(QRegularExpressionValidator(QRegularExpression(pattern), field))


class Panel(QFrame):
    """Panneau blanc à coins arrondis."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("panel")


def h_line() -> QFrame:
    """Fine ligne de séparation horizontale."""
    line = QFrame()
    line.setObjectName("hline")
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFixedHeight(1)
    return line


def page_title(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("pageTitle")
    return label


def section_title(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("sectionTitle")
    return label


def field_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("fieldLabel")
    return label


def hint_label(text: str = "") -> QLabel:
    label = QLabel(text)
    label.setObjectName("hintLabel")
    label.setWordWrap(True)
    return label


DISCLAIMER_TEXT = (
    "⚠ Les résultats sont des estimations. Les droits, taxes, valeurs douanières "
    "et autres frais doivent être vérifiés auprès des autorités et professionnels "
    "compétents avant toute opération d'importation."
)


def show_db_error(parent: QWidget | None, exc: Exception) -> None:
    """Affiche une erreur de base de données sans faire planter l'application."""
    QMessageBox.critical(
        parent,
        "Erreur de base de données",
        f"Une erreur est survenue lors de l'accès à la base de données locale.\n\n{exc}",
    )
