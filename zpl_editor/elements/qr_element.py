from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QPen, QColor, QFont, QImage
from .base_element import BaseElement
import io
import re


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
        self._qr_version = None  # actual version after generation
        self._update_size_from_properties()

    def _strip_fd_prefix(self, data):
        """Strip ZPL QR ^FD prefix: {ECC}{mode},{data}.

        ZPL format: ^FD{error_correction}{input_mode},{actual_data}^FS
        Error correction: H, Q, M, L
        Input mode: A (auto), M (manual)
        """
        m = re.match(r'^([HQML])([AM]),', data)
        if m:
            ec = m.group(1)
            return data[m.end():], ec
        return data, None

    def _update_size_from_properties(self):
        self._generate_qr()
        mag = self._properties.get("magnification", 3)
        if self._qr_version:
            modules = 4 * self._qr_version + 17
        else:
            modules = 33  # fallback for version 4
        size = max(self._min_size, mag * modules)
        self._dot_width = size
        self._dot_height = size

    def _sync_properties_from_size(self):
        d = max(self._dot_width, self._dot_height)
        self._dot_width = d
        self._dot_height = d
        modules = (4 * self._qr_version + 17) if self._qr_version else 33
        self._properties["magnification"] = max(1, d // modules)

    def _generate_qr(self):
        self._qr_image = None
        self._qr_version = None
        try:
            import qrcode

            data = self._properties.get("data", "")
            data, ec_from_fd = self._strip_fd_prefix(data)
            if not data:
                return

            # Use ECC from FD prefix if available, otherwise from property
            ec_level = ec_from_fd or self._properties.get("error_correction", "M")
            ec_map = {
                "L": qrcode.constants.ERROR_CORRECT_L,
                "M": qrcode.constants.ERROR_CORRECT_M,
                "Q": qrcode.constants.ERROR_CORRECT_Q,
                "H": qrcode.constants.ERROR_CORRECT_H,
            }
            mag = self._properties.get("magnification", 3)
            qr = qrcode.QRCode(
                version=1,
                error_correction=ec_map.get(ec_level, qrcode.constants.ERROR_CORRECT_M),
                box_size=mag,
                border=0,
            )
            qr.add_data(data)
            qr.make(fit=True)
            self._qr_version = qr.version
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
