from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QPainter, QPen, QColor, QBrush

HANDLE_SIZE = 8


def draw_selection_handles(painter: QPainter, rect: QRectF):
    painter.setPen(QPen(QColor(0, 122, 204), 1))
    painter.setBrush(QBrush(QColor(0, 122, 204)))

    cx = rect.center().x()
    cy = rect.center().y()
    hs = HANDLE_SIZE / 2

    positions = [
        (rect.left(), rect.top()),
        (cx, rect.top()),
        (rect.right(), rect.top()),
        (rect.right(), cy),
        (rect.right(), rect.bottom()),
        (cx, rect.bottom()),
        (rect.left(), rect.bottom()),
        (rect.left(), cy),
    ]

    for px, py in positions:
        painter.drawRect(QRectF(px - hs, py - hs, HANDLE_SIZE, HANDLE_SIZE))
