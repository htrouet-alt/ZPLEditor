from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QPen, QColor
from .base_element import BaseElement


class DiagonalLineElement(BaseElement):
    def __init__(self, x=0, y=0, width=100, height=100, thickness=1, color="B", orientation="R", parent=None):
        super().__init__(x, y, parent)
        self._element_type = "diagonal"
        self._properties = {
            "width": width,
            "height": height,
            "thickness": thickness,
            "color": color,
            "orientation": orientation,
        }
        self._dot_width = max(self._min_size, width)
        self._dot_height = max(self._min_size, height)

    def _update_size_from_properties(self):
        self._dot_width = max(self._min_size, self._properties.get("width", 100))
        self._dot_height = max(self._min_size, self._properties.get("height", 100))

    def _sync_properties_from_size(self):
        self._properties["width"] = self._dot_width
        self._properties["height"] = self._dot_height

    def _draw_content(self, painter: QPainter):
        color = QColor(0, 0, 0) if self._properties.get("color", "B") == "B" else QColor(255, 255, 255)
        thickness = self._properties.get("thickness", 1)
        orientation = self._properties.get("orientation", "R")

        pen = QPen(color, thickness)
        painter.setPen(pen)

        if orientation == "R":
            painter.drawLine(0, 0, self._dot_width, self._dot_height)
        else:
            painter.drawLine(self._dot_width, 0, 0, self._dot_height)

    def get_zpl_element(self):
        elem = super().get_zpl_element()
        elem.properties = dict(self._properties)
        return elem
