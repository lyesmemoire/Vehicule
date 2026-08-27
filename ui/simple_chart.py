"""Graphe d'évolution de secours, dessiné avec QPainter (sans dépendance QtCharts).

Utilisé uniquement si le module PySide6.QtCharts n'est pas disponible ;
le rendu reste lisible : axes, grille, courbe, points, premier/dernier prix.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QWidget


class SimpleLineChart(QWidget):
    """Courbe 2D minimaliste : liste de points (étiquette, valeur)."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._points: list[tuple[str, float]] = []
        self.setMinimumHeight(260)

    def set_points(self, points: list[tuple[str, float]]) -> None:
        self._points = list(points)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        area = QRectF(self.rect()).adjusted(64, 18, -18, -32)
        if not self._points:
            painter.setPen(QColor("#94a3b8"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Aucune donnée à afficher.")
            return

        values = [v for _, v in self._points]
        vmin, vmax = min(values), max(values)
        if vmax == vmin:
            pad = max(abs(vmax) * 0.1, 1.0)
            vmin, vmax = vmin - pad, vmax + pad

        def x_at(i: int) -> float:
            if len(self._points) == 1:
                return area.center().x()
            return area.left() + (area.width() * i / (len(self._points) - 1))

        def y_at(v: float) -> float:
            return area.bottom() - (area.height() * (v - vmin) / (vmax - vmin))

        # Grille + étiquettes de l'axe Y
        font = painter.font()
        font.setPointSize(8)
        painter.setFont(font)
        for i in range(5):
            value = vmin + (vmax - vmin) * i / 4
            y = y_at(value)
            painter.setPen(QPen(QColor("#eef2f6"), 1))
            painter.drawLine(QPointF(area.left(), y), QPointF(area.right(), y))
            painter.setPen(QColor("#64748b"))
            painter.drawText(
                QRectF(0, y - 8, area.left() - 8, 16),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                f"{value:,.0f}".replace(",", " "),
            )

        # Axes
        painter.setPen(QPen(QColor("#cbd5e1"), 1))
        painter.drawLine(QPointF(area.left(), area.top()), QPointF(area.left(), area.bottom()))
        painter.drawLine(QPointF(area.left(), area.bottom()), QPointF(area.right(), area.bottom()))

        # Courbe
        polygon = QPolygonF([QPointF(x_at(i), y_at(v)) for i, (_, v) in enumerate(self._points)])
        painter.setPen(QPen(QColor("#1d4ed8"), 2))
        painter.drawPolyline(polygon)

        # Points (le dernier en vert)
        for i, (_label, value) in enumerate(self._points):
            color = QColor("#15803d") if i == len(self._points) - 1 else QColor("#1d4ed8")
            painter.setPen(QPen(QColor("#ffffff"), 1))
            painter.setBrush(color)
            painter.drawEllipse(QPointF(x_at(i), y_at(value)), 4.5, 4.5)

        # Étiquettes de dates (première, médiane, dernière)
        painter.setPen(QColor("#64748b"))
        indices = sorted({0, (len(self._points) - 1) // 2, len(self._points) - 1})
        for i in indices:
            label = self._points[i][0]
            x = x_at(i)
            painter.drawText(
                QRectF(x - 45, area.bottom() + 6, 90, 16),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                label,
            )
        painter.end()
