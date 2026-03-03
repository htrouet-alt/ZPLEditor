from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QPainter, QPen, QColor, QFont, QFontMetrics


class Ruler(QWidget):
    HORIZONTAL = 0
    VERTICAL = 1

    def __init__(self, orientation=0, parent=None):
        super().__init__(parent)
        self._orientation = orientation
        self._dpi = 203
        self._zoom = 1.0
        self._origin_offset = 0.0
        self._mouse_pos = -1.0
        self._bg_color = QColor(37, 37, 38)
        self._text_color = QColor(160, 160, 160)
        self._tick_color = QColor(120, 120, 120)
        self._mouse_color = QColor(0, 122, 204)
        self._font = QFont("Segoe UI", 7)

        if orientation == self.HORIZONTAL:
            self.setFixedHeight(25)
            self.setMinimumWidth(50)
        else:
            self.setFixedWidth(30)
            self.setMinimumHeight(50)

    def set_params(self, zoom: float, origin_offset: float, dpi: int = 203):
        self._zoom = zoom
        self._origin_offset = origin_offset
        self._dpi = dpi
        self.update()

    def set_mouse_position(self, pos: float):
        self._mouse_pos = pos
        self.update()

    def _dots_to_mm(self, dots: float) -> float:
        return dots * 25.4 / self._dpi

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.fillRect(self.rect(), self._bg_color)
        painter.setFont(self._font)
        fm = QFontMetrics(self._font)

        mm_per_dot = 25.4 / self._dpi
        pixels_per_mm = self._zoom / mm_per_dot

        mm_step = 1.0
        if pixels_per_mm < 2:
            mm_step = 50.0
        elif pixels_per_mm < 4:
            mm_step = 20.0
        elif pixels_per_mm < 8:
            mm_step = 10.0
        elif pixels_per_mm < 20:
            mm_step = 5.0

        cm_step = mm_step * 10 if mm_step < 10 else mm_step

        if self._orientation == self.HORIZONTAL:
            self._draw_horizontal(painter, fm, mm_step, cm_step, pixels_per_mm)
        else:
            self._draw_vertical(painter, fm, mm_step, cm_step, pixels_per_mm)

        painter.end()

    def _draw_horizontal(self, painter, fm, mm_step, cm_step, px_per_mm):
        w = self.width()
        h = self.height()

        painter.setPen(QPen(QColor(60, 60, 60)))
        painter.drawLine(0, h - 1, w, h - 1)

        start_mm = self._dots_to_mm(self._origin_offset)
        end_mm = start_mm + w / px_per_mm

        mm = (start_mm // mm_step) * mm_step
        while mm <= end_mm:
            px = (mm - start_mm) * px_per_mm
            if 0 <= px <= w:
                is_cm = abs(mm % 10) < 0.01 or abs(mm % 10 - 10) < 0.01
                if is_cm:
                    painter.setPen(QPen(self._text_color))
                    tick_h = 10
                    cm_val = mm / 10.0
                    label = f"{cm_val:.0f}" if cm_val == int(cm_val) else f"{cm_val:.1f}"
                    painter.drawText(int(px) + 2, h - tick_h - 2, label)
                else:
                    painter.setPen(QPen(self._tick_color))
                    tick_h = 5
                painter.drawLine(int(px), h - 1, int(px), h - 1 - tick_h)
            mm += mm_step

        if self._mouse_pos >= 0:
            mouse_mm = self._dots_to_mm(self._mouse_pos)
            mx = (mouse_mm - start_mm) * px_per_mm
            if 0 <= mx <= w:
                painter.setPen(QPen(self._mouse_color, 1))
                painter.drawLine(int(mx), 0, int(mx), h)

    def _draw_vertical(self, painter, fm, mm_step, cm_step, px_per_mm):
        w = self.width()
        h = self.height()

        painter.setPen(QPen(QColor(60, 60, 60)))
        painter.drawLine(w - 1, 0, w - 1, h)

        start_mm = self._dots_to_mm(self._origin_offset)
        end_mm = start_mm + h / px_per_mm

        mm = (start_mm // mm_step) * mm_step
        while mm <= end_mm:
            py = (mm - start_mm) * px_per_mm
            if 0 <= py <= h:
                is_cm = abs(mm % 10) < 0.01 or abs(mm % 10 - 10) < 0.01
                if is_cm:
                    painter.setPen(QPen(self._text_color))
                    tick_w = 10
                    cm_val = mm / 10.0
                    label = f"{cm_val:.0f}" if cm_val == int(cm_val) else f"{cm_val:.1f}"
                    painter.save()
                    painter.translate(w - tick_w - 3, int(py) + 2)
                    painter.rotate(90)
                    painter.drawText(0, 0, label)
                    painter.restore()
                else:
                    painter.setPen(QPen(self._tick_color))
                    tick_w = 5
                painter.drawLine(w - 1, int(py), w - 1 - tick_w, int(py))
            mm += mm_step

        if self._mouse_pos >= 0:
            mouse_mm = self._dots_to_mm(self._mouse_pos)
            my = (mouse_mm - start_mm) * px_per_mm
            if 0 <= my <= h:
                painter.setPen(QPen(self._mouse_color, 1))
                painter.drawLine(0, int(my), w, int(my))


class RulerCorner(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(30, 25)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(37, 37, 38))
        painter.setPen(QPen(QColor(100, 100, 100)))
        painter.setFont(QFont("Segoe UI", 6))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "cm")
        painter.end()
