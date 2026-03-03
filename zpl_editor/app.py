import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from .ui.main_window import MainWindow


def run():
    app = QApplication(sys.argv)
    app.setApplicationName("ZPL Visual Editor")
    app.setOrganizationName("ZPLEditor")
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())
