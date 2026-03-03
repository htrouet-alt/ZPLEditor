from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QPen, QColor, QFont, QFontMetrics
from .base_element import BaseElement, HANDLE_HALF
from ..fonts.font_mapper import zpl_font_to_qfont


class TextElement(BaseElement):
    def __init__(self, x=0, y=0, text="Text", font_id="0", font_height=30, font_width=0, orientation="N", parent=None):
        super().__init__(x, y, parent)
        self._element_type = "text"
        self._font_descent = 0
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
        font_width = self._properties.get("font_width", 0)
        self._font_descent = fm.descent()

        # Calculate width: if ZPL font_width is specified, use character count * width
        if font_width and text:
            self._dot_width = max(self._min_size, font_width * len(text))
        else:
            rect = fm.boundingRect(text if text else "X")
            self._dot_width = max(self._min_size, rect.width() + 4)

        # Use ZPL font_height as element height to match label layout;
        # fall back to font metrics if no explicit height
        if zpl_height > 0:
            self._dot_height = max(self._min_size, zpl_height)
        else:
            rect = fm.boundingRect(text if text else "X")
            self._dot_height = max(self._min_size, rect.height() + 2)

    def _get_qfont(self) -> QFont:
        font_id = self._properties.get("font", "0")
        height = self._properties.get("font_height", 30)
        font_name = self._properties.get("font_name", "")
        # Don't pass width to font_mapper; width scaling is handled
        # via painter.scale() in _draw_content for precise control
        return zpl_font_to_qfont(font_id, height, 0, font_name)

    def _sync_properties_from_size(self):
        self._properties["font_height"] = max(8, self._dot_height)
        if self._properties.get("font_width"):
            self._properties["font_width"] = max(5, self._dot_width)

    def boundingRect(self) -> QRectF:
        margin = HANDLE_HALF + 2
        # Extend bounding rect to include font descenders so text is not clipped
        extra_descent = self._font_descent
        return QRectF(-margin, -margin,
                       self._dot_width + margin * 2,
                       self._dot_height + extra_descent + margin * 2)

    def _draw_content(self, painter: QPainter):
        font = self._get_qfont()
        painter.setFont(font)
        painter.setPen(QPen(QColor(0, 0, 0)))
        text = self._properties.get("data", "")
        orientation = self._properties.get("orientation", "N")
        font_width = self._properties.get("font_width", 0)
        descent = self._font_descent

        # Calculate horizontal scale factor to match ZPL font_width
        scale_x = 1.0
        if font_width and text:
            fm = QFontMetrics(font)
            natural_width = fm.horizontalAdvance(text)
            desired_width = font_width * len(text)
            if natural_width > 0:
                scale_x = desired_width / natural_width

        if orientation == "N":
            self._draw_scaled_text(painter, text, scale_x,
                                   QRectF(0, 0, self._dot_width, self._dot_height + descent),
                                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        elif orientation == "R":
            painter.save()
            painter.translate(self._dot_width, 0)
            painter.rotate(90)
            self._draw_scaled_text(painter, text, scale_x,
                                   QRectF(0, 0, self._dot_height, self._dot_width + descent),
                                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            painter.restore()
        elif orientation == "I":
            painter.save()
            painter.translate(self._dot_width, self._dot_height)
            painter.rotate(180)
            self._draw_scaled_text(painter, text, scale_x,
                                   QRectF(0, 0, self._dot_width, self._dot_height + descent),
                                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            painter.restore()
        elif orientation == "B":
            painter.save()
            painter.translate(0, self._dot_height)
            painter.rotate(270)
            self._draw_scaled_text(painter, text, scale_x,
                                   QRectF(0, 0, self._dot_height, self._dot_width + descent),
                                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            painter.restore()

    def _draw_scaled_text(self, painter, text, scale_x, rect, alignment):
        """Draw text with optional horizontal scaling for ZPL font_width."""
        if abs(scale_x - 1.0) > 0.01:
            painter.save()
            painter.scale(scale_x, 1.0)
            scaled_rect = QRectF(rect.x() / scale_x, rect.y(),
                                 rect.width() / scale_x, rect.height())
            painter.drawText(scaled_rect, alignment, text)
            painter.restore()
        else:
            painter.drawText(rect, alignment, text)

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
