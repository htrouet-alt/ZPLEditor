from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QPen, QColor, QBrush
from .base_element import BaseElement


class BoxElement(BaseElement):
    def __init__(self, x=0, y=0, width=100, height=100, thickness=1, color="B", rounding=0, parent=None):
        super().__init__(x, y, parent)
        self._element_type = "box"
        self._properties = {
            "width": width,
            "height": height,
            "thickness": thickness,
            "color": color,
            "rounding": rounding,
        }
        self._dot_width = max(self._min_size, width)
        self._dot_height = max(self._min_size, height)

    def _update_size_from_properties(self):
        self._dot_width = max(self._min_size, self._properties.get("width", 100))
        self._dot_height = max(self._min_size, self._properties.get("height", 100))

    def _sync_properties_from_size(self):
        self._properties["width"] = self._dot_width
        self._properties["height"] = self._dot_height

    def _is_line(self) -> bool:
        t = self._properties.get("thickness", 1)
        w = self._properties.get("width", 0)
        h = self._properties.get("height", 0)
        return w <= t or h <= t

    def _draw_content(self, painter: QPainter):
        color = QColor(0, 0, 0) if self._properties.get("color", "B") == "B" else QColor(255, 255, 255)
        thickness = self._properties.get("thickness", 1)
        rounding = self._properties.get("rounding", 0)
        w = self._dot_width
        h = self._dot_height

        if self._is_line():
            # Use fillRect for pixel-perfect line rendering (avoids QPen centering offsets).
            # Use property values for actual ZPL size (dot_width/dot_height may be clamped by _min_size).
            prop_w = self._properties.get("width", w)
            prop_h = self._properties.get("height", h)
            painter.fillRect(QRectF(0, 0, prop_w, prop_h), color)
        elif thickness >= min(w, h) / 2:
            # Filled box
            painter.fillRect(QRectF(0, 0, w, h), color)
        elif rounding > 0:
            # Rounded box - use QPen
            pen = QPen(color, thickness)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            half_t = thickness / 2
            rect = QRectF(half_t, half_t, w - thickness, h - thickness)
            radius = rounding * min(w, h) / 16
            painter.drawRoundedRect(rect, radius, radius)
        else:
            # Non-filled, non-rounded box: draw each border edge with fillRect
            # for pixel-perfect rendering (avoids QPen centering issues)
            t = thickness
            painter.fillRect(QRectF(0, 0, w, t), color)         # top
            painter.fillRect(QRectF(0, h - t, w, t), color)     # bottom
            painter.fillRect(QRectF(0, 0, t, h), color)         # left
            painter.fillRect(QRectF(w - t, 0, t, h), color)     # right

    def get_zpl_element(self):
        elem = super().get_zpl_element()
        elem.properties = dict(self._properties)
        return elem
