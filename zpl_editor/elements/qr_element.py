from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QPen, QColor, QFont, QImage
from .base_element import BaseElement
import io


class QRElement(BaseElement):
    def __init__(self, x=0, y=0, data="https://example.com", magnification=3,
                 qr_model=2, orientation="N", error_correction="M", parent=None):
        super().__init__(x, y, parent)
        self._element_type = "qrcode"
        self._properties = {
            "data": data,
            "magnification": magnification,
            "qr_model": qr_model,
            "orientation": orientation,
            "error_correction": error_correction,
        }
        self._qr_image = None
        self._update_size_from_properties()

    def _update_size_from_properties(self):
        mag = self._properties.get("magnification", 3)
        size = max(self._min_size, mag * 33)
        self._dot_width = size
        self._dot_height = size
        self._generate_qr()

    def _sync_properties_from_size(self):
        d = max(self._dot_width, self._dot_height)
        self._dot_width = d
        self._dot_height = d
        self._properties["magnification"] = max(1, d // 33)

    def _generate_qr(self):
        self._qr_image = None
        try:
            import qrcode

            data = self._properties.get("data", "")
            if data.startswith("QA,"):
                data = data[3:]
            elif data.startswith("QM,"):
                data = data[3:]
            if not data:
                return

            ec_level = self._properties.get("error_correction", "M")
            ec_map = {
                "L": qrcode.constants.ERROR_CORRECT_L,
                "M": qrcode.constants.ERROR_CORRECT_M,
                "Q": qrcode.constants.ERROR_CORRECT_Q,
                "H": qrcode.constants.ERROR_CORRECT_H,
            }
            qr = qrcode.QRCode(
                version=1,
                error_correction=ec_map.get(ec_level, qrcode.constants.ERROR_CORRECT_M),
                box_size=4,
                border=1,
            )
            qr.add_data(data)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")

            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            buffer.seek(0)

            qimg = QImage()
            qimg.loadFromData(buffer.read())
            if not qimg.isNull():
                self._qr_image = qimg
        except Exception:
            pass

    def _draw_content(self, painter: QPainter):
        if self._qr_image and not self._qr_image.isNull():
            target = self.content_rect()
            painter.drawImage(target, self._qr_image)
        else:
            painter.setPen(QPen(QColor(0, 0, 0)))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(self.content_rect())
            font = QFont("Courier New", 8)
            painter.setFont(font)
            painter.drawText(self.content_rect(), Qt.AlignmentFlag.AlignCenter, "[QR]")

    def get_zpl_element(self):
        elem = super().get_zpl_element()
        elem.properties = dict(self._properties)
        return elem

    def mouseDoubleClickEvent(self, event):
        from PyQt6.QtWidgets import QInputDialog
        scene = self.scene()
        view = scene.views()[0] if scene and scene.views() else None
        text, ok = QInputDialog.getText(
            view, "Edit QR Code",
            "QR data:",
            text=self._properties.get("data", "")
        )
        if ok:
            self._properties["data"] = text
            self._update_size_from_properties()
            self.update()
            self.signals.property_changed.emit(self, "data", text)
