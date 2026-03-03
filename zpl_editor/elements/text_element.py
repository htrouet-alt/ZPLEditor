from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QPen, QColor, QFont, QFontMetrics
from .base_element import BaseElement
from ..fonts.font_mapper import zpl_font_to_qfont


class TextElement(BaseElement):
    def __init__(self, x=0, y=0, text="Text", font_id="0", font_height=30, font_width=0, orientation="N", parent=None):
        super().__init__(x, y, parent)
        self._element_type = "text"
        self._properties = {
            "data": text,
            "font": font_id,
            "font_height": font_height,
            "font_width": font_width,
            "orientation": orientation,
        }
        self._update_size_from_properties()

    def _update_size_from_properties(self):
        font = self._get_qfont()
        fm = QFontMetrics(font)
        text = self._properties.get("data", "Text")
        zpl_height = self._properties.get("font_height", 0)
        rect = fm.boundingRect(text if text else "X")
        self._dot_width = max(self._min_size, rect.width() + 4)
        # Use ZPL font_height as element height to match label layout;
        # fall back to font metrics if no explicit height
        if zpl_height > 0:
            self._dot_height = max(self._min_size, zpl_height)
        else:
            self._dot_height = max(self._min_size, rect.height() + 2)

    def _get_qfont(self) -> QFont:
        font_id = self._properties.get("font", "0")
        height = self._properties.get("font_height", 30)
        width = self._properties.get("font_width", 0)
        font_name = self._properties.get("font_name", "")
        return zpl_font_to_qfont(font_id, height, width, font_name)

    def _sync_properties_from_size(self):
        self._properties["font_height"] = max(8, self._dot_height)
        if self._properties.get("font_width"):
            self._properties["font_width"] = max(5, self._dot_width)

    def _draw_content(self, painter: QPainter):
        font = self._get_qfont()
        painter.setFont(font)
        painter.setPen(QPen(QColor(0, 0, 0)))
        text = self._properties.get("data", "")
        orientation = self._properties.get("orientation", "N")

        if orientation == "N":
            painter.drawText(self.content_rect(), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, text)
        elif orientation == "R":
            painter.save()
            painter.translate(self._dot_width, 0)
            painter.rotate(90)
            painter.drawText(QRectF(0, 0, self._dot_height, self._dot_width),
                           Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)
            painter.restore()
        elif orientation == "I":
            painter.save()
            painter.translate(self._dot_width, self._dot_height)
            painter.rotate(180)
            painter.drawText(QRectF(0, 0, self._dot_width, self._dot_height),
                           Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)
            painter.restore()
        elif orientation == "B":
            painter.save()
            painter.translate(0, self._dot_height)
            painter.rotate(270)
            painter.drawText(QRectF(0, 0, self._dot_height, self._dot_width),
                           Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)
            painter.restore()

    def get_zpl_element(self):
        elem = super().get_zpl_element()
        elem.properties = dict(self._properties)
        return elem

    def mouseDoubleClickEvent(self, event):
        from PyQt6.QtWidgets import QInputDialog
        scene = self.scene()
        view = scene.views()[0] if scene and scene.views() else None
        text, ok = QInputDialog.getText(
            view, "Edit Text",
            "Text content:",
            text=self._properties.get("data", "")
        )
        if ok:
            self._properties["data"] = text
            self._update_size_from_properties()
            self.update()
            self.signals.property_changed.emit(self, "data", text)
