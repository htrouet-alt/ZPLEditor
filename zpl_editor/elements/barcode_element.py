from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QPen, QColor, QFont, QFontMetrics, QImage, QPixmap
from .base_element import BaseElement
import io

# All ZPL barcode types with display names and categories
BARCODE_TYPES = {
    # 1D Barcodes
    "code128":        {"name": "Code 128",           "category": "1D", "zpl_cmd": "BC"},
    "code39":         {"name": "Code 39",            "category": "1D", "zpl_cmd": "B3"},
    "code93":         {"name": "Code 93",            "category": "1D", "zpl_cmd": "BA"},
    "code11":         {"name": "Code 11",            "category": "1D", "zpl_cmd": "B1"},
    "ean13":          {"name": "EAN-13",             "category": "1D", "zpl_cmd": "BE"},
    "ean8":           {"name": "EAN-8",              "category": "1D", "zpl_cmd": "B8"},
    "upca":           {"name": "UPC-A",              "category": "1D", "zpl_cmd": "BU"},
    "upce":           {"name": "UPC-E",              "category": "1D", "zpl_cmd": "B9"},
    "codabar":        {"name": "Codabar",            "category": "1D", "zpl_cmd": "BK"},
    "i2of5":          {"name": "Interleaved 2 of 5", "category": "1D", "zpl_cmd": "B2"},
    "industrial2of5": {"name": "Industrial 2 of 5",  "category": "1D", "zpl_cmd": "BI"},
    "standard2of5":   {"name": "Standard 2 of 5",    "category": "1D", "zpl_cmd": "BJ"},
    "logmars":        {"name": "LOGMARS",            "category": "1D", "zpl_cmd": "BL"},
    "msi":            {"name": "MSI",                "category": "1D", "zpl_cmd": "BM"},
    "plessey":        {"name": "Plessey",            "category": "1D", "zpl_cmd": "BP"},
    "postnet":        {"name": "POSTNET",            "category": "1D", "zpl_cmd": "BZ"},
    "planet":         {"name": "Planet Code",        "category": "1D", "zpl_cmd": "B5"},
    "gs1databar":     {"name": "GS1 DataBar",        "category": "1D", "zpl_cmd": "BR"},
    "gs1_128":        {"name": "GS1-128",            "category": "1D", "zpl_cmd": "BC"},
    "upcean_ext":     {"name": "UPC/EAN Extensions", "category": "1D", "zpl_cmd": "BS"},
    # 2D Barcodes
    "datamatrix":     {"name": "Data Matrix",        "category": "2D", "zpl_cmd": "BX"},
    "pdf417":         {"name": "PDF417",             "category": "2D", "zpl_cmd": "B7"},
    "aztec":          {"name": "Aztec",              "category": "2D", "zpl_cmd": "BO"},
    "maxicode":       {"name": "MaxiCode",           "category": "2D", "zpl_cmd": "BD"},
    "micropdf417":    {"name": "Micro-PDF417",       "category": "2D", "zpl_cmd": "BF"},
    "codablockf":     {"name": "CODABLOCK-F",        "category": "2D", "zpl_cmd": "BB"},
    "code49":         {"name": "Code 49",            "category": "2D", "zpl_cmd": "B4"},
}

# python-barcode library mapping (types it can render)
PYTHON_BARCODE_MAP = {
    "code128": "code128",
    "code39": "code39",
    "ean13": "ean13",
    "ean8": "ean8",
    "upca": "upca",
    "codabar": "nw-7",
    "i2of5": "itf",
    "gs1_128": "gs1_128",
    "logmars": "code39",
}


class BarcodeElement(BaseElement):
    def __init__(self, x=0, y=0, barcode_type="code128", data="123456",
                 module_width=2, bar_height=100, orientation="N",
                 interpretation="Y", parent=None):
        super().__init__(x, y, parent)
        self._element_type = "barcode"
        self._properties = {
            "barcode_type": barcode_type,
            "data": data,
            "module_width": module_width,
            "bar_height": bar_height,
            "ratio": 3.0,
            "orientation": orientation,
            "interpretation": interpretation,
            "interpretation_above": "N",
        }
        self._barcode_image = None
        self._update_size_from_properties()

    def _update_size_from_properties(self):
        data = self._properties.get("data", "123456")
        mw = self._properties.get("module_width", 2)
        bh = self._properties.get("bar_height", 100)
        interp = self._properties.get("interpretation", "Y") == "Y"
        bc_type = self._properties.get("barcode_type", "code128")
        info = BARCODE_TYPES.get(bc_type, {})
        category = info.get("category", "1D")

        if category == "2D":
            mag = self._properties.get("magnification", 3)
            size = max(self._min_size, max(mag * 30, bh if bh > 0 else 80))
            self._dot_width = size
            self._dot_height = size
        else:
            # Code 128: each char = 11 modules + start(11) + stop(13) + checksum(11) + quiet zones
            # Other 1D: roughly similar. Multiply by module_width for dot width.
            ratio = self._properties.get("ratio", 3.0)
            n_chars = len(data) if data else 1
            modules_per_char = 11  # Code 128 standard
            overhead_modules = 35  # start + stop + checksum
            quiet_zone = 20  # quiet zones on both sides
            total_modules = n_chars * modules_per_char + overhead_modules
            estimated_width = total_modules * mw + quiet_zone
            self._dot_width = max(self._min_size, estimated_width)
            self._dot_height = max(self._min_size, bh + (25 if interp else 0))

        self._generate_barcode()

    def _sync_properties_from_size(self):
        self._properties["bar_height"] = max(20, self._dot_height - 20)

    def _generate_barcode(self):
        self._barcode_image = None
        try:
            import barcode
            from barcode.writer import ImageWriter

            data = self._properties.get("data", "123456")
            barcode_type = self._properties.get("barcode_type", "code128")
            if not data:
                return

            bc_name = PYTHON_BARCODE_MAP.get(barcode_type)
            if not bc_name:
                return

            writer = ImageWriter()
            bc = barcode.get(bc_name, data, writer=writer)

            buffer = io.BytesIO()
            bc.write(buffer, options={
                "module_width": 0.3,
                "module_height": max(5, self._properties.get("bar_height", 100) * 0.1),
                "write_text": self._properties.get("interpretation", "Y") == "Y",
                "font_size": 8,
                "text_distance": 2,
                "quiet_zone": 2,
            })
            buffer.seek(0)

            img = QImage()
            img.loadFromData(buffer.read())
            if not img.isNull():
                self._barcode_image = img
        except Exception:
            pass

    def _draw_content(self, painter: QPainter):
        bc_type = self._properties.get("barcode_type", "code128")
        info = BARCODE_TYPES.get(bc_type, {})
        category = info.get("category", "1D")

        if self._barcode_image and not self._barcode_image.isNull():
            target = self.content_rect()
            painter.drawImage(target, self._barcode_image)
        elif category == "2D":
            self._draw_2d_placeholder(painter, bc_type, info)
        else:
            self._draw_1d_placeholder(painter, bc_type, info)

    def _draw_1d_placeholder(self, painter: QPainter, bc_type: str, info: dict):
        rect = self.content_rect()
        painter.setPen(QPen(QColor(0, 0, 0)))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(rect)

        data = self._properties.get("data", "")
        display_name = info.get("name", bc_type.upper())

        # Draw barcode lines placeholder
        y_start = int(rect.y()) + 3
        bar_h = int(rect.height()) - 25
        x = int(rect.x()) + 5
        max_x = int(rect.x() + rect.width()) - 5
        for i, ch in enumerate(data[:30]):
            if x >= max_x:
                break
            w = 2
            if i % 2 == 0:
                painter.fillRect(x, y_start, w, max(5, bar_h), QColor(0, 0, 0))
            x += w + 1

        # Draw type label and data text
        font = QFont("Courier New", 7)
        painter.setFont(font)
        painter.setPen(QPen(QColor(80, 80, 80)))
        label_rect = QRectF(rect.x(), rect.y() + rect.height() - 18, rect.width(), 18)
        painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter,
                         f"[{display_name}] {data}")

    def _draw_2d_placeholder(self, painter: QPainter, bc_type: str, info: dict):
        rect = self.content_rect()
        display_name = info.get("name", bc_type.upper())
        data = self._properties.get("data", "")

        # Background
        painter.setPen(QPen(QColor(0, 0, 0), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(rect)

        # Draw a pattern to represent the 2D code
        margin = 4
        inner = QRectF(rect.x() + margin, rect.y() + margin,
                       rect.width() - margin * 2, rect.height() - margin * 2 - 16)

        # Draw a grid pattern
        cell_size = max(3, int(min(inner.width(), inner.height()) / 12))
        import hashlib
        hash_val = hashlib.md5((data or "placeholder").encode()).hexdigest()
        ix = int(inner.x())
        iy = int(inner.y())
        for row in range(int(inner.height() / cell_size)):
            for col in range(int(inner.width() / cell_size)):
                idx = (row * int(inner.width() / cell_size) + col) % len(hash_val)
                if int(hash_val[idx], 16) > 7:
                    painter.fillRect(ix + col * cell_size, iy + row * cell_size,
                                     cell_size - 1, cell_size - 1, QColor(0, 0, 0))

        # Type label
        font = QFont("Courier New", 7)
        painter.setFont(font)
        painter.setPen(QPen(QColor(80, 80, 80)))
        label_rect = QRectF(rect.x(), rect.y() + rect.height() - 14, rect.width(), 14)
        painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, f"[{display_name}]")

    def get_zpl_element(self):
        elem = super().get_zpl_element()
        elem.properties = dict(self._properties)
        return elem

    def mouseDoubleClickEvent(self, event):
        from PyQt6.QtWidgets import QInputDialog
        scene = self.scene()
        view = scene.views()[0] if scene and scene.views() else None
        text, ok = QInputDialog.getText(
            view, "Edit Barcode",
            "Barcode data:",
            text=self._properties.get("data", "")
        )
        if ok and text:
            self._properties["data"] = text
            self._update_size_from_properties()
            self.update()
            self.signals.property_changed.emit(self, "data", text)
