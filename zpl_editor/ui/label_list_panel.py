"""
Label list panel for managing multiple imported label images.
Shows thumbnails in a list, supports add from file/clipboard and delete.
"""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                              QListWidget, QListWidgetItem, QLabel, QFileDialog,
                              QInputDialog, QMessageBox, QApplication, QMenu)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QImage, QIcon, QAction
import os
import numpy as np


class LabelItem:
    """Stores data for a single imported label."""
    def __init__(self, name: str, image: np.ndarray, pixmap: QPixmap,
                 label_width: int = 812, label_height: int = 1218, dpi: int = 203):
        self.name = name
        self.image = image          # OpenCV numpy array (BGR)
        self.pixmap = pixmap        # QPixmap for display
        self.label_width = label_width
        self.label_height = label_height
        self.dpi = dpi
        self.analysis_results = []  # DetectedRegion list
        self.generated_zpl = ""


class LabelListPanel(QWidget):
    label_selected = pyqtSignal(object)  # Emits LabelItem or None
    generate_zpl_requested = pyqtSignal(object)  # Emits LabelItem

    def __init__(self, parent=None):
        super().__init__(parent)
        self._labels = []  # List[LabelItem]
        self._init_ui()
        self.setMinimumWidth(180)
        self.setMaximumWidth(250)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        title = QLabel("Label Images")
        title.setStyleSheet("font-weight: bold; font-size: 13px; padding: 3px;")
        layout.addWidget(title)

        # Buttons - Row 1
        btn_row1 = QHBoxLayout()
        btn_row1.setSpacing(3)

        self._btn_new = QPushButton("+ New")
        self._btn_new.setToolTip("Create empty label (set size and DPI)")
        self._btn_new.clicked.connect(self._add_new_empty)
        btn_row1.addWidget(self._btn_new)

        self._btn_add = QPushButton("Import")
        self._btn_add.setToolTip("Add label image from file")
        self._btn_add.clicked.connect(self._add_from_file)
        btn_row1.addWidget(self._btn_add)

        layout.addLayout(btn_row1)

        # Buttons - Row 2
        btn_row2 = QHBoxLayout()
        btn_row2.setSpacing(3)

        self._btn_paste = QPushButton("Paste")
        self._btn_paste.setToolTip("Paste image from clipboard into selected label")
        self._btn_paste.clicked.connect(self._add_from_clipboard)
        btn_row2.addWidget(self._btn_paste)

        self._btn_delete = QPushButton("Delete")
        self._btn_delete.setToolTip("Delete selected label")
        self._btn_delete.clicked.connect(self._delete_selected)
        btn_row2.addWidget(self._btn_delete)

        layout.addLayout(btn_row2)

        # List
        self._list = QListWidget()
        self._list.setIconSize(QSize(120, 80))
        self._list.setSpacing(3)
        self._list.currentRowChanged.connect(self._on_selection_changed)
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self._list)

        # Info label
        self._info_label = QLabel("No labels imported")
        self._info_label.setStyleSheet("color: #808080; font-size: 11px; padding: 3px;")
        self._info_label.setWordWrap(True)
        layout.addWidget(self._info_label)

    def _add_from_file(self):
        """Add label image(s) from file dialog."""
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Open Label Image(s)", "",
            "Image Files (*.png *.jpg *.jpeg *.bmp *.tiff *.gif);;All Files (*.*)")
        if not paths:
            return

        # Ask label size and DPI once for batch
        label_w, label_h, dpi = self._ask_label_settings()
        if label_w is None:
            return

        for path in paths:
            self._import_image_file(path, label_w, label_h, dpi)

    def _add_new_empty(self):
        """Create a new empty label with user-specified size and DPI."""
        label_w, label_h, dpi = self._ask_label_settings()
        if label_w is None:
            return

        # Create white image at label dimensions
        image = np.ones((label_h, label_w, 3), dtype=np.uint8) * 255
        pixmap = self._numpy_to_pixmap(image)
        idx = len(self._labels) + 1
        label = LabelItem(f"Label_{idx}", image, pixmap, label_w, label_h, dpi)
        self._add_label(label)

    def _add_from_clipboard(self):
        """Paste image from clipboard into selected label, or create new."""
        clipboard = QApplication.clipboard()
        mime = clipboard.mimeData()

        if not mime.hasImage():
            QMessageBox.information(self, "Paste", "No image found in clipboard.")
            return

        qimage = clipboard.image()
        if qimage.isNull():
            QMessageBox.warning(self, "Paste", "Clipboard image is empty.")
            return

        row = self._list.currentRow()
        if 0 <= row < len(self._labels):
            # Paste into selected label (replace its image)
            self._paste_into_label(row, qimage)
        else:
            # No label selected, create new
            label_w, label_h, dpi = self._ask_label_settings()
            if label_w is None:
                return
            self._import_qimage(qimage, "Clipboard", label_w, label_h, dpi)

    def _paste_into_label(self, row: int, qimage: QImage):
        """Replace the image of an existing label with clipboard content."""
        try:
            import cv2
            label = self._labels[row]

            qimage = qimage.convertToFormat(QImage.Format.Format_RGB888)
            w = qimage.width()
            h = qimage.height()
            bpl = qimage.bytesPerLine()  # May differ from w*3 due to 32-bit alignment
            ptr = qimage.bits()
            ptr.setsize(h * bpl)
            if bpl == w * 3:
                arr = np.array(ptr).reshape(h, w, 3)
            else:
                # Handle row stride padding (QImage rows are 32-bit aligned)
                arr = np.array(ptr).reshape(h, bpl)[:, :w * 3].reshape(h, w, 3).copy()
            image = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
            print(f"[LabelList] Pasted image: {w}x{h}, label: {label.label_width}x{label.label_height}")

            # Save pasted image for diagnostic/debugging
            try:
                import os, tempfile
                diag_path = os.path.join(tempfile.gettempdir(), "zpl_pasted_debug.png")
                cv2.imwrite(diag_path, image)
                print(f"[LabelList] Debug image saved: {diag_path}")
            except Exception:
                pass

            label.image = image
            label.pixmap = QPixmap.fromImage(qimage)
            label.analysis_results = []
            label.generated_zpl = ""

            # Update thumbnail
            thumb = label.pixmap.scaled(120, 80, Qt.AspectRatioMode.KeepAspectRatio,
                                        Qt.TransformationMode.SmoothTransformation)
            self._list.item(row).setIcon(QIcon(thumb))

            # Re-emit selection to refresh the analysis view
            self.label_selected.emit(label)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Paste failed:\n{e}")

    def _ask_label_settings(self):
        """Ask user for label dimensions and DPI using the label size dialog."""
        from .label_size_dialog import LabelSizeDialog
        dlg = LabelSizeDialog(self)
        if dlg.exec():
            return dlg.get_result()
        return None, None, None

    def _import_image_file(self, path: str, label_w: int, label_h: int, dpi: int):
        """Import an image file as a label."""
        try:
            import cv2
            image = cv2.imread(path)
            if image is None:
                QMessageBox.warning(self, "Error", f"Cannot read image:\n{path}")
                return

            name = os.path.splitext(os.path.basename(path))[0]
            pixmap = self._numpy_to_pixmap(image)
            label = LabelItem(name, image, pixmap, label_w, label_h, dpi)
            self._add_label(label)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Import failed:\n{e}")

    def _import_qimage(self, qimage: QImage, name: str,
                       label_w: int, label_h: int, dpi: int):
        """Import a QImage as a label."""
        try:
            import cv2
            # Convert QImage to numpy array (handle row stride alignment)
            qimage = qimage.convertToFormat(QImage.Format.Format_RGB888)
            w = qimage.width()
            h = qimage.height()
            bpl = qimage.bytesPerLine()
            ptr = qimage.bits()
            ptr.setsize(h * bpl)
            if bpl == w * 3:
                arr = np.array(ptr).reshape(h, w, 3)
            else:
                arr = np.array(ptr).reshape(h, bpl)[:, :w * 3].reshape(h, w, 3).copy()
            image = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)

            pixmap = QPixmap.fromImage(qimage)
            idx = len(self._labels) + 1
            label = LabelItem(f"{name}_{idx}", image, pixmap, label_w, label_h, dpi)
            self._add_label(label)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Paste failed:\n{e}")

    def _add_label(self, label: LabelItem):
        """Add a label to the list."""
        self._labels.append(label)

        item = QListWidgetItem()
        item.setText(label.name)
        # Create thumbnail
        thumb = label.pixmap.scaled(120, 80, Qt.AspectRatioMode.KeepAspectRatio,
                                    Qt.TransformationMode.SmoothTransformation)
        item.setIcon(QIcon(thumb))
        item.setToolTip(f"{label.name}\n{label.label_width}x{label.label_height} @ {label.dpi} DPI")
        self._list.addItem(item)
        self._list.setCurrentRow(self._list.count() - 1)
        self._update_info()

    def _delete_selected(self):
        """Delete the selected label."""
        row = self._list.currentRow()
        if row < 0:
            return
        self._list.takeItem(row)
        self._labels.pop(row)
        self._update_info()
        if self._list.count() == 0:
            self.label_selected.emit(None)

    def _on_selection_changed(self, row: int):
        """Handle label selection change."""
        if 0 <= row < len(self._labels):
            self.label_selected.emit(self._labels[row])
        else:
            self.label_selected.emit(None)

    def _show_context_menu(self, pos):
        """Show context menu for label list."""
        row = self._list.currentRow()
        if row < 0:
            return
        menu = QMenu(self)
        rename_action = QAction("Rename", self)
        rename_action.triggered.connect(lambda: self._rename_label(row))
        menu.addAction(rename_action)
        delete_action = QAction("Delete", self)
        delete_action.triggered.connect(self._delete_selected)
        menu.addAction(delete_action)
        menu.exec(self._list.mapToGlobal(pos))

    def _rename_label(self, row: int):
        """Rename a label."""
        if row < 0 or row >= len(self._labels):
            return
        name, ok = QInputDialog.getText(
            self, "Rename", "New name:", text=self._labels[row].name)
        if ok and name:
            self._labels[row].name = name
            self._list.item(row).setText(name)

    def _update_info(self):
        count = len(self._labels)
        if count == 0:
            self._info_label.setText("No labels imported")
        else:
            self._info_label.setText(f"{count} label(s) imported")

    def get_selected_label(self) -> LabelItem:
        """Get the currently selected label."""
        row = self._list.currentRow()
        if 0 <= row < len(self._labels):
            return self._labels[row]
        return None

    @staticmethod
    def _numpy_to_pixmap(image: np.ndarray) -> QPixmap:
        """Convert numpy BGR image to QPixmap."""
        import cv2
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        qimage = QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        return QPixmap.fromImage(qimage.copy())
