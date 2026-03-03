from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QPainter, QPen, QColor


def draw_grid(painter: QPainter, rect: QRectF, grid_size: int = 10):
    minor_pen = QPen(QColor(230, 230, 230), 0.5)
    major_pen = QPen(QColor(200, 200, 200), 1.0)

    left = int(rect.left())
    right = int(rect.right())
    top = int(rect.top())
    bottom = int(rect.bottom())

    x = left - (left % grid_size)
    while x <= right:
        is_major = (x % (grid_size * 10) == 0)
        painter.setPen(major_pen if is_major else minor_pen)
        painter.drawLine(x, top, x, bottom)
        x += grid_size

    y = top - (top % grid_size)
    while y <= bottom:
        is_major = (y % (grid_size * 10) == 0)
        painter.setPen(major_pen if is_major else minor_pen)
        painter.drawLine(left, y, right, y)
        y += grid_size
