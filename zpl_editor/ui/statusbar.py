from PyQt6.QtWidgets import QStatusBar, QLabel


class EditorStatusBar(QStatusBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._pos_label = QLabel("X: 0  Y: 0")
        self._zoom_label = QLabel("Zoom: 100%")
        self._info_label = QLabel("Ready")
        self._dpi_label = QLabel("DPI: 203")

        self.addWidget(self._pos_label)
        self.addWidget(self._zoom_label)
        self.addWidget(self._dpi_label)
        self.addPermanentWidget(self._info_label)

    def update_position(self, x: float, y: float):
        self._pos_label.setText(f"X: {int(x)}  Y: {int(y)}")

    def update_zoom(self, factor: float):
        self._zoom_label.setText(f"Zoom: {int(factor * 100)}%")

    def update_info(self, text: str):
        self._info_label.setText(text)

    def update_dpi(self, dpi: int):
        self._dpi_label.setText(f"DPI: {dpi}")
