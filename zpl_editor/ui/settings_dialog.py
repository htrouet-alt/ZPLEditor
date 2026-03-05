"""Settings dialog for application configuration."""
import os
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                              QLineEdit, QPushButton, QFileDialog, QGroupBox,
                              QDialogButtonBox)
from PyQt6.QtCore import Qt
from ..utils.settings import AppSettings


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(500)
        self._settings = AppSettings()
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Tesseract group
        tess_group = QGroupBox("Tesseract OCR")
        tess_layout = QVBoxLayout(tess_group)

        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("tesseract.exe:"))
        self._tess_path = QLineEdit(self._settings.tesseract_path)
        self._tess_path.setMinimumWidth(300)
        path_layout.addWidget(self._tess_path)
        btn_browse = QPushButton("...")
        btn_browse.setFixedWidth(30)
        btn_browse.clicked.connect(self._browse_tesseract)
        path_layout.addWidget(btn_browse)
        tess_layout.addLayout(path_layout)

        layout.addWidget(tess_group)
        layout.addStretch()

        # OK / Cancel
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._save_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse_tesseract(self):
        current = self._tess_path.text()
        start_dir = os.path.dirname(current) if current else ""
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Tesseract Executable", start_dir,
            "Executable (tesseract.exe);;All Files (*.*)")
        if path:
            self._tess_path.setText(path)

    def _save_and_accept(self):
        path = self._tess_path.text().strip()
        if path:
            self._settings.tesseract_path = path
        self.accept()
