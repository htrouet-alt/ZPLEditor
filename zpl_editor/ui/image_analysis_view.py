"""
Image analysis view showing the imported label image with colored overlays
for detected regions: Red=images, Yellow=text, Blue=QR, Green=barcodes.
"""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                              QLabel, QScrollArea, QListWidget, QListWidgetItem,
                              QSplitter, QProgressBar, QComboBox, QLineEdit,
                              QFileDialog)
from PyQt6.QtCore import Qt, pyqtSignal, QRectF
from PyQt6.QtGui import QPainter, QPixmap, QImage, QColor, QPen, QFont, QBrush
import numpy as np
import cv2


# Colors for each detection type (RGBA: 10% opacity = alpha 25)
REGION_COLORS = {
    "barcode": QColor(0, 200, 0, 25),       # Green
    "qrcode":  QColor(0, 100, 255, 25),     # Blue
    "text":    QColor(255, 200, 0, 25),      # Yellow
    "image":   QColor(255, 50, 50, 25),      # Red
    "hline":   QColor(180, 0, 255, 25),      # Purple
    "vline":   QColor(180, 0, 255, 25),      # Purple
    "box":     QColor(0, 200, 200, 25),      # Cyan
}
REGION_BORDER_COLORS = {
    "barcode": QColor(0, 200, 0, 200),
    "qrcode":  QColor(0, 100, 255, 200),
    "text":    QColor(255, 200, 0, 200),
    "image":   QColor(255, 50, 50, 200),
    "hline":   QColor(180, 0, 255, 200),
    "vline":   QColor(180, 0, 255, 200),
    "box":     QColor(0, 200, 200, 200),
}
REGION_LABELS = {
    "barcode": "Barcode",
    "qrcode":  "QR Code",
    "text":    "Text",
    "image":   "Image",
    "hline":   "H-Line",
    "vline":   "V-Line",
    "box":     "Box",
}


class AnalysisImageWidget(QWidget):
    """Widget that displays the image with colored overlay rectangles."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap = None
        self._regions = []
        self._scale = 1.0
        self.setMinimumSize(200, 200)

    def set_image(self, pixmap: QPixmap):
        self._pixmap = pixmap
        self._update_scale()
        self.update()

    def set_regions(self, regions):
        self._regions = regions
        self.update()

    def clear(self):
        self._pixmap = None
        self._regions = []
        self.update()

    def _update_scale(self):
        if self._pixmap is None:
            return
        pw = self._pixmap.width()
        ph = self._pixmap.height()
        ww = self.width() - 20
        wh = self.height() - 20
        if pw > 0 and ph > 0:
            self._scale = min(ww / pw, wh / ph, 1.0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_scale()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background
        painter.fillRect(self.rect(), QColor(30, 30, 30))

        if self._pixmap is None:
            painter.setPen(QColor(128, 128, 128))
            painter.setFont(QFont("Arial", 12))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                             "No image loaded\n\nUse the label list to import images")
            painter.end()
            return

        # Draw scaled image centered
        sw = int(self._pixmap.width() * self._scale)
        sh = int(self._pixmap.height() * self._scale)
        ox = (self.width() - sw) // 2
        oy = (self.height() - sh) // 2

        scaled = self._pixmap.scaled(sw, sh,
                                     Qt.AspectRatioMode.KeepAspectRatio,
                                     Qt.TransformationMode.SmoothTransformation)
        painter.drawPixmap(ox, oy, scaled)

        # Draw detection overlays
        for region in self._regions:
            rtype = region.region_type
            fill_color = REGION_COLORS.get(rtype, QColor(128, 128, 128, 25))
            border_color = REGION_BORDER_COLORS.get(rtype, QColor(128, 128, 128, 200))
            label = REGION_LABELS.get(rtype, rtype)

            rx = int(region.x * self._scale) + ox
            ry = int(region.y * self._scale) + oy
            rw = int(region.width * self._scale)
            rh = int(region.height * self._scale)

            # Fill rectangle (semi-transparent)
            painter.setBrush(QBrush(fill_color))
            painter.setPen(QPen(border_color, 2))
            painter.drawRect(rx, ry, rw, rh)

            # Label text
            painter.setPen(border_color)
            font = QFont("Arial", 8, QFont.Weight.Bold)
            painter.setFont(font)
            text = label
            if region.data:
                text += f": {region.data[:30]}"
            painter.drawText(rx + 3, ry - 3, text)

        painter.end()


class ImageAnalysisView(QWidget):
    """Complete image analysis view with image display, region list, and controls."""
    generate_zpl_signal = pyqtSignal()
    batch_process_signal = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_label = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Top: buttons
        btn_layout = QHBoxLayout()

        self._btn_analyze = QPushButton("Analyze Image")
        self._btn_analyze.setToolTip("Detect barcodes, QR codes, text and image regions")
        self._btn_analyze.clicked.connect(self._analyze)
        self._btn_analyze.setEnabled(False)
        self._btn_analyze.setStyleSheet("QPushButton { padding: 6px 12px; font-weight: bold; }")
        btn_layout.addWidget(self._btn_analyze)

        self._btn_generate = QPushButton("Generate ZPL from Image")
        self._btn_generate.setToolTip("Convert detected regions to ZPL code")
        self._btn_generate.clicked.connect(self._generate_zpl)
        self._btn_generate.setEnabled(False)
        self._btn_generate.setStyleSheet(
            "QPushButton { padding: 6px 12px; font-weight: bold; "
            "background-color: #007ACC; color: white; }")
        btn_layout.addWidget(self._btn_generate)

        # Batch process button
        self._btn_batch = QPushButton("Batch Process...")
        self._btn_batch.setToolTip("Select multiple images, analyze and save ZPL files to a folder")
        self._btn_batch.clicked.connect(lambda: self.batch_process_signal.emit())
        self._btn_batch.setStyleSheet(
            "QPushButton { padding: 6px 12px; font-weight: bold; "
            "background-color: #5F7C3A; color: white; }")
        btn_layout.addWidget(self._btn_batch)

        # OCR engine selector
        btn_layout.addSpacing(15)
        btn_layout.addWidget(QLabel("OCR Engine:"))

        self._ocr_combo = QComboBox()
        self._ocr_combo.setToolTip("Select which OCR engine to use for text detection")
        self._ocr_combo.setMinimumWidth(160)

        # Probe engine availability once
        from ..image_processing.image_analyzer import ImageAnalyzer
        from ..utils.settings import AppSettings
        self._app_settings = AppSettings()
        tess_path = self._app_settings.tesseract_path
        self._engine_availability = ImageAnalyzer.get_available_engines(tesseract_path=tess_path)

        # (display_name, internal_key_or_None)
        self._engine_options = [
            ("Auto (All Available)", None),
            ("RapidOCR", "rapidocr"),
            ("EasyOCR", "easyocr"),
            ("Tesseract", "tesseract"),
        ]

        for display_name, key in self._engine_options:
            if key is None:
                self._ocr_combo.addItem(display_name)
            else:
                is_available = self._engine_availability.get(key, False)
                if is_available:
                    self._ocr_combo.addItem(display_name)
                else:
                    self._ocr_combo.addItem(f"{display_name} (not installed)")

        # Gray out unavailable engines
        model = self._ocr_combo.model()
        for i, (_, key) in enumerate(self._engine_options):
            if key is not None and not self._engine_availability.get(key, False):
                model.item(i).setEnabled(False)

        # Default to Tesseract if available, otherwise Auto
        default_idx = 0
        for i, (_, key) in enumerate(self._engine_options):
            if key == "tesseract" and self._engine_availability.get("tesseract", False):
                default_idx = i
                break
        self._ocr_combo.setCurrentIndex(default_idx)
        btn_layout.addWidget(self._ocr_combo)

        btn_layout.addStretch()

        # Legend
        legend_layout = QHBoxLayout()
        legend_layout.setSpacing(10)
        for rtype, color in REGION_BORDER_COLORS.items():
            dot = QLabel(f"  {REGION_LABELS[rtype]}")
            dot.setStyleSheet(
                f"color: {color.name()}; font-weight: bold; font-size: 11px;")
            legend_layout.addWidget(dot)
        legend_layout.addStretch()

        layout.addLayout(btn_layout)
        layout.addLayout(legend_layout)

        # Tesseract path row
        tess_layout = QHBoxLayout()
        tess_layout.addWidget(QLabel("Tesseract:"))
        self._tess_path_edit = QLineEdit(tess_path)
        self._tess_path_edit.setToolTip("Path to tesseract.exe")
        self._tess_path_edit.setMinimumWidth(250)
        self._tess_path_edit.editingFinished.connect(self._on_tesseract_path_changed)
        tess_layout.addWidget(self._tess_path_edit)
        self._btn_tess_browse = QPushButton("...")
        self._btn_tess_browse.setFixedWidth(30)
        self._btn_tess_browse.setToolTip("Browse for tesseract.exe")
        self._btn_tess_browse.clicked.connect(self._browse_tesseract)
        tess_layout.addWidget(self._btn_tess_browse)
        tess_layout.addStretch()
        layout.addLayout(tess_layout)

        # Main area: splitter with image view and region list
        splitter = QSplitter(Qt.Orientation.Vertical)

        self._image_widget = AnalysisImageWidget()
        splitter.addWidget(self._image_widget)

        # Region list
        self._region_list = QListWidget()
        self._region_list.setMaximumHeight(150)
        self._region_list.setAlternatingRowColors(True)
        splitter.addWidget(self._region_list)

        splitter.setSizes([400, 120])
        layout.addWidget(splitter)

        # Status
        self._status = QLabel("Select a label from the list to begin analysis")
        self._status.setStyleSheet("color: #808080; font-size: 11px; padding: 3px;")
        layout.addWidget(self._status)

    def set_label(self, label_item):
        """Set the current label for analysis."""
        self._current_label = label_item
        self._region_list.clear()

        if label_item is None:
            self._image_widget.clear()
            self._btn_analyze.setEnabled(False)
            self._btn_generate.setEnabled(False)
            self._status.setText("Select a label from the list to begin analysis")
            return

        self._image_widget.set_image(label_item.pixmap)
        self._btn_analyze.setEnabled(True)
        self._status.setText(
            f"Label: {label_item.name} | "
            f"{label_item.label_width}x{label_item.label_height} @ {label_item.dpi} DPI | "
            f"Image: {label_item.image.shape[1]}x{label_item.image.shape[0]}px")

        # Show existing analysis if available
        if label_item.analysis_results:
            self._show_results(label_item.analysis_results)
            self._btn_generate.setEnabled(True)

    def _analyze(self):
        """Run image analysis on the current label."""
        if self._current_label is None:
            return

        self._status.setText("Analyzing image...")
        self._region_list.clear()

        try:
            from ..image_processing.image_analyzer import ImageAnalyzer

            # Get selected engine from combo box
            selected_index = self._ocr_combo.currentIndex()
            _, selected_key = self._engine_options[selected_index]
            enabled_engines = {selected_key} if selected_key else None

            tess_path = self._app_settings.tesseract_path
            analyzer = ImageAnalyzer(enabled_engines=enabled_engines, tesseract_path=tess_path)
            results = analyzer.analyze(self._current_label.image)
            self._current_label.analysis_results = results
            self._show_results(results)
            self._btn_generate.setEnabled(len(results) > 0)
            engine_label = self._ocr_combo.currentText()
            self._status.setText(
                f"Analysis complete: {len(results)} regions detected "
                f"({self._count_by_type(results)}) | Engine: {engine_label}")
        except Exception as e:
            self._status.setText(f"Analysis error: {e}")
            import traceback
            traceback.print_exc()

    def _show_results(self, results):
        """Display analysis results."""
        self._image_widget.set_regions(results)
        self._region_list.clear()

        for i, r in enumerate(results):
            color = REGION_BORDER_COLORS.get(r.region_type, QColor(128, 128, 128))
            label = REGION_LABELS.get(r.region_type, r.region_type)
            text = f"[{label}] ({r.x},{r.y}) {r.width}x{r.height}"
            if r.data:
                text += f" - {r.data[:40]}"
            if r.barcode_type and r.barcode_type != "unknown":
                text += f" ({r.barcode_type})"

            item = QListWidgetItem(text)
            item.setForeground(color)
            self._region_list.addItem(item)

    def _generate_zpl(self):
        """Generate ZPL from the analyzed image."""
        if self._current_label is None:
            return
        self.generate_zpl_signal.emit()

    def _browse_tesseract(self):
        """Open file dialog to select tesseract.exe."""
        import os
        current = self._tess_path_edit.text()
        start_dir = os.path.dirname(current) if current else ""
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Tesseract Executable", start_dir,
            "Executable (tesseract.exe);;All Files (*.*)")
        if path:
            self._tess_path_edit.setText(path)
            self._on_tesseract_path_changed()

    def _on_tesseract_path_changed(self):
        """Save the new Tesseract path to settings and refresh engine availability."""
        path = self._tess_path_edit.text().strip()
        if path:
            self._app_settings.tesseract_path = path
            # Refresh engine availability with new path
            from ..image_processing.image_analyzer import ImageAnalyzer
            self._engine_availability = ImageAnalyzer.get_available_engines(tesseract_path=path)
            # Update combo box items
            model = self._ocr_combo.model()
            for i, (display_name, key) in enumerate(self._engine_options):
                if key is not None:
                    is_available = self._engine_availability.get(key, False)
                    self._ocr_combo.setItemText(
                        i, display_name if is_available else f"{display_name} (not installed)")
                    model.item(i).setEnabled(is_available)

    def _count_by_type(self, results):
        """Count regions by type for display."""
        counts = {}
        for r in results:
            label = REGION_LABELS.get(r.region_type, r.region_type)
            counts[label] = counts.get(label, 0) + 1
        return ", ".join(f"{v} {k}" for k, v in counts.items())
