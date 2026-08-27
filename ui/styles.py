"""Feuille de style globale de l'application (design sobre et professionnel).

Palette :
- fond gris très clair : #eef1f6 / #f8fafc
- panneaux blancs      : #ffffff
- bleu foncé (titres)  : #14345c
- vert (coût final)    : #15803d
- rouge/orange alertes : #b91c1c / #b45309
"""

APP_STYLESHEET = """
* {
    font-family: 'Segoe UI', 'Noto Sans', 'DejaVu Sans', Arial, sans-serif;
    font-size: 10pt;
    color: #1f2937;
}

QWidget#pageRoot { background: #eef1f6; }

QFrame#panel {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
}

QFrame#hline {
    border: none;
    background: #e5e7eb;
    max-height: 1px;
}

QLabel { background: transparent; }
QLabel#pageTitle   { font-size: 16pt; font-weight: 700; color: #14345c; }
QLabel#sectionTitle{ font-size: 12pt; font-weight: 600; color: #14345c; }
QLabel#fieldLabel  { color: #475569; font-weight: 500; }
QLabel#hintLabel   { color: #64748b; font-size: 9pt; }
QLabel#warnLabel   { color: #b45309; font-size: 9pt; font-weight: 600; }
QLabel#statusLabel { color: #166534; font-size: 9pt; font-weight: 600; }
QLabel#countLabel  { color: #64748b; font-size: 9pt; }

QLabel#resultLabel { color: #475569; }
QLabel#resultValue { font-weight: 600; color: #0f172a; }
QLabel#resultHeader{ font-size: 12pt; font-weight: 700; color: #1d4ed8; }

QFrame#totalCard {
    background: #ecfdf5;
    border: 2px solid #15803d;
    border-radius: 12px;
}
QLabel#totalTitle { font-size: 11pt; font-weight: 700; color: #166534; }
QLabel#totalValue { font-size: 22pt; font-weight: 800; color: #15803d; }

QFrame#disclaimerBar {
    background: #fffbeb;
    border: 1px solid #fde68a;
    border-radius: 8px;
}
QLabel#disclaimerLabel { color: #92400e; font-size: 8.5pt; }

QLineEdit, QComboBox, QSpinBox, QDateEdit {
    background: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 6px 8px;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDateEdit:focus {
    border: 1px solid #2563eb;
}
QComboBox::drop-down { border: none; width: 22px; }
QComboBox::down-arrow {
    image: url(__ICONS_DIR__/arrow-down.png);
    width: 12px; height: 8px; margin-right: 6px;
}

/* Ruban « Marque / Modèle » : liste déroulante large, arrondie, mise en valeur */
QComboBox#ribbon {
    min-height: 36px;
    border-radius: 18px;
    padding: 4px 36px 4px 14px;
    font-size: 10.5pt;
    font-weight: 600;
    color: #14345c;
    border: 1.5px solid #cbd5e1;
    background: #ffffff;
}
QComboBox#ribbon:hover  { border-color: #94a3b8; background: #fcfdff; }
QComboBox#ribbon:focus  { border-color: #2563eb; background: #f5f9ff; }
QComboBox#ribbon::drop-down { width: 34px; border: none; }
QComboBox#ribbon::down-arrow { margin-right: 11px; }
QComboBox#ribbon QAbstractItemView {
    background: #ffffff;
    border: 1px solid #dbe2ea;
    border-radius: 10px;
    padding: 5px;
    selection-background-color: #dbeafe;
    selection-color: #14345c;
    outline: 0;
}

QSpinBox::up-button, QDateEdit::up-button {
    subcontrol-origin: border; subcontrol-position: top right;
    width: 20px; border: none; border-left: 1px solid #e2e8f0; background: #f8fafc;
}
QSpinBox::down-button, QDateEdit::down-button {
    subcontrol-origin: border; subcontrol-position: bottom right;
    width: 20px; border: none; border-left: 1px solid #e2e8f0; background: #f8fafc;
}
QSpinBox::up-button:hover, QDateEdit::up-button:hover,
QSpinBox::down-button:hover, QDateEdit::down-button:hover { background: #e2e8f0; }
QSpinBox::up-arrow, QDateEdit::up-arrow {
    image: url(__ICONS_DIR__/arrow-up.png);
    width: 12px; height: 8px;
}
QSpinBox::down-arrow, QDateEdit::down-arrow {
    image: url(__ICONS_DIR__/arrow-down.png);
    width: 12px; height: 8px;
}

QPushButton {
    background: #ffffff;
    color: #1f2937;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 8px 14px;
    font-weight: 500;
}
QPushButton:hover  { background: #f1f5f9; }
QPushButton:pressed{ background: #e2e8f0; }
QPushButton:disabled { color: #94a3b8; background: #f8fafc; }

QPushButton#primary { background: #1d4ed8; color: #ffffff; border: none; font-weight: 600; }
QPushButton#primary:hover   { background: #1e40af; }
QPushButton#primary:pressed { background: #1e3a8a; }

QPushButton#success { background: #15803d; color: #ffffff; border: none; font-weight: 600; }
QPushButton#success:hover   { background: #166534; }

QPushButton#danger { background: #ffffff; color: #b91c1c; border: 1px solid #fca5a5; font-weight: 600; }
QPushButton#danger:hover { background: #fef2f2; }

QTabWidget::pane {
    border: 1px solid #dbe2ea;
    border-radius: 8px;
    background: #f8fafc;
}
QTabBar::tab {
    background: #e6ebf2;
    color: #475569;
    padding: 9px 20px;
    margin-right: 4px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    font-weight: 500;
}
QTabBar::tab:selected { background: #ffffff; color: #14345c; font-weight: 700; }

QTableView {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    gridline-color: #eef2f6;
    alternate-background-color: #f8fafc;
    selection-background-color: #dbeafe;
    selection-color: #1f2937;
}
QHeaderView::section {
    background: #f1f5f9;
    color: #334155;
    padding: 8px;
    border: none;
    border-bottom: 2px solid #cbd5e1;
    font-weight: 600;
}

QTableWidget {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    gridline-color: #eef2f6;
    alternate-background-color: #f8fafc;
    selection-background-color: #dbeafe;
    selection-color: #1f2937;
}

QComboBox QAbstractItemView {
    background: #ffffff;
    border: 1px solid #cbd5e1;
    selection-background-color: #dbeafe;
    selection-color: #1f2937;
}

QMessageBox { background: #ffffff; }

QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #cbd5e1; border-radius: 5px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: #cbd5e1; border-radius: 5px; min-width: 30px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
"""

# Résolution du dossier d'icônes (placeholders du QSS) — compatible exécutable PyInstaller.
from utils.paths import asset_path  # noqa: E402

APP_STYLESHEET = APP_STYLESHEET.replace("__ICONS_DIR__", asset_path("icons").as_posix())
