from PyQt6.QtWidgets import QToolBar, QToolButton, QSlider, QLabel, QWidget, QHBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QAction


class EditorToolBar(QToolBar):
    tool_selected = pyqtSignal(str)
    zoom_value_changed = pyqtSignal(int)
    action_triggered = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__("Tools", parent)
        self.setMovable(False)
        self.setIconSize(self.iconSize())
        self._current_tool = "select"
        self._tool_buttons = {}

        self._create_tool_buttons()
        self.addSeparator()
        self._create_action_buttons()
        self.addSeparator()
        self._create_alignment_buttons()
        self.addSeparator()
        self._create_zoom_slider()

    def _create_tool_buttons(self):
        tools = [
            ("select", "Select (V)", "V"),
            ("text", "Text (T)", "T"),
            ("line", "Line (L)", "L"),
            ("rect", "Rectangle (R)", "R"),
            ("circle", "Circle (C)", "C"),
            ("barcode", "Barcode (B)", "B"),
            ("qrcode", "QR Code (Q)", "Q"),
        ]
        for tool_id, tooltip, shortcut in tools:
            btn = QToolButton()
            btn.setText(tooltip.split("(")[0].strip())
            btn.setToolTip(f"{tooltip}")
            btn.setCheckable(True)
            btn.setChecked(tool_id == "select")
            btn.clicked.connect(lambda checked, t=tool_id: self._on_tool_clicked(t))
            self.addWidget(btn)
            self._tool_buttons[tool_id] = btn

    def _create_action_buttons(self):
        actions = [
            ("undo", "Undo (Ctrl+Z)"),
            ("redo", "Redo (Ctrl+Y)"),
        ]
        for action_id, tooltip in actions:
            btn = QToolButton()
            btn.setText(action_id.capitalize())
            btn.setToolTip(tooltip)
            btn.clicked.connect(lambda checked, a=action_id: self.action_triggered.emit(a))
            self.addWidget(btn)

    def _create_alignment_buttons(self):
        alignments = [
            ("align_left", "Align Left"),
            ("align_center_h", "Align Center H"),
            ("align_right", "Align Right"),
            ("align_top", "Align Top"),
            ("align_center_v", "Align Center V"),
            ("align_bottom", "Align Bottom"),
        ]
        for align_id, tooltip in alignments:
            btn = QToolButton()
            short_name = tooltip.replace("Align ", "")
            btn.setText(short_name)
            btn.setToolTip(tooltip)
            btn.clicked.connect(lambda checked, a=align_id: self.action_triggered.emit(a))
            self.addWidget(btn)

    def _create_zoom_slider(self):
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(5, 0, 5, 0)

        self._zoom_label = QLabel("100%")
        self._zoom_label.setMinimumWidth(45)
        self._zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self._zoom_slider.setRange(10, 3000)
        self._zoom_slider.setValue(100)
        self._zoom_slider.setFixedWidth(120)
        self._zoom_slider.valueChanged.connect(self._on_zoom_slider_changed)

        layout.addWidget(QLabel("Zoom:"))
        layout.addWidget(self._zoom_slider)
        layout.addWidget(self._zoom_label)
        self.addWidget(container)

    def _on_tool_clicked(self, tool_id: str):
        for tid, btn in self._tool_buttons.items():
            btn.setChecked(tid == tool_id)
        self._current_tool = tool_id
        self.tool_selected.emit(tool_id)

    def _on_zoom_slider_changed(self, value: int):
        self._zoom_label.setText(f"{value}%")
        self.zoom_value_changed.emit(value)

    def set_zoom_display(self, factor: float):
        pct = int(factor * 100)
        self._zoom_slider.blockSignals(True)
        self._zoom_slider.setValue(pct)
        self._zoom_slider.blockSignals(False)
        self._zoom_label.setText(f"{pct}%")

    @property
    def current_tool(self) -> str:
        return self._current_tool
