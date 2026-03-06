from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QListWidget,
                              QListWidgetItem, QHBoxLayout)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon
from ..core.label_model import LabelModel
from ..core.zpl_commands import ZPLElement


class LinterPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QHBoxLayout()
        header.setContentsMargins(8, 4, 8, 4)
        self._title = QLabel("Linter Warnings")
        self._title.setStyleSheet("font-weight: bold; font-size: 12px; padding: 2px;")
        header.addWidget(self._title)
        self._count_label = QLabel("(0)")
        self._count_label.setStyleSheet("color: #808080; font-size: 12px; padding: 2px;")
        header.addWidget(self._count_label)
        header.addStretch()

        header_widget = QWidget()
        header_widget.setLayout(header)
        layout.addWidget(header_widget)

        self._list = QListWidget()
        self._list.setAlternatingRowColors(True)
        self._list.setStyleSheet("""
            QListWidget {
                background-color: #1E1E1E;
                border: none;
                font-family: Consolas, monospace;
                font-size: 11px;
            }
            QListWidget::item {
                padding: 3px 8px;
                border-bottom: 1px solid #2D2D2D;
            }
            QListWidget::item:alternate {
                background-color: #252526;
            }
            QListWidget::item:selected {
                background-color: #094771;
            }
        """)
        layout.addWidget(self._list)

    def validate(self, model: LabelModel, label_w: int = None, label_h: int = None, canvas_elements=None) -> list:
        warnings = []
        settings = model.settings
        if label_w is None:
            label_w = settings.width
        if label_h is None:
            label_h = settings.height

        # Check overflow using actual canvas element bounds
        if canvas_elements:
            for ce in canvas_elements:
                x = ce.dot_x
                y = ce.dot_y
                w = ce.dot_width
                h = ce.dot_height
                etype = ce.element_type
                if x < 0:
                    warnings.append({
                        "level": "warning",
                        "cmd": "^FO",
                        "msg": f"{etype.capitalize()} taşıyor: sol kenar ({x}) < 0 — konum ({x},{y})"
                    })
                if y < 0:
                    warnings.append({
                        "level": "warning",
                        "cmd": "^FO",
                        "msg": f"{etype.capitalize()} taşıyor: üst kenar ({y}) < 0 — konum ({x},{y})"
                    })
                if x + w > label_w:
                    warnings.append({
                        "level": "warning",
                        "cmd": "^FO",
                        "msg": f"{etype.capitalize()} taşıyor: sağ kenar ({x + w}) > etiket genişliği ({label_w}) — konum ({x},{y})"
                    })
                if y + h > label_h:
                    warnings.append({
                        "level": "warning",
                        "cmd": "^FO",
                        "msg": f"{etype.capitalize()} taşıyor: alt kenar ({y + h}) > etiket yüksekliği ({label_h}) — konum ({x},{y})"
                    })

        for elem in model.elements:
            x, y = elem.x, elem.y
            props = elem.properties
            etype = elem.element_type

            if etype == "box":
                w = props.get("width", 0)
                h = props.get("height", 0)
                t = props.get("thickness", 1)
                if w == 0 and h == 0:
                    warnings.append({
                        "level": "warning",
                        "cmd": "^GB",
                        "msg": f"Width and height are both 0 at ({x},{y}); element will not render"
                    })
                if h == 0 and t < 1:
                    warnings.append({
                        "level": "warning",
                        "cmd": "^GB",
                        "msg": f"Value 0 is less than minimum value 1; used 1 instead"
                    })
                if h == 0:
                    warnings.append({
                        "level": "info",
                        "cmd": "^GB",
                        "msg": f"Value 0 is less than minimum value 2; used 2 instead (line at y={y})"
                    })
                if w == 0:
                    warnings.append({
                        "level": "info",
                        "cmd": "^GB",
                        "msg": f"Value 0 is less than minimum value 2; used 2 instead (line at x={x})"
                    })

            elif etype == "circle":
                d = props.get("diameter", 0)
                if d == 0:
                    warnings.append({
                        "level": "warning",
                        "cmd": "^GC",
                        "msg": f"Circle diameter is 0 at ({x},{y})"
                    })

            elif etype == "text":
                data = props.get("data", "")
                if not data:
                    warnings.append({
                        "level": "info",
                        "cmd": "^FD",
                        "msg": f"Empty text field at ({x},{y})"
                    })

            elif etype == "barcode":
                data = props.get("data", "")
                if not data:
                    warnings.append({
                        "level": "error",
                        "cmd": "^FD",
                        "msg": f"Barcode has no data at ({x},{y})"
                    })
                mw = props.get("module_width", 2)
                if mw < 1 or mw > 10:
                    warnings.append({
                        "level": "warning",
                        "cmd": "^BY",
                        "msg": f"Module width {mw} is out of range 1-10 at ({x},{y})"
                    })

            elif etype == "qrcode":
                data = props.get("data", "")
                if not data:
                    warnings.append({
                        "level": "error",
                        "cmd": "^FD",
                        "msg": f"QR code has no data at ({x},{y})"
                    })
                mag = props.get("magnification", 3)
                if mag < 1 or mag > 10:
                    warnings.append({
                        "level": "warning",
                        "cmd": "^BQ",
                        "msg": f"QR magnification {mag} is out of range 1-10 at ({x},{y})"
                    })

        return warnings

    def update_warnings(self, model: LabelModel, label_w: int = None, label_h: int = None, canvas_elements=None):
        self._list.clear()
        warnings = self.validate(model, label_w, label_h, canvas_elements)

        self._count_label.setText(f"({len(warnings)})")
        if len(warnings) > 0:
            self._title.setText(f"Linter Warnings ({len(warnings)}+)" if len(warnings) >= 20 else f"Linter Warnings")
        else:
            self._title.setText("Linter Warnings")

        level_icons = {
            "error": "\u274c",
            "warning": "\u26a0\ufe0f",
            "info": "\u2139\ufe0f",
        }
        level_colors = {
            "error": QColor(244, 71, 71),
            "warning": QColor(227, 179, 65),
            "info": QColor(100, 149, 237),
        }

        for w in warnings:
            level = w.get("level", "warning")
            cmd = w.get("cmd", "")
            msg = w.get("msg", "")

            icon_char = level_icons.get(level, "\u26a0\ufe0f")
            display = f"{icon_char}  {cmd}: {msg}"

            item = QListWidgetItem(display)
            item.setForeground(level_colors.get(level, QColor(227, 179, 65)))
            self._list.addItem(item)

    def clear_warnings(self):
        self._list.clear()
        self._count_label.setText("(0)")
        self._title.setText("Linter Warnings")
