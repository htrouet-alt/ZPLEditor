from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QPen, QColor, QFont, QImage, qRgb
from .base_element import BaseElement

_BLACK = qRgb(0, 0, 0)
_WHITE = qRgb(255, 255, 255)


class ImageElement(BaseElement):
    def __init__(self, x=0, y=0, width=100, height=100, parent=None):
        super().__init__(x, y, parent)
        self._element_type = "image"
        self._properties = {
            "width": width,
            "height": height,
            "format": "A",
            "data": "",
            "bytes_per_row": 0,
            "total_bytes": 0,
        }
        self._dot_width = width
        self._dot_height = height
        self._rendered_image = None

    def _update_size_from_properties(self):
        w = self._properties.get("width", 100)
        h = self._properties.get("height", 100)
        self._dot_width = max(self._min_size, w)
        self._dot_height = max(self._min_size, h)
        self._render_gfa()

    def _render_gfa(self):
        """Decode GFA hex data and create a QImage."""
        self._rendered_image = None
        hex_data = self._properties.get("data", "")
        bytes_per_row = self._properties.get("bytes_per_row", 0)
        if not hex_data or not bytes_per_row:
            return

        try:
            hex_data = hex_data.replace('\n', '').replace('\r', '').replace(' ', '')

            width_pixels = bytes_per_row * 8
            total_hex_bytes = len(hex_data) // 2
            height_pixels = total_hex_bytes // bytes_per_row if bytes_per_row > 0 else 0

            if width_pixels <= 0 or height_pixels <= 0:
                return

            # Use RGB32 for reliable cross-platform rendering
            img = QImage(width_pixels, height_pixels, QImage.Format.Format_RGB32)
            img.fill(_WHITE)

            for row in range(height_pixels):
                for col_byte in range(bytes_per_row):
                    hex_offset = (row * bytes_per_row + col_byte) * 2
                    if hex_offset + 2 > len(hex_data):
                        break
                    byte_val = int(hex_data[hex_offset:hex_offset + 2], 16)
                    for bit in range(8):
                        pixel_x = col_byte * 8 + bit
                        if pixel_x < width_pixels:
                            # GFA: 1 bit = black pixel, 0 bit = white pixel
                            if byte_val & (0x80 >> bit):
                                img.setPixel(pixel_x, row, _BLACK)

            self._rendered_image = img
            self._dot_width = width_pixels
            self._dot_height = height_pixels
        except Exception as e:
            print(f"[ImageElement] GFA decode error: {e}")

    def _draw_content(self, painter: QPainter):
        if self._rendered_image and not self._rendered_image.isNull():
            painter.drawImage(self.content_rect(), self._rendered_image)
        else:
            painter.setPen(QPen(QColor(128, 128, 128), 1, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(self.content_rect())
            font = QFont("Arial", 8)
            painter.setFont(font)
            painter.drawText(self.content_rect(), Qt.AlignmentFlag.AlignCenter, "[GFA Image]")

    def get_zpl_element(self):
        elem = super().get_zpl_element()
        elem.properties = dict(self._properties)
        return elem
