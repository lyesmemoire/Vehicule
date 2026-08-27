"""Onglet « Évolution des prix » : historique chronologique et graphique."""

from __future__ import annotations

from datetime import timedelta

from PySide6.QtCore import QDate, QDateTime, QMargins, Qt, QTime
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from database.db import DatabaseError
from database.repositories import SimulationRepository
from services.price_history import compute_price_stats
from ui.components import Panel, field_label, section_title, show_db_error
from ui.simple_chart import SimpleLineChart
from utils.currency import format_dzd, format_signed_percent, format_signed_usd, format_usd

try:  # QtCharts est fourni avec PySide6 ; on garde un plan B sans dépendance.
    from PySide6.QtCharts import (
        QChart,
        QChartView,
        QDateTimeAxis,
        QLineSeries,
        QValueAxis,
    )

    HAS_QTCHARTS = True
except ImportError:  # pragma: no cover
    HAS_QTCHARTS = False

_STAT_ROWS = [
    ("premier", "Premier prix"),
    ("dernier", "Dernier prix"),
    ("variation", "Variation (USD)"),
    ("variation_pct", "Variation (%)"),
    ("minimum", "Prix minimum"),
    ("maximum", "Prix maximum"),
    ("moyenne", "Prix moyen"),
    ("count", "Nombre de relevés"),
]


class PriceHistoryPage(QWidget):
    """Suivi de l'évolution des prix d'un même véhicule (plusieurs simulations)."""

    def __init__(self, sim_repo: SimulationRepository, parent=None):
        super().__init__(parent)
        self.sim_repo = sim_repo
        self._loading = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        # --- Sélection du véhicule -------------------------------------------
        selector = Panel()
        selector_layout = QHBoxLayout(selector)
        selector_layout.setContentsMargins(14, 10, 14, 10)
        selector_layout.setSpacing(10)
        selector_layout.addWidget(field_label("Marque :"))
        self.marque_cb = QComboBox()
        selector_layout.addWidget(self.marque_cb, stretch=2)
        selector_layout.addWidget(field_label("Modèle :"))
        self.modele_cb = QComboBox()
        selector_layout.addWidget(self.modele_cb, stretch=2)
        selector_layout.addWidget(field_label("Année :"))
        self.annee_cb = QComboBox()
        selector_layout.addWidget(self.annee_cb, stretch=1)
        self.btn_show = QPushButton("Afficher")
        self.btn_show.setObjectName("primary")
        self.btn_show.clicked.connect(self.load_current)
        selector_layout.addWidget(self.btn_show)
        root.addWidget(selector)

        # --- Corps -------------------------------------------------------------
        body = QHBoxLayout()
        body.setSpacing(12)

        left = Panel()
        left.setFixedWidth(480)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(16, 14, 16, 14)
        left_layout.setSpacing(8)
        left_layout.addWidget(section_title("Historique chronologique"))

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Date", "Prix (USD)", "Coût total (DZD)"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setMinimumHeight(180)
        left_layout.addWidget(self.table)

        left_layout.addSpacing(6)
        left_layout.addWidget(section_title("Statistiques"))
        stats_grid = QHBoxLayout()
        stats_labels = QVBoxLayout()
        stats_values = QVBoxLayout()
        stats_labels.setSpacing(7)
        stats_values.setSpacing(7)
        self.stat_labels: dict[str, QLabel] = {}
        for key, text in _STAT_ROWS:
            label = QLabel(text)
            label.setObjectName("resultLabel")
            value = QLabel("—")
            value.setObjectName("resultValue")
            value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            stats_labels.addWidget(label)
            stats_values.addWidget(value)
            self.stat_labels[key] = value
        stats_grid.addLayout(stats_labels, stretch=1)
        stats_grid.addLayout(stats_values, stretch=1)
        left_layout.addLayout(stats_grid)
        left_layout.addStretch(1)
        body.addWidget(left)

        right = Panel()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(16, 14, 16, 14)
        right_layout.setSpacing(8)
        right_layout.addWidget(section_title("Évolution du prix (USD)"))

        self.stack = QStackedWidget()
        if HAS_QTCHARTS:
            self.chart_view = QChartView()
            self.chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
            self.chart_view.chart().setTitle("")
            self.stack.addWidget(self.chart_view)
        else:
            self.fallback_chart = SimpleLineChart()
            self.stack.addWidget(self.fallback_chart)
        empty = QLabel(
            "Aucune donnée.\n\nEnregistrez plusieurs simulations du même véhicule "
            "(même marque, modèle et année) pour visualiser l'évolution de son prix."
        )
        empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty.setObjectName("hintLabel")
        empty.setWordWrap(True)
        self.stack.addWidget(empty)
        self.stack.setCurrentIndex(1)
        right_layout.addWidget(self.stack, stretch=1)
        body.addWidget(right, stretch=1)

        root.addLayout(body, stretch=1)

        # --- Signaux ---------------------------------------------------------
        self.marque_cb.currentTextChanged.connect(self._on_brand_changed)
        self.modele_cb.currentTextChanged.connect(self._on_model_changed)
        self.annee_cb.currentIndexChanged.connect(lambda _i: self.load_current())

        self.refresh(quiet=True)  # à l'ouverture : pas de dialogue modal

    # ------------------------------------------------------------- sélections

    def refresh(self, quiet: bool = False) -> None:
        """Recharge les listes de véhicules disponibles dans l'historique.

        ``quiet=True`` (à l'ouverture de la fenêtre) : pas de boîte de dialogue
        modale en cas d'erreur de base de données, simple état vide.
        """
        if self._loading:
            return
        self._loading = True
        try:
            try:
                brands = self.sim_repo.distinct_brands()
            except DatabaseError as exc:
                if not quiet:
                    show_db_error(self, exc)
                return
            current_marque = self.marque_cb.currentText()
            self.marque_cb.blockSignals(True)
            self.marque_cb.clear()
            self.marque_cb.addItems(brands)
            if current_marque:
                index = self.marque_cb.findText(current_marque)
                self.marque_cb.setCurrentIndex(index if index >= 0 else (0 if brands else -1))
            self.marque_cb.blockSignals(False)

            self._reload_models(quiet=quiet)
            self._reload_years(quiet=quiet)
        finally:
            self._loading = False
        self.load_current(quiet=quiet)

    def _reload_models(self, quiet: bool = False) -> None:
        marque = self.marque_cb.currentText()
        current = self.modele_cb.currentText()
        self.modele_cb.blockSignals(True)
        self.modele_cb.clear()
        if marque.strip():
            try:
                self.modele_cb.addItems(self.sim_repo.distinct_models(marque))
            except DatabaseError as exc:
                if not quiet:
                    show_db_error(self, exc)
        if current:
            index = self.modele_cb.findText(current)
            self.modele_cb.setCurrentIndex(max(index, 0))
        self.modele_cb.blockSignals(False)

    def _reload_years(self, quiet: bool = False) -> None:
        marque = self.marque_cb.currentText()
        modele = self.modele_cb.currentText()
        current = self.annee_cb.currentData()
        self.annee_cb.blockSignals(True)
        self.annee_cb.clear()
        if marque.strip() and modele.strip():
            try:
                for year in self.sim_repo.distinct_years(marque, modele):
                    self.annee_cb.addItem(str(year), year)
            except DatabaseError as exc:
                if not quiet:
                    show_db_error(self, exc)
        if current is not None:
            index = self.annee_cb.findData(current)
            if index >= 0:
                self.annee_cb.setCurrentIndex(index)
        self.annee_cb.blockSignals(False)

    def _on_brand_changed(self, _text: str) -> None:
        if self._loading:
            return
        self._loading = True
        try:
            self._reload_models()
            self._reload_years()
        finally:
            self._loading = False
        self.load_current()

    def _on_model_changed(self, _text: str) -> None:
        if self._loading:
            return
        self._loading = True
        try:
            self._reload_years()
        finally:
            self._loading = False
        self.load_current()

    # ----------------------------------------------------------------- affichage

    def load_current(self, quiet: bool = False) -> None:
        """Charge l'historique chronologique + stats + graphique du véhicule choisi."""
        marque = self.marque_cb.currentText().strip()
        modele = self.modele_cb.currentText().strip()
        annee = self.annee_cb.currentData()
        if not marque or not modele or annee is None:
            self._show_empty()
            return
        try:
            sims = self.sim_repo.find_vehicle_history(marque, modele, int(annee))
        except DatabaseError as exc:
            if not quiet:
                show_db_error(self, exc)
            self._show_empty()
            return

        stats = compute_price_stats(sims)
        if stats is None:
            self._show_empty()
            return

        # Tableau chronologique
        self.table.setRowCount(len(stats.points))
        for row, (sim_date, prix, cout) in enumerate(stats.points):
            date_item = QTableWidgetItem(sim_date.strftime("%d/%m/%Y"))
            prix_item = QTableWidgetItem(format_usd(prix))
            cout_item = QTableWidgetItem(format_dzd(cout))
            for col, item in enumerate((date_item, prix_item, cout_item)):
                if col > 0:
                    item.setTextAlignment(
                        int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    )
                self.table.setItem(row, col, item)
        self.table.resizeColumnsToContents()

        # Statistiques
        self.stat_labels["premier"].setText(format_usd(stats.premier))
        self.stat_labels["dernier"].setText(format_usd(stats.dernier))
        self.stat_labels["minimum"].setText(format_usd(stats.minimum))
        self.stat_labels["maximum"].setText(format_usd(stats.maximum))
        self.stat_labels["moyenne"].setText(format_usd(stats.moyenne))
        self.stat_labels["count"].setText(str(stats.count))

        variation_color = "#0f172a"
        if stats.variation < 0:  # baisse de prix = bonne nouvelle
            variation_color = "#15803d"
        elif stats.variation > 0:
            variation_color = "#b91c1c"
        self.stat_labels["variation"].setText(format_signed_usd(stats.variation))
        self.stat_labels["variation"].setStyleSheet(f"color: {variation_color};")
        self.stat_labels["variation_pct"].setText(
            format_signed_percent(stats.variation_pct) if stats.variation_pct is not None else "—"
        )
        self.stat_labels["variation_pct"].setStyleSheet(f"color: {variation_color};")

        self._update_chart(
            [(point_date, float(prix)) for point_date, prix, _ in stats.points]
        )

    def _show_empty(self) -> None:
        self.table.setRowCount(0)
        for label in self.stat_labels.values():
            label.setText("—")
            label.setStyleSheet("")
        self._update_chart([])

    def _update_chart(self, points: list) -> None:
        if not points:
            self.stack.setCurrentIndex(1)
            if HAS_QTCHARTS:
                old = self.chart_view.chart()
                self.chart_view.setChart(QChart())
                old.deleteLater()
            else:
                self.fallback_chart.set_points([])
            return

        self.stack.setCurrentIndex(0)
        if HAS_QTCHARTS:
            series = QLineSeries()
            series.setName("Prix (USD)")
            first_date, last_date = points[0][0], points[-1][0]
            values = [v for _, v in points]
            for point_date, value in points:
                moment = QDateTime(
                    QDate(point_date.year, point_date.month, point_date.day), QTime(0, 0)
                )
                series.append(moment.toMSecsSinceEpoch(), value)
            series.setPointsVisible(True)

            chart = QChart()
            chart.addSeries(series)
            chart.legend().setVisible(False)
            chart.setMargins(QMargins(4, 4, 4, 4))

            start_date, end_date = first_date, last_date
            if start_date == end_date:  # un seul relevé : évite un axe de plage nulle
                start_date = start_date - timedelta(days=3)
                end_date = end_date + timedelta(days=3)

            axis_x = QDateTimeAxis()
            axis_x.setFormat("dd/MM/yy")
            axis_x.setTitleText("Date")
            axis_x.setRange(
                QDateTime(QDate(start_date.year, start_date.month, start_date.day), QTime(0, 0)),
                QDateTime(QDate(end_date.year, end_date.month, end_date.day), QTime(0, 0)),
            )
            axis_y = QValueAxis()
            axis_y.setTitleText("Prix (USD)")
            axis_y.setLabelFormat("%.0f")
            margin = max((max(values) - min(values)) * 0.1, 10.0)
            axis_y.setRange(min(values) - margin, max(values) + margin)

            chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
            chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
            series.attachAxis(axis_x)
            series.attachAxis(axis_y)

            old = self.chart_view.chart()
            self.chart_view.setChart(chart)
            old.deleteLater()
        else:
            self.fallback_chart.set_points(
                [(point_date.strftime("%d/%m/%y"), value) for point_date, value in points]
            )
