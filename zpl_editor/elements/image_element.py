from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QPen, QColor, QFont
from .base_element import BaseElement


class ImageElement(BaseElement):
    def __init__(self, x=0, y=0, width=100, height=100, parent=None):
        super().__init__(x, y, parent)
        self._element_type = "image"
        self._properties = {
            "width": width,
            "height": height,
            "format": "A",
            "data": "",
        }
        self._dot_width = width
        self._dot_height = height

    def _draw_content(self, painter: QPainter):
        painter.setPen(QPen(QColor(128, 128, 128), 1, Qt.PenStyle.DashLine))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(self.content_rect())
        font = QFont("Arial", 8)
        painter.setFont(font)
        painter.drawText(self.content_rect(), Qt.AlignmentFlag.AlignCenter, "[GFA Image]")
