from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QPen, QColor, QFont, QImage, QTransform
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

# python-barcode library mapping (fallback for types we don't natively render)
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

# Code 128 binary patterns (11 bits per symbol, 13 bits for STOP)
# Each bit: 1=bar(black), 0=space(white)
# Values 0-105 are data/control symbols, 106 is STOP
_CODE128_BITS = [
    0b11011001100, 0b11001101100, 0b11001100110, 0b10010011000,  # 0-3
    0b10010001100, 0b10001001100, 0b10011001000, 0b10011000100,  # 4-7
    0b10001100100, 0b11001001000, 0b11001000100, 0b11000100100,  # 8-11
    0b10110011100, 0b10011011100, 0b10011001110, 0b10111001100,  # 12-15
    0b10011101100, 0b10011100110, 0b11001110010, 0b11001011100,  # 16-19
    0b11001001110, 0b11011100100, 0b11001110100, 0b11101101110,  # 20-23
    0b11101001100, 0b11100101100, 0b11100100110, 0b11101100100,  # 24-27
    0b11100110100, 0b11100110010, 0b11011011000, 0b11011000110,  # 28-31
    0b11000110110, 0b10100011000, 0b10001011000, 0b10001000110,  # 32-35
    0b10110001000, 0b10001101000, 0b10001100010, 0b11010001000,  # 36-39
    0b11000101000, 0b11000100010, 0b10110111000, 0b10110001110,  # 40-43
    0b10001101110, 0b10111011000, 0b10111000110, 0b10001110110,  # 44-47
    0b11101110110, 0b11010001110, 0b11000101110, 0b11011101000,  # 48-51
    0b11011100010, 0b11011101110, 0b11101011000, 0b11101000110,  # 52-55
    0b11100010110, 0b11101101000, 0b11101100010, 0b11100011010,  # 56-59
    0b11101111010, 0b11001000010, 0b11110001010, 0b10100110000,  # 60-63
    0b10100001100, 0b10010110000, 0b10010000110, 0b10000101100,  # 64-67
    0b10000100110, 0b10110010000, 0b10110000100, 0b10011010000,  # 68-71
    0b10011000010, 0b10000110100, 0b10000110010, 0b11000010010,  # 72-75
    0b11001010000, 0b11110111010, 0b11000010100, 0b10001111010,  # 76-79
    0b10100111100, 0b10010111100, 0b10010011110, 0b10111100100,  # 80-83
    0b10011110100, 0b10011110010, 0b11110100100, 0b11110010100,  # 84-87
    0b11110010010, 0b11011011110, 0b11011110110, 0b11110110110,  # 88-91
    0b10101111000, 0b10100011110, 0b10001011110, 0b10111101000,  # 92-95
    0b10111100010, 0b11110101000, 0b11110100010, 0b10111011110,  # 96-99
    0b10111101110, 0b11101011110, 0b11110101110, 0b11010000100,  # 100-103
    0b11010010000, 0b11010011100,                                 # 104-105
]
_CODE128_STOP_BITS = 0b1100011101011  # 13 bits

_START_A = 103
_START_B = 104
_START_C = 105
_CODE_A = 101
_CODE_B = 100
_CODE_C = 99


def _bits_to_widths(pattern, nbits):
    """Convert a binary pattern to a list of bar/space widths."""
    bits = format(pattern, f'0{nbits}b')
    widths = []
    count = 1
    for i in range(1, len(bits)):
        if bits[i] == bits[i - 1]:
            count += 1
        else:
            widths.append(count)
            count = 1
    widths.append(count)
    return widths


def _encode_code128(data):
    """Encode data as Code 128 and return list of module widths (bar/space alternating).

    Handles Code B for ASCII and Code C for digit pairs.
    Supports >7 prefix for forced Code C mode, >: prefix for forced Code B mode.
    """
    if not data:
        return []

    # Check for explicit subset prefixes
    force_code_b = data.startswith(">:")
    if force_code_b:
        data = data[2:]
    force_code_c = data.startswith(">7")
    if force_code_c:
        data = data[2:]

    # Decide encoding: Code C for forced or auto-detected numeric data
    # Auto-detection only kicks in when no explicit prefix is given
    if force_code_c:
        use_code_c = True
    elif force_code_b:
        use_code_c = False
    else:
        use_code_c = data.isdigit() and len(data) >= 4 and len(data) % 2 == 0

    if use_code_c:
        values = [_START_C]
        for i in range(0, len(data) - 1, 2):
            values.append(int(data[i:i + 2]))
        # Handle leftover odd character by switching to Code B
        if len(data) % 2 == 1:
            values.append(_CODE_B)
            values.append(ord(data[-1]) - 32)
    else:
        values = [_START_B]
        for ch in data:
            code = ord(ch) - 32
            if 0 <= code <= 95:
                values.append(code)
            else:
                values.append(0)  # fallback for out-of-range chars

    # Compute check digit
    checksum = values[0]
    for i, v in enumerate(values[1:], 1):
        checksum += i * v
    checksum %= 103
    values.append(checksum)

    # Convert values to module widths
    all_widths = []
    for v in values:
        all_widths.extend(_bits_to_widths(_CODE128_BITS[v], 11))
    # Add stop pattern
    all_widths.extend(_bits_to_widths(_CODE128_STOP_BITS, 13))
    return all_widths


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
        self._barcode_widths = None  # Code 128 module widths for direct drawing
        self._barcode_image = None   # Fallback rendered image
        self._update_size_from_properties()

    def _update_size_from_properties(self):
        data = self._properties.get("data", "123456")
        mw = self._properties.get("module_width", 2)
        bh = self._properties.get("bar_height", 100)
        interp = self._properties.get("interpretation", "Y") == "Y"
        bc_type = self._properties.get("barcode_type", "code128")
        orientation = (self._properties.get("orientation", "N") or "N").upper()
        info = BARCODE_TYPES.get(bc_type, {})
        category = info.get("category", "1D")

        self._barcode_widths = None
        self._barcode_image = None

        if category == "2D":
            mag = self._properties.get("magnification", 3)
            base_w = max(self._min_size, max(mag * 30, bh if bh > 0 else 80))
            base_h = base_w
        elif bc_type in ("code128", "gs1_128"):
            # Direct Code 128 encoding - pixel-perfect
            widths = _encode_code128(data if data else "0")
            if widths:
                self._barcode_widths = widths
                total_modules = sum(widths)
                base_w = total_modules * mw
                base_h = bh
            else:
                base_w = max(self._min_size, 100)
                base_h = max(self._min_size, bh)
        else:
            # Fallback for other barcode types: use python-barcode
            self._generate_barcode_image()
            if self._barcode_image and not self._barcode_image.isNull():
                base_w = self._barcode_image.width()
                base_h = self._barcode_image.height()
            else:
                n_chars = len(data) if data else 1
                total_modules = n_chars * 11 + 35
                base_w = max(self._min_size, total_modules * mw)
                base_h = max(self._min_size, bh)

        if orientation in ("R", "B"):
            self._dot_width = base_h
            self._dot_height = base_w
        else:
            self._dot_width = base_w
            self._dot_height = base_h

    def _sync_properties_from_size(self):
        self._properties["bar_height"] = max(20, self._dot_height - 20)

    def _generate_barcode_image(self):
        """Fallback barcode generation using python-barcode library."""
        self._barcode_image = None
        try:
            import barcode
            from barcode.writer import ImageWriter

            data = self._properties.get("data", "123456")
            barcode_type = self._properties.get("barcode_type", "code128")
            mw = self._properties.get("module_width", 2)
            bh = self._properties.get("bar_height", 100)
            if not data:
                return

            bc_name = PYTHON_BARCODE_MAP.get(barcode_type)
            if not bc_name:
                return

            dpi = 203
            mm_per_dot = 25.4 / dpi
            module_width_mm = mw * mm_per_dot
            module_height_mm = bh * mm_per_dot

            writer = ImageWriter()
            bc = barcode.get(bc_name, data, writer=writer)

            buffer = io.BytesIO()
            bc.write(buffer, options={
                "module_width": module_width_mm,
                "module_height": module_height_mm,
                "write_text": False,
                "quiet_zone": 0,
                "dpi": dpi,
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
        orientation = (self._properties.get("orientation", "N") or "N").upper()

        if self._barcode_widths:
            # Direct pixel-perfect Code 128 drawing
            self._draw_code128_direct(painter, orientation)
        elif self._barcode_image and not self._barcode_image.isNull():
            target = self.content_rect()
            painter.drawImage(target, self._get_oriented_image(self._barcode_image))
        elif category == "2D":
            self._draw_2d_placeholder(painter, bc_type, info)
        else:
            self._draw_1d_placeholder(painter, bc_type, info)

    def _draw_code128_direct(self, painter: QPainter, orientation: str):
        """Draw Code 128 barcode directly at exact module_width pixels."""
        mw = self._properties.get("module_width", 2)
        bh = self._properties.get("bar_height", 100)
        widths = self._barcode_widths
        if not widths:
            return

        painter.save()

        # Apply rotation for orientation
        if orientation == "R":
            painter.translate(self._dot_width, 0)
            painter.rotate(90)
        elif orientation == "I":
            painter.translate(self._dot_width, self._dot_height)
            painter.rotate(180)
        elif orientation == "B":
            painter.translate(0, self._dot_height)
            painter.rotate(270)

        # Draw bars: alternating bar/space starting with bar
        x = 0
        is_bar = True
        for w in widths:
            px_width = w * mw
            if is_bar:
                painter.fillRect(int(x), 0, int(px_width), int(bh), QColor(0, 0, 0))
            x += px_width
            is_bar = not is_bar

        painter.restore()

    def _get_oriented_image(self, image: QImage) -> QImage:
        orientation = (self._properties.get("orientation", "N") or "N").upper()
        angle_map = {"N": 0, "R": 90, "I": 180, "B": 270}
        angle = angle_map.get(orientation, 0)
        if angle == 0:
            return image
        transform = QTransform()
        transform.rotate(angle)
        return image.transformed(transform, Qt.TransformationMode.FastTransformation)

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
