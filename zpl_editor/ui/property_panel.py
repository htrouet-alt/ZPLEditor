from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QSpinBox, QComboBox, QLineEdit, QGroupBox,
                              QFormLayout, QScrollArea, QFrame, QCheckBox)
from PyQt6.QtCore import Qt, pyqtSignal
from ..elements.base_element import BaseElement
from ..elements.text_element import TextElement
from ..elements.box_element import BoxElement
from ..elements.circle_element import CircleElement
from ..elements.diagonal_line import DiagonalLineElement
from ..elements.barcode_element import BarcodeElement, BARCODE_TYPES
from ..elements.qr_element import QRElement
from ..fonts.zebra_fonts import ZEBRA_FONT_MAP, get_system_fonts


class PropertyPanel(QWidget):
    property_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_element: BaseElement = None
        self._syncing = False
        self._init_ui()
        self.setMinimumWidth(250)
        self.setMaximumWidth(350)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        self._title = QLabel("Properties")
        self._title.setStyleSheet("font-weight: bold; font-size: 13px; color: #D4D4D4; padding: 5px;")
        layout.addWidget(self._title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(5)

        self._create_position_group()
        self._create_text_group()
        self._create_box_group()
        self._create_circle_group()
        self._create_barcode_group()
        self._create_qr_group()

        self._content_layout.addStretch()
        scroll.setWidget(self._content)
        layout.addWidget(scroll)

        self._no_selection_label = QLabel("No element selected")
        self._no_selection_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._no_selection_label.setStyleSheet("color: #808080; padding: 20px;")
        layout.addWidget(self._no_selection_label)

        self._hide_all_groups()
        self._no_selection_label.show()

    def _create_position_group(self):
        self._pos_group = QGroupBox("Position && Size")
        form = QFormLayout()
        form.setSpacing(4)

        self._spin_x = QSpinBox()
        self._spin_x.setRange(0, 10000)
        self._spin_x.valueChanged.connect(self._on_position_changed)
        form.addRow("X:", self._spin_x)

        self._spin_y = QSpinBox()
        self._spin_y.setRange(0, 10000)
        self._spin_y.valueChanged.connect(self._on_position_changed)
        form.addRow("Y:", self._spin_y)

        self._spin_w = QSpinBox()
        self._spin_w.setRange(5, 10000)
        self._spin_w.valueChanged.connect(self._on_size_changed)
        form.addRow("Width:", self._spin_w)

        self._spin_h = QSpinBox()
        self._spin_h.setRange(5, 10000)
        self._spin_h.valueChanged.connect(self._on_size_changed)
        form.addRow("Height:", self._spin_h)

        self._combo_rotation = QComboBox()
        self._combo_rotation.addItems(["0° (N)", "90° (R)", "180° (I)", "270° (B)"])
        self._combo_rotation.currentIndexChanged.connect(self._on_rotation_changed)
        form.addRow("Rotation:", self._combo_rotation)

        self._pos_group.setLayout(form)
        self._content_layout.addWidget(self._pos_group)

    def _create_text_group(self):
        self._text_group = QGroupBox("Text Properties")
        form = QFormLayout()
        form.setSpacing(4)

        self._text_content = QLineEdit()
        self._text_content.textChanged.connect(self._on_text_content_changed)
        form.addRow("Text:", self._text_content)

        # Font type selector (Built-in vs TrueType)
        self._font_type_combo = QComboBox()
        self._font_type_combo.addItems(["Zebra Built-in", "TrueType (^A@)"])
        self._font_type_combo.currentIndexChanged.connect(self._on_font_type_changed)
        form.addRow("Font Type:", self._font_type_combo)

        # Built-in font combo
        self._font_combo = QComboBox()
        for fid, info in ZEBRA_FONT_MAP.items():
            self._font_combo.addItem(f"{fid} - {info['name']}", fid)
        self._font_combo.currentIndexChanged.connect(self._on_font_changed)
        form.addRow("Font:", self._font_combo)

        # TrueType font combo (system fonts)
        self._tt_font_combo = QComboBox()
        self._tt_font_combo.setEditable(True)
        self._tt_font_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._tt_font_combo.currentTextChanged.connect(self._on_truetype_font_changed)
        self._tt_font_label = QLabel("TrueType:")
        form.addRow(self._tt_font_label, self._tt_font_combo)

        self._font_height = QSpinBox()
        self._font_height.setRange(8, 500)
        self._font_height.valueChanged.connect(self._on_font_size_changed)
        form.addRow("Font H:", self._font_height)

        self._font_width = QSpinBox()
        self._font_width.setRange(0, 500)
        self._font_width.valueChanged.connect(self._on_font_size_changed)
        form.addRow("Font W:", self._font_width)

        self._text_group.setLayout(form)
        self._content_layout.addWidget(self._text_group)

        # Initially hide TrueType combo
        self._tt_font_combo.hide()
        self._tt_font_label.hide()

    def _populate_system_fonts(self):
        if self._tt_font_combo.count() > 0:
            return
        fonts = get_system_fonts()
        self._tt_font_combo.addItems(fonts)

    def _create_box_group(self):
        self._box_group = QGroupBox("Box / Line Properties")
        form = QFormLayout()
        form.setSpacing(4)

        self._box_thickness = QSpinBox()
        self._box_thickness.setRange(1, 500)
        self._box_thickness.valueChanged.connect(self._on_box_changed)
        form.addRow("Thickness:", self._box_thickness)

        self._box_color = QComboBox()
        self._box_color.addItems(["Black (B)", "White (W)"])
        self._box_color.currentIndexChanged.connect(self._on_box_changed)
        form.addRow("Color:", self._box_color)

        self._box_rounding = QSpinBox()
        self._box_rounding.setRange(0, 8)
        self._box_rounding.valueChanged.connect(self._on_box_changed)
        form.addRow("Rounding:", self._box_rounding)

        self._box_group.setLayout(form)
        self._content_layout.addWidget(self._box_group)

    def _create_circle_group(self):
        self._circle_group = QGroupBox("Circle Properties")
        form = QFormLayout()
        form.setSpacing(4)

        self._circle_diameter = QSpinBox()
        self._circle_diameter.setRange(5, 5000)
        self._circle_diameter.valueChanged.connect(self._on_circle_changed)
        form.addRow("Diameter:", self._circle_diameter)

        self._circle_thickness = QSpinBox()
        self._circle_thickness.setRange(1, 500)
        self._circle_thickness.valueChanged.connect(self._on_circle_changed)
        form.addRow("Thickness:", self._circle_thickness)

        self._circle_color = QComboBox()
        self._circle_color.addItems(["Black (B)", "White (W)"])
        self._circle_color.currentIndexChanged.connect(self._on_circle_changed)
        form.addRow("Color:", self._circle_color)

        self._circle_group.setLayout(form)
        self._content_layout.addWidget(self._circle_group)

    def _create_barcode_group(self):
        self._barcode_group = QGroupBox("Barcode Properties")
        form = QFormLayout()
        form.setSpacing(4)

        self._bc_type = QComboBox()
        # Add 1D barcodes
        self._bc_type.addItem("--- 1D Barcodes ---", "")
        for bc_id, info in BARCODE_TYPES.items():
            if info["category"] == "1D":
                self._bc_type.addItem(f"  {info['name']} (^{info['zpl_cmd']})", bc_id)
        # Add 2D barcodes
        self._bc_type.addItem("--- 2D Barcodes ---", "")
        for bc_id, info in BARCODE_TYPES.items():
            if info["category"] == "2D":
                self._bc_type.addItem(f"  {info['name']} (^{info['zpl_cmd']})", bc_id)
        self._bc_type.currentIndexChanged.connect(self._on_barcode_changed)
        form.addRow("Type:", self._bc_type)

        self._bc_data = QLineEdit()
        self._bc_data.textChanged.connect(self._on_barcode_changed)
        form.addRow("Data:", self._bc_data)

        self._bc_module_width = QSpinBox()
        self._bc_module_width.setRange(1, 10)
        self._bc_module_width.valueChanged.connect(self._on_barcode_changed)
        form.addRow("Module W:", self._bc_module_width)

        self._bc_height = QSpinBox()
        self._bc_height.setRange(10, 500)
        self._bc_height.valueChanged.connect(self._on_barcode_changed)
        form.addRow("Height:", self._bc_height)

        self._bc_interpretation = QCheckBox("Show text")
        self._bc_interpretation.stateChanged.connect(self._on_barcode_changed)
        form.addRow("", self._bc_interpretation)

        self._barcode_group.setLayout(form)
        self._content_layout.addWidget(self._barcode_group)

    def _create_qr_group(self):
        self._qr_group = QGroupBox("QR Code Properties")
        form = QFormLayout()
        form.setSpacing(4)

        self._qr_model = QComboBox()
        self._qr_model.addItem("Model 1", 1)
        self._qr_model.addItem("Model 2 (Default)", 2)
        self._qr_model.setCurrentIndex(1)
        self._qr_model.currentIndexChanged.connect(self._on_qr_changed)
        form.addRow("QR Model:", self._qr_model)

        self._qr_data = QLineEdit()
        self._qr_data.textChanged.connect(self._on_qr_changed)
        form.addRow("Data:", self._qr_data)

        self._qr_magnification = QSpinBox()
        self._qr_magnification.setRange(1, 10)
        self._qr_magnification.valueChanged.connect(self._on_qr_changed)
        form.addRow("Size:", self._qr_magnification)

        self._qr_error = QComboBox()
        self._qr_error.addItem("H - High Recovery (~30%)", "H")
        self._qr_error.addItem("Q - Quartile (~25%)", "Q")
        self._qr_error.addItem("M - Medium (~15%)", "M")
        self._qr_error.addItem("L - Low (~7%)", "L")
        self._qr_error.currentIndexChanged.connect(self._on_qr_changed)
        form.addRow("Error Corr:", self._qr_error)

        self._qr_group.setLayout(form)
        self._content_layout.addWidget(self._qr_group)

    def _hide_all_groups(self):
        self._pos_group.hide()
        self._text_group.hide()
        self._box_group.hide()
        self._circle_group.hide()
        self._barcode_group.hide()
        self._qr_group.hide()
        self._content.hide()

    def set_element(self, element: BaseElement):
        self._syncing = True
        self._current_element = element
        self._hide_all_groups()

        if element is None:
            self._no_selection_label.show()
            self._syncing = False
            return

        self._no_selection_label.hide()
        self._content.show()
        self._pos_group.show()

        self._spin_x.setValue(element.dot_x)
        self._spin_y.setValue(element.dot_y)
        self._spin_w.setValue(element.dot_width)
        self._spin_h.setValue(element.dot_height)

        orientation = element._properties.get("orientation", "N")
        rot_map = {"N": 0, "R": 1, "I": 2, "B": 3}
        self._combo_rotation.setCurrentIndex(rot_map.get(orientation, 0))

        if isinstance(element, TextElement):
            self._text_group.show()
            self._text_content.setText(element._properties.get("data", ""))

            font_id = element._properties.get("font", "0")
            if font_id == "@":
                self._font_type_combo.setCurrentIndex(1)
                self._font_combo.hide()
                self._tt_font_combo.show()
                self._tt_font_label.show()
                self._populate_system_fonts()
                font_name = element._properties.get("font_name", "Arial")
                idx = self._tt_font_combo.findText(font_name)
                if idx >= 0:
                    self._tt_font_combo.setCurrentIndex(idx)
                else:
                    self._tt_font_combo.setCurrentText(font_name)
            else:
                self._font_type_combo.setCurrentIndex(0)
                self._font_combo.show()
                self._tt_font_combo.hide()
                self._tt_font_label.hide()
                idx = self._font_combo.findData(font_id)
                if idx >= 0:
                    self._font_combo.setCurrentIndex(idx)

            self._font_height.setValue(element._properties.get("font_height", 30))
            self._font_width.setValue(element._properties.get("font_width", 0))

        elif isinstance(element, BoxElement):
            self._box_group.show()
            self._box_thickness.setValue(element._properties.get("thickness", 1))
            color = element._properties.get("color", "B")
            self._box_color.setCurrentIndex(0 if color == "B" else 1)
            self._box_rounding.setValue(element._properties.get("rounding", 0))

        elif isinstance(element, CircleElement):
            self._circle_group.show()
            self._circle_diameter.setValue(element._properties.get("diameter", 100))
            self._circle_thickness.setValue(element._properties.get("thickness", 1))
            color = element._properties.get("color", "B")
            self._circle_color.setCurrentIndex(0 if color == "B" else 1)

        elif isinstance(element, BarcodeElement):
            self._barcode_group.show()
            bc_type = element._properties.get("barcode_type", "code128")
            idx = self._bc_type.findData(bc_type)
            if idx >= 0:
                self._bc_type.setCurrentIndex(idx)
            self._bc_data.setText(element._properties.get("data", ""))
            self._bc_module_width.setValue(element._properties.get("module_width", 2))
            self._bc_height.setValue(element._properties.get("bar_height", 100))
            self._bc_interpretation.setChecked(
                element._properties.get("interpretation", "Y") == "Y")

        elif isinstance(element, QRElement):
            self._qr_group.show()
            qr_model = element._properties.get("qr_model", 2)
            self._qr_model.setCurrentIndex(0 if qr_model == 1 else 1)
            self._qr_data.setText(element._properties.get("data", ""))
            self._qr_magnification.setValue(element._properties.get("magnification", 3))
            error_corr = element._properties.get("error_correction", "M")
            ec_map = {"H": 0, "Q": 1, "M": 2, "L": 3}
            self._qr_error.setCurrentIndex(ec_map.get(error_corr, 2))

        self._syncing = False

    def _on_position_changed(self):
        if self._syncing or not self._current_element:
            return
        self._current_element.dot_x = self._spin_x.value()
        self._current_element.dot_y = self._spin_y.value()
        self.property_changed.emit()

    def _on_size_changed(self):
        if self._syncing or not self._current_element:
            return
        self._current_element.dot_width = self._spin_w.value()
        self._current_element.dot_height = self._spin_h.value()
        self._current_element._sync_properties_from_size()
        self._current_element.update()
        self.property_changed.emit()

    def _on_rotation_changed(self):
        if self._syncing or not self._current_element:
            return
        rot_map = {0: "N", 1: "R", 2: "I", 3: "B"}
        self._current_element._properties["orientation"] = rot_map.get(
            self._combo_rotation.currentIndex(), "N")
        self._current_element.update()
        self.property_changed.emit()

    def _on_text_content_changed(self):
        if self._syncing or not self._current_element:
            return
        if isinstance(self._current_element, TextElement):
            self._current_element._properties["data"] = self._text_content.text()
            self._current_element._update_size_from_properties()
            self._current_element.update()
            self.property_changed.emit()

    def _on_font_type_changed(self):
        if self._syncing:
            return
        is_truetype = self._font_type_combo.currentIndex() == 1
        self._font_combo.setVisible(not is_truetype)
        self._tt_font_combo.setVisible(is_truetype)
        self._tt_font_label.setVisible(is_truetype)
        if is_truetype:
            self._populate_system_fonts()
            if self._current_element and isinstance(self._current_element, TextElement):
                font_name = self._tt_font_combo.currentText() or "Arial"
                self._current_element._properties["font"] = "@"
                self._current_element._properties["font_name"] = font_name
                self._current_element._update_size_from_properties()
                self._current_element.update()
                self.property_changed.emit()
        else:
            if self._current_element and isinstance(self._current_element, TextElement):
                font_id = self._font_combo.currentData() or "0"
                self._current_element._properties["font"] = font_id
                self._current_element._properties.pop("font_name", None)
                self._current_element._update_size_from_properties()
                self._current_element.update()
                self.property_changed.emit()

    def _on_font_changed(self):
        if self._syncing or not self._current_element:
            return
        if isinstance(self._current_element, TextElement):
            font_id = self._font_combo.currentData()
            self._current_element._properties["font"] = font_id
            self._current_element._properties.pop("font_name", None)
            self._current_element._update_size_from_properties()
            self._current_element.update()
            self.property_changed.emit()

    def _on_truetype_font_changed(self):
        if self._syncing or not self._current_element:
            return
        if isinstance(self._current_element, TextElement):
            font_name = self._tt_font_combo.currentText()
            if font_name:
                self._current_element._properties["font"] = "@"
                self._current_element._properties["font_name"] = font_name
                self._current_element._update_size_from_properties()
                self._current_element.update()
                self.property_changed.emit()

    def _on_font_size_changed(self):
        if self._syncing or not self._current_element:
            return
        if isinstance(self._current_element, TextElement):
            self._current_element._properties["font_height"] = self._font_height.value()
            self._current_element._properties["font_width"] = self._font_width.value()
            self._current_element._update_size_from_properties()
            self._current_element.update()
            self.property_changed.emit()

    def _on_box_changed(self):
        if self._syncing or not self._current_element:
            return
        if isinstance(self._current_element, BoxElement):
            self._current_element._properties["thickness"] = self._box_thickness.value()
            self._current_element._properties["color"] = "B" if self._box_color.currentIndex() == 0 else "W"
            self._current_element._properties["rounding"] = self._box_rounding.value()
            self._current_element.update()
            self.property_changed.emit()

    def _on_circle_changed(self):
        if self._syncing or not self._current_element:
            return
        if isinstance(self._current_element, CircleElement):
            self._current_element._properties["diameter"] = self._circle_diameter.value()
            self._current_element._properties["thickness"] = self._circle_thickness.value()
            self._current_element._properties["color"] = "B" if self._circle_color.currentIndex() == 0 else "W"
            self._current_element._update_size_from_properties()
            self._current_element.update()
            self.property_changed.emit()

    def _on_barcode_changed(self):
        if self._syncing or not self._current_element:
            return
        if isinstance(self._current_element, BarcodeElement):
            bc_type = self._bc_type.currentData()
            if bc_type:  # Skip separator items
                self._current_element._properties["barcode_type"] = bc_type
            self._current_element._properties["data"] = self._bc_data.text()
            self._current_element._properties["module_width"] = self._bc_module_width.value()
            self._current_element._properties["bar_height"] = self._bc_height.value()
            self._current_element._properties["interpretation"] = "Y" if self._bc_interpretation.isChecked() else "N"
            self._current_element._update_size_from_properties()
            self._current_element.update()
            self.property_changed.emit()

    def _on_qr_changed(self):
        if self._syncing or not self._current_element:
            return
        if isinstance(self._current_element, QRElement):
            self._current_element._properties["qr_model"] = self._qr_model.currentData()
            self._current_element._properties["data"] = self._qr_data.text()
            self._current_element._properties["magnification"] = self._qr_magnification.value()
            self._current_element._properties["error_correction"] = self._qr_error.currentData()
            self._current_element._update_size_from_properties()
            self._current_element.update()
            self.property_changed.emit()
