from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtWidgets import QGraphicsScene


def export_scene_to_png(scene: QGraphicsScene, path: str,
                         width: int, height: int) -> bool:
    try:
        rect = QRectF(0, 0, width, height)
        image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(0xFFFFFFFF)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        scene.render(painter, rect, rect)
        painter.end()
        return image.save(path, "PNG")
    except Exception:
        return False
