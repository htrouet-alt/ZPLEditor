import os
from typing import Optional, Tuple

from PyQt6.QtCore import QBuffer, QByteArray, QIODevice, QRectF, Qt
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtWidgets import QApplication

from .zpl_parser import ZPLParser
from ..ui.canvas_scene import CanvasScene


_APP: Optional[QApplication] = None


class _RenderScene(CanvasScene):
    def drawBackground(self, painter: QPainter, rect: QRectF):
        painter.fillRect(rect, Qt.GlobalColor.white)


def _ensure_qt_app() -> QApplication:
    global _APP
    app = _APP or QApplication.instance()
    if app is None:
        if os.name != "nt" and not os.environ.get("DISPLAY"):
            os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        app = QApplication([])
        _APP = app
    else:
        _APP = app
    return app


def _resolve_size(
    parsed_width: int,
    parsed_height: int,
    width_inches: Optional[float],
    height_inches: Optional[float],
    dpi: int,
) -> Tuple[int, int]:
    if width_inches and height_inches and width_inches > 0 and height_inches > 0:
        return max(1, int(round(width_inches * dpi))), max(1, int(round(height_inches * dpi)))
    return max(1, int(parsed_width)), max(1, int(parsed_height))


def render_zpl_to_png_bytes(
    zpl_code: str,
    width_inches: Optional[float] = None,
    height_inches: Optional[float] = None,
    dpi: int = 203,
) -> Optional[bytes]:
    try:
        _ensure_qt_app()

        parser = ZPLParser()
        model = parser.parse(zpl_code)

        width, height = _resolve_size(
            model.settings.width,
            model.settings.height,
            width_inches,
            height_inches,
            dpi,
        )
        model.settings.width = width
        model.settings.height = height

        scene = _RenderScene()
        scene.set_grid_visible(False)
        scene.load_from_model(model)

        image = QImage(width, height, QImage.Format.Format_RGB32)
        image.fill(0xFFFFFFFF)

        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, False)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        source_rect = QRectF(0, 0, width, height)
        scene.render(painter, source_rect, source_rect)
        painter.end()

        byte_array = QByteArray()
        buffer = QBuffer(byte_array)
        if not buffer.open(QIODevice.OpenModeFlag.WriteOnly):
            return None
        ok = image.save(buffer, "PNG")
        buffer.close()
        if not ok:
            return None

        return bytes(byte_array)
    except Exception:
        return None
