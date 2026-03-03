from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QPen, QColor, QBrush
from .base_element import BaseElement


class CircleElement(BaseElement):
    def __init__(self, x=0, y=0, diameter=100, thickness=1, color="B", parent=None):
        super().__init__(x, y, parent)
        self._element_type = "circle"
        self._properties = {
            "diameter": diameter,
            "thickness": thickness,
            "color": color,
        }
        self._dot_width = max(self._min_size, diameter)
        self._dot_height = max(self._min_size, diameter)

    def _update_size_from_properties(self):
        d = max(self._min_size, self._properties.get("diameter", 100))
        self._dot_width = d
        self._dot_height = d

    def _sync_properties_from_size(self):
        d = max(self._dot_width, self._dot_height)
        self._dot_width = d
        self._dot_height = d
        self._properties["diameter"] = d

    def _draw_content(self, painter: QPainter):
        color = QColor(0, 0, 0) if self._properties.get("color", "B") == "B" else QColor(255, 255, 255)
        thickness = self._properties.get("thickness", 1)
        d = self._properties.get("diameter", self._dot_width)

        pen = QPen(color, thickness)
        painter.setPen(pen)
        if thickness >= d / 2:
            painter.setBrush(QBrush(color))
        else:
            painter.setBrush(Qt.BrushStyle.NoBrush)
        half_t = thickness / 2
        painter.drawEllipse(QRectF(half_t, half_t, d - thickness, d - thickness))

    def get_zpl_element(self):
        elem = super().get_zpl_element()
        elem.properties = dict(self._properties)
        return elem
