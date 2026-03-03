from PyQt6.QtWidgets import QGraphicsScene
from PyQt6.QtCore import Qt, QRectF, pyqtSignal
from PyQt6.QtGui import QPainter, QPen, QColor, QBrush
from ..elements.base_element import BaseElement
from ..elements.text_element import TextElement
from ..elements.box_element import BoxElement
from ..elements.line_element import LineElement
from ..elements.circle_element import CircleElement
from ..elements.diagonal_line import DiagonalLineElement
from ..elements.barcode_element import BarcodeElement
from ..elements.qr_element import QRElement
from ..core.zpl_commands import ZPLElement
from ..core.label_model import LabelModel


class CanvasScene(QGraphicsScene):
    element_changed = pyqtSignal()
    selection_changed_signal = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._label_width = 812
        self._label_height = 1218
        self._grid_visible = True
        self._grid_size = 10
        self._snap_to_grid = False
        self._elements: list[BaseElement] = []
        self._syncing = False

        padding = 100
        self.setSceneRect(-padding, -padding,
                          self._label_width + padding * 2,
                          self._label_height + padding * 2)
        self.selectionChanged.connect(self._on_selection_changed)

    def set_label_size(self, width: int, height: int):
        self._label_width = width
        self._label_height = height
        padding = 100
        self.setSceneRect(-padding, -padding,
                          width + padding * 2,
                          height + padding * 2)
        self.update()

    def set_grid_visible(self, visible: bool):
        self._grid_visible = visible
        self.update()

    def set_snap_to_grid(self, enabled: bool):
        self._snap_to_grid = enabled
        for elem in self._elements:
            elem.set_snap_to_grid(enabled, self._grid_size)

    def set_grid_size(self, size: int):
        self._grid_size = size
        for elem in self._elements:
            elem.set_snap_to_grid(self._snap_to_grid, size)
        self.update()

    def get_elements(self) -> list:
        return list(self._elements)

    def clear_elements(self):
        for elem in self._elements:
            self.removeItem(elem)
        self._elements.clear()

    def load_from_model(self, model: LabelModel):
        self._syncing = True
        success_count = 0
        error_count = 0
        try:
            self.clear_elements()
            self.set_label_size(model.settings.width, model.settings.height)
            
            print(f"[CanvasScene] Loading {len(model.elements)} elements from model")

            for i, zpl_elem in enumerate(model.elements):
                try:
                    item = self._create_element_from_zpl(zpl_elem, model)
                    if item:
                        self._add_element(item)
                        success_count += 1
                    else:
                        print(f"[CanvasScene] Warning: _create_element_from_zpl returned None for {zpl_elem.element_type}")
                        error_count += 1
                except Exception as e:
                    error_count += 1
                    print(f"[CanvasScene] Error creating {zpl_elem.element_type} at ({zpl_elem.x},{zpl_elem.y}): {e}")
                    import traceback
                    traceback.print_exc()
            
            print(f"[CanvasScene] Loaded {success_count} elements, {error_count} errors")
        finally:
            self._syncing = False

    def _create_element_from_zpl(self, zpl_elem: ZPLElement, model: LabelModel) -> BaseElement:
        t = zpl_elem.element_type
        props = zpl_elem.properties
        x, y = zpl_elem.x, zpl_elem.y

        if t == "text":
            font = props.get("font", model.settings.default_font)
            fh = props.get("font_height", model.settings.default_font_height)
            fw = props.get("font_width", model.settings.default_font_width)
            orientation = props.get("orientation", "N")
            data = props.get("data", "")
            # ^FT uses baseline (bottom-left) as Y origin, adjust to top-left
            if zpl_elem.use_ft:
                y = max(0, y - fh)
            elem = TextElement(x, y, data, font, fh, fw, orientation)
            elem._properties = dict(props)
            return elem

        elif t == "box":
            w = props.get("width", 100)
            h = props.get("height", 100)
            thickness = props.get("thickness", 1)
            color = props.get("color", "B")
            rounding = props.get("rounding", 0)
            return BoxElement(x, y, w, h, thickness, color, rounding)

        elif t == "circle":
            d = props.get("diameter", 100)
            thickness = props.get("thickness", 1)
            color = props.get("color", "B")
            return CircleElement(x, y, d, thickness, color)

        elif t == "diagonal":
            w = props.get("width", 100)
            h = props.get("height", 100)
            thickness = props.get("thickness", 1)
            color = props.get("color", "B")
            orientation = props.get("orientation", "R")
            return DiagonalLineElement(x, y, w, h, thickness, color, orientation)

        elif t == "barcode":
            bc_type = props.get("barcode_type", "code128")
            data = props.get("data", "")
            mw = props.get("module_width", 2)
            bh = props.get("bar_height", 100)
            orientation = props.get("orientation", "N")
            interp = props.get("interpretation", "Y")
            elem = BarcodeElement(x, y, bc_type, data, mw, bh, orientation, interp)
            elem._properties = dict(props)
            return elem

        elif t == "qrcode":
            data = props.get("data", "")
            mag = props.get("magnification", 3)
            qr_model = props.get("qr_model", 2)
            orientation = props.get("orientation", "N")
            elem = QRElement(x, y, data, mag, qr_model, orientation)
            elem._properties = dict(props)
            return elem

        return None

    def _add_element(self, elem: BaseElement):
        elem.set_snap_to_grid(self._snap_to_grid, self._grid_size)
        elem.signals.position_changed.connect(self._on_element_changed)
        elem.signals.size_changed.connect(self._on_element_changed)
        elem.signals.property_changed.connect(self._on_element_property_changed)
        self._elements.append(elem)
        self.addItem(elem)

    def add_new_element(self, elem: BaseElement):
        self._add_element(elem)
        self.element_changed.emit()

    def remove_element(self, elem: BaseElement):
        if elem in self._elements:
            self._elements.remove(elem)
            self.removeItem(elem)
            self.element_changed.emit()

    def _on_element_changed(self, elem):
        if not self._syncing:
            self.element_changed.emit()

    def _on_element_property_changed(self, elem, prop_name, value):
        if not self._syncing:
            self.element_changed.emit()

    def _on_selection_changed(self):
        self.selection_changed_signal.emit()

    def get_model(self) -> LabelModel:
        model = LabelModel()
        model.settings.width = self._label_width
        model.settings.height = self._label_height
        for elem in self._elements:
            zpl_elem = elem.get_zpl_element()
            model.add_element(zpl_elem)
        return model

    def handle_context_action(self, action_text: str, element: BaseElement):
        if action_text == "Delete":
            self.remove_element(element)
        elif action_text == "Clone":
            zpl_elem = element.get_zpl_element()
            zpl_elem.x += 20
            zpl_elem.y += 20
            model = self.get_model()
            new_item = self._create_element_from_zpl(zpl_elem, model)
            if new_item:
                self.add_new_element(new_item)
        elif action_text == "Bring to Front":
            max_z = max((e.zValue() for e in self._elements), default=0)
            element.setZValue(max_z + 1)
        elif action_text == "Send to Back":
            min_z = min((e.zValue() for e in self._elements), default=0)
            element.setZValue(min_z - 1)

    def drawBackground(self, painter: QPainter, rect: QRectF):
        super().drawBackground(painter, rect)

        # Light work area background (like Labelary)
        painter.setBrush(QBrush(QColor(240, 240, 240)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(rect)

        # Drop shadow for the label
        shadow_offset = 4
        shadow_rect = QRectF(shadow_offset, shadow_offset,
                             self._label_width, self._label_height)
        painter.setBrush(QBrush(QColor(180, 180, 180)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(shadow_rect)

        # White label area
        label_rect = QRectF(0, 0, self._label_width, self._label_height)
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        painter.setPen(QPen(QColor(160, 160, 160), 1, Qt.PenStyle.SolidLine))
        painter.drawRect(label_rect)

        if self._grid_visible:
            self._draw_grid(painter, label_rect)

    def _draw_grid(self, painter: QPainter, label_rect: QRectF):
        minor_pen = QPen(QColor(230, 230, 230), 0.5)
        major_pen = QPen(QColor(200, 200, 200), 1.0)

        x = 0
        while x <= self._label_width:
            is_major = (x % (self._grid_size * 10) == 0)
            painter.setPen(major_pen if is_major else minor_pen)
            painter.drawLine(int(x), 0, int(x), self._label_height)
            x += self._grid_size

        y = 0
        while y <= self._label_height:
            is_major = (y % (self._grid_size * 10) == 0)
            painter.setPen(major_pen if is_major else minor_pen)
            painter.drawLine(0, int(y), self._label_width, int(y))
            y += self._grid_size

    def delete_selected(self):
        for item in self.selectedItems():
            if isinstance(item, BaseElement) and item in self._elements:
                self._elements.remove(item)
                self.removeItem(item)
        self.element_changed.emit()

    def clone_selected(self):
        model = self.get_model()
        for item in self.selectedItems():
            if isinstance(item, BaseElement):
                zpl_elem = item.get_zpl_element()
                zpl_elem.x += 20
                zpl_elem.y += 20
                new_item = self._create_element_from_zpl(zpl_elem, model)
                if new_item:
                    self.add_new_element(new_item)

    def select_all(self):
        for elem in self._elements:
            elem.setSelected(True)
