"""Custom label size dialog with DPI, width, height inputs."""
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                              QComboBox, QDoubleSpinBox, QSpinBox, QLabel,
                              QDialogButtonBox, QGroupBox, QFrame)
from PyQt6.QtCore import Qt


# Presets: (display_name, width_cm, height_cm, dpi)
PRESETS = [
    ("4\" x 6\" (10.2 x 15.2 cm) @ 203 DPI", 10.16, 15.24, 203),
    ("4\" x 8\" (10.2 x 20.3 cm) @ 203 DPI", 10.16, 20.32, 203),
    ("4\" x 2\" (10.2 x 5.1 cm) @ 203 DPI", 10.16, 5.08, 203),
    ("2\" x 1\" (5.1 x 2.5 cm) @ 203 DPI", 5.08, 2.54, 203),
    ("4\" x 6\" (10.2 x 15.2 cm) @ 300 DPI", 10.16, 15.24, 300),
]


class LabelSizeDialog(QDialog):
    """Dialog to select or enter custom label size with DPI."""

    def __init__(self, parent=None, current_width=812, current_height=1218, current_dpi=203):
        super().__init__(parent)
        self.setWindowTitle("Label Size")
        self.setMinimumWidth(360)

        self._result_width = current_width
        self._result_height = current_height
        self._result_dpi = current_dpi
        self._updating = False

        layout = QVBoxLayout(self)

        # Preset combo
        preset_group = QGroupBox("Preset")
        preset_layout = QVBoxLayout(preset_group)
        self._preset_combo = QComboBox()
        for p in PRESETS:
            self._preset_combo.addItem(p[0])
        self._preset_combo.addItem("Custom")
        self._preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        preset_layout.addWidget(self._preset_combo)
        layout.addWidget(preset_group)

        # Custom inputs
        self._custom_group = QGroupBox("Custom Size")
        form = QFormLayout(self._custom_group)

        # DPI
        self._dpi_combo = QComboBox()
        self._dpi_combo.addItems(["203", "300", "600"])
        self._dpi_combo.setCurrentText(str(current_dpi))
        self._dpi_combo.currentTextChanged.connect(self._on_value_changed)
        form.addRow("DPI:", self._dpi_combo)

        # Unit selector
        self._unit_combo = QComboBox()
        self._unit_combo.addItems(["cm", "inch", "mm", "dots"])
        self._unit_combo.currentTextChanged.connect(self._on_unit_changed)
        form.addRow("Unit:", self._unit_combo)

        # Width
        self._width_spin = QDoubleSpinBox()
        self._width_spin.setRange(0.5, 300.0)
        self._width_spin.setDecimals(2)
        self._width_spin.setSingleStep(0.1)
        self._width_spin.valueChanged.connect(self._on_value_changed)
        form.addRow("Width:", self._width_spin)

        # Height
        self._height_spin = QDoubleSpinBox()
        self._height_spin.setRange(0.5, 300.0)
        self._height_spin.setDecimals(2)
        self._height_spin.setSingleStep(0.1)
        self._height_spin.valueChanged.connect(self._on_value_changed)
        form.addRow("Height:", self._height_spin)

        layout.addWidget(self._custom_group)

        # Calculated result display
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        self._result_label = QLabel()
        self._result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._result_label.setStyleSheet("font-weight: bold; padding: 8px;")
        layout.addWidget(self._result_label)

        # OK / Cancel
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Initialize from current values
        self._init_from_current(current_width, current_height, current_dpi)

    def _init_from_current(self, width_dots, height_dots, dpi):
        """Set initial values from current label dimensions."""
        self._updating = True

        # Check if it matches a preset
        matched = False
        for i, (name, w_cm, h_cm, p_dpi) in enumerate(PRESETS):
            pw = round(w_cm * p_dpi / 2.54)
            ph = round(h_cm * p_dpi / 2.54)
            if abs(pw - width_dots) <= 2 and abs(ph - height_dots) <= 2 and p_dpi == dpi:
                self._preset_combo.setCurrentIndex(i)
                matched = True
                break

        if not matched:
            self._preset_combo.setCurrentIndex(len(PRESETS))  # "Custom"

        # Set DPI
        dpi_text = str(dpi)
        if self._dpi_combo.findText(dpi_text) >= 0:
            self._dpi_combo.setCurrentText(dpi_text)

        # Set width/height in cm
        w_cm = width_dots * 2.54 / dpi
        h_cm = height_dots * 2.54 / dpi
        self._width_spin.setValue(w_cm)
        self._height_spin.setValue(h_cm)

        self._updating = False
        self._update_result()

    def _on_preset_changed(self, index):
        if self._updating:
            return

        if index < len(PRESETS):
            name, w_cm, h_cm, dpi = PRESETS[index]
            self._updating = True
            self._dpi_combo.setCurrentText(str(dpi))
            unit = self._unit_combo.currentText()
            self._width_spin.setValue(self._cm_to_unit(w_cm, unit))
            self._height_spin.setValue(self._cm_to_unit(h_cm, unit))
            self._custom_group.setEnabled(False)
            self._updating = False
            self._update_result()
        else:
            # Custom
            self._custom_group.setEnabled(True)
            self._update_result()

    def _on_unit_changed(self, unit):
        if self._updating:
            return

        self._updating = True

        # Convert current dot values back to new unit
        dpi = int(self._dpi_combo.currentText())

        if unit == "dots":
            self._width_spin.setDecimals(0)
            self._height_spin.setDecimals(0)
            self._width_spin.setRange(50, 10000)
            self._height_spin.setRange(50, 10000)
            self._width_spin.setSingleStep(1)
            self._height_spin.setSingleStep(1)
            self._width_spin.setValue(self._result_width)
            self._height_spin.setValue(self._result_height)
        elif unit == "mm":
            self._width_spin.setDecimals(1)
            self._height_spin.setDecimals(1)
            self._width_spin.setRange(5, 3000)
            self._height_spin.setRange(5, 3000)
            self._width_spin.setSingleStep(1.0)
            self._height_spin.setSingleStep(1.0)
            self._width_spin.setValue(self._result_width * 25.4 / dpi)
            self._height_spin.setValue(self._result_height * 25.4 / dpi)
        elif unit == "inch":
            self._width_spin.setDecimals(2)
            self._height_spin.setDecimals(2)
            self._width_spin.setRange(0.2, 120.0)
            self._height_spin.setRange(0.2, 120.0)
            self._width_spin.setSingleStep(0.1)
            self._height_spin.setSingleStep(0.1)
            self._width_spin.setValue(self._result_width / dpi)
            self._height_spin.setValue(self._result_height / dpi)
        else:  # cm
            self._width_spin.setDecimals(2)
            self._height_spin.setDecimals(2)
            self._width_spin.setRange(0.5, 300.0)
            self._height_spin.setRange(0.5, 300.0)
            self._width_spin.setSingleStep(0.1)
            self._height_spin.setSingleStep(0.1)
            self._width_spin.setValue(self._result_width * 2.54 / dpi)
            self._height_spin.setValue(self._result_height * 2.54 / dpi)

        self._updating = False

    def _on_value_changed(self):
        if self._updating:
            return
        # Switch to Custom if user edits values
        if self._preset_combo.currentIndex() < len(PRESETS):
            self._updating = True
            self._preset_combo.setCurrentIndex(len(PRESETS))
            self._custom_group.setEnabled(True)
            self._updating = False
        self._update_result()

    def _update_result(self):
        """Calculate and display the resulting dot dimensions."""
        dpi = int(self._dpi_combo.currentText())
        unit = self._unit_combo.currentText()
        w_val = self._width_spin.value()
        h_val = self._height_spin.value()

        if self._preset_combo.currentIndex() < len(PRESETS):
            _, w_cm, h_cm, dpi = PRESETS[self._preset_combo.currentIndex()]
            self._result_width = round(w_cm * dpi / 2.54)
            self._result_height = round(h_cm * dpi / 2.54)
            self._result_dpi = dpi
        else:
            self._result_dpi = dpi
            if unit == "dots":
                self._result_width = int(w_val)
                self._result_height = int(h_val)
            elif unit == "mm":
                self._result_width = round(w_val * dpi / 25.4)
                self._result_height = round(h_val * dpi / 25.4)
            elif unit == "inch":
                self._result_width = round(w_val * dpi)
                self._result_height = round(h_val * dpi)
            else:  # cm
                self._result_width = round(w_val * dpi / 2.54)
                self._result_height = round(h_val * dpi / 2.54)

        w_inch = self._result_width / dpi
        h_inch = self._result_height / dpi
        self._result_label.setText(
            f"{self._result_width} x {self._result_height} dots  |  "
            f"{w_inch:.1f}\" x {h_inch:.1f}\"  |  {dpi} DPI"
        )

    @staticmethod
    def _cm_to_unit(cm_val, unit):
        if unit == "mm":
            return cm_val * 10
        elif unit == "inch":
            return cm_val / 2.54
        elif unit == "dots":
            return cm_val  # will be overridden
        return cm_val  # cm

    def get_result(self):
        """Return (width_dots, height_dots, dpi)."""
        return self._result_width, self._result_height, self._result_dpi
