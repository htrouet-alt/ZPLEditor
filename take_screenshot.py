"""Take a screenshot of the ZPL Visual Editor for README documentation."""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QScreen
from zpl_editor.ui.main_window import MainWindow

SAMPLE_ZPL = r"""^XA
^PW812
^LL1218
^FX -- Header --
^FO50,40^A0N,44,44^FDYurtici Kargo^FS
^FO50,92^GB712,0,3^FS
^FX -- Receiver --
^FO50,110^A0N,30,30^FDAhmet Yilmaz^FS
^FO50,148^A0N,24,24^FDAtaturk Cad. No:45^FS
^FO50,178^A0N,24,24^FDKadikoy / Istanbul^FS
^FO50,208^A0N,24,24^FDTel: 0532 123 4567^FS
^FX -- Separator --
^FO50,245^GB712,0,2^FS
^FX -- Order Info --
^FO50,265^A0N,36,36^FDTrendyol^FS
^FO50,310^A0N,22,22^FDSiparis: TRN-2024-987654^FS
^FO50,338^A0N,22,22^FDGonderi: 7290012345678^FS
^FX -- Barcode --
^FO100,390^BY3
^BCN,120,Y,N,N
^FD7290012345678^FS
^FX -- Bottom Info --
^FO50,560^A0N,20,20^FDTarih: 05.03.2026^FS
^FO50,586^A0N,20,20^FDAgirlik: 1.2 kg^FS
^FX -- QR Code --
^FO600,540^BQN,2,5^FDQA,https://tracking.yurtici.com.tr/7290012345678^FS
^XZ"""


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("ZPL Visual Editor")
    app.setOrganizationName("ZPLEditor")
    app.setStyle("Fusion")

    window = MainWindow()
    window.resize(1280, 800)
    window.show()

    def setup_and_capture():
        # Set ZPL code in editor
        editor = window._code_editor
        editor.setPlainText(SAMPLE_ZPL)

        # Wait for canvas to render, then capture
        QTimer.singleShot(1500, capture)

    def capture():
        # Grab the window
        screen = window.grab()
        out_path = os.path.join(os.path.dirname(__file__), "docs", "screenshot_main.png")
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        screen.save(out_path)
        print(f"Screenshot saved: {out_path}")
        app.quit()

    QTimer.singleShot(1000, setup_and_capture)
    app.exec()


if __name__ == "__main__":
    main()
