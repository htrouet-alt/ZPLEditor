import traceback
from PyQt6.QtWidgets import (QMainWindow, QSplitter, QWidget, QVBoxLayout,
                              QFileDialog, QMessageBox, QDockWidget,
                              QApplication, QHBoxLayout, QTabWidget)
from PyQt6.QtCore import Qt, QSettings, QTimer
from PyQt6.QtGui import QAction, QKeySequence, QIcon
from .code_editor import CodeEditor
from .canvas_view import CanvasView, CanvasViewWidget
from .canvas_scene import CanvasScene
from .property_panel import PropertyPanel
from .toolbar import EditorToolBar
from .statusbar import EditorStatusBar
from .linter_panel import LinterPanel
from .label_list_panel import LabelListPanel
from .image_analysis_view import ImageAnalysisView
from ..core.zpl_parser import ZPLParser
from ..core.zpl_generator import ZPLGenerator
from ..core.label_model import LabelModel
from ..elements.base_element import BaseElement
from ..elements.text_element import TextElement
from ..elements.box_element import BoxElement
from ..elements.line_element import LineElement
from ..elements.circle_element import CircleElement
from ..elements.diagonal_line import DiagonalLineElement
from ..elements.barcode_element import BarcodeElement
from ..elements.qr_element import QRElement


DARK_THEME = """
QMainWindow, QWidget {
    background-color: #1E1E1E;
    color: #D4D4D4;
}
QMenuBar {
    background-color: #252526;
    color: #D4D4D4;
    border-bottom: 1px solid #3C3C3C;
}
QMenuBar::item:selected {
    background-color: #094771;
}
QMenu {
    background-color: #252526;
    color: #D4D4D4;
    border: 1px solid #3C3C3C;
}
QMenu::item:selected {
    background-color: #094771;
}
QToolBar {
    background-color: #252526;
    border-bottom: 1px solid #3C3C3C;
    spacing: 3px;
    padding: 2px;
}
QToolButton {
    background-color: #333333;
    color: #D4D4D4;
    border: 1px solid #3C3C3C;
    border-radius: 3px;
    padding: 4px 8px;
    margin: 1px;
}
QToolButton:hover {
    background-color: #094771;
    border-color: #007ACC;
}
QToolButton:checked {
    background-color: #007ACC;
    border-color: #007ACC;
}
QSplitter::handle:horizontal {
    background-color: #007ACC;
    width: 5px;
    margin: 0px;
    border-left: 1px solid #005A9E;
    border-right: 1px solid #005A9E;
}
QSplitter::handle:horizontal:hover {
    background-color: #1A8CFF;
}
QSplitter::handle:vertical {
    background-color: #007ACC;
    height: 5px;
    margin: 0px;
    border-top: 1px solid #005A9E;
    border-bottom: 1px solid #005A9E;
}
QSplitter::handle:vertical:hover {
    background-color: #1A8CFF;
}
QStatusBar {
    background-color: #007ACC;
    color: #FFFFFF;
}
QStatusBar QLabel {
    color: #FFFFFF;
    padding: 0 10px;
}
QScrollBar:vertical, QScrollBar:horizontal {
    background-color: #1E1E1E;
    width: 12px;
    height: 12px;
}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
    background-color: #424242;
    min-height: 20px;
    min-width: 20px;
    border-radius: 3px;
}
QScrollBar::handle:hover {
    background-color: #525252;
}
QScrollBar::add-line, QScrollBar::sub-line {
    height: 0; width: 0;
}
QGroupBox {
    color: #D4D4D4;
    border: 1px solid #3C3C3C;
    border-radius: 4px;
    margin-top: 8px;
    padding-top: 10px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 3px;
}
QSpinBox, QComboBox, QLineEdit {
    background-color: #333333;
    color: #D4D4D4;
    border: 1px solid #3C3C3C;
    border-radius: 3px;
    padding: 3px;
}
QSpinBox:focus, QComboBox:focus, QLineEdit:focus {
    border-color: #007ACC;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QComboBox QAbstractItemView {
    background-color: #252526;
    color: #D4D4D4;
    selection-background-color: #094771;
}
QCheckBox {
    color: #D4D4D4;
}
QCheckBox::indicator {
    width: 16px; height: 16px;
    border: 1px solid #3C3C3C;
    border-radius: 3px;
    background-color: #333333;
}
QCheckBox::indicator:checked {
    background-color: #007ACC;
    border-color: #007ACC;
}
QDockWidget {
    color: #D4D4D4;
    titlebar-close-icon: none;
}
QDockWidget::title {
    background-color: #252526;
    padding: 5px;
    border-bottom: 1px solid #3C3C3C;
}
QLabel {
    color: #D4D4D4;
}
QSlider::groove:horizontal {
    background: #3C3C3C;
    height: 4px;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #007ACC;
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}
QTabWidget::pane {
    border: 1px solid #3C3C3C;
    background-color: #1E1E1E;
}
QTabBar::tab {
    background-color: #2D2D2D;
    color: #808080;
    border: 1px solid #3C3C3C;
    border-bottom: none;
    padding: 6px 14px;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background-color: #1E1E1E;
    color: #D4D4D4;
    border-bottom: 2px solid #007ACC;
}
QTabBar::tab:hover {
    color: #D4D4D4;
    background-color: #333333;
}
QPushButton {
    background-color: #333333;
    color: #D4D4D4;
    border: 1px solid #3C3C3C;
    border-radius: 3px;
    padding: 4px 10px;
}
QPushButton:hover {
    background-color: #094771;
    border-color: #007ACC;
}
QPushButton:disabled {
    color: #666666;
    background-color: #2D2D2D;
}
QListWidget {
    background-color: #252526;
    color: #D4D4D4;
    border: 1px solid #3C3C3C;
    border-radius: 3px;
}
QListWidget::item:selected {
    background-color: #094771;
}
QListWidget::item:hover {
    background-color: #2A2D2E;
}
"""

LIGHT_THEME = """
QMainWindow, QWidget {
    background-color: #F3F3F3;
    color: #1E1E1E;
}
QMenuBar {
    background-color: #E8E8E8;
    color: #1E1E1E;
}
QMenu {
    background-color: #FFFFFF;
    color: #1E1E1E;
    border: 1px solid #CCCCCC;
}
QMenu::item:selected {
    background-color: #0060C0;
    color: #FFFFFF;
}
QToolBar {
    background-color: #E8E8E8;
    border-bottom: 1px solid #CCCCCC;
}
QToolButton {
    background-color: #FFFFFF;
    color: #1E1E1E;
    border: 1px solid #CCCCCC;
    border-radius: 3px;
    padding: 4px 8px;
}
QToolButton:hover {
    background-color: #0060C0;
    color: #FFFFFF;
}
QToolButton:checked {
    background-color: #0060C0;
    color: #FFFFFF;
}
QSplitter::handle:horizontal {
    background-color: #0060C0;
    width: 5px;
    border-left: 1px solid #004A99;
    border-right: 1px solid #004A99;
}
QSplitter::handle:horizontal:hover {
    background-color: #3399FF;
}
QSplitter::handle:vertical {
    background-color: #0060C0;
    height: 5px;
    border-top: 1px solid #004A99;
    border-bottom: 1px solid #004A99;
}
QSplitter::handle:vertical:hover {
    background-color: #3399FF;
}
QStatusBar {
    background-color: #0060C0;
    color: #FFFFFF;
}
QStatusBar QLabel {
    color: #FFFFFF;
}
QGroupBox {
    color: #1E1E1E;
    border: 1px solid #CCCCCC;
}
QSpinBox, QComboBox, QLineEdit {
    background-color: #FFFFFF;
    color: #1E1E1E;
    border: 1px solid #CCCCCC;
}
QLabel {
    color: #1E1E1E;
}
QTabWidget::pane {
    border: 1px solid #CCCCCC;
    background-color: #FFFFFF;
}
QTabBar::tab {
    background-color: #E8E8E8;
    color: #666666;
    border: 1px solid #CCCCCC;
    border-bottom: none;
    padding: 6px 14px;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background-color: #FFFFFF;
    color: #1E1E1E;
    border-bottom: 2px solid #0060C0;
}
QPushButton {
    background-color: #FFFFFF;
    color: #1E1E1E;
    border: 1px solid #CCCCCC;
    border-radius: 3px;
    padding: 4px 10px;
}
QPushButton:hover {
    background-color: #0060C0;
    color: #FFFFFF;
}
QPushButton:disabled {
    color: #999999;
    background-color: #E8E8E8;
}
QListWidget {
    background-color: #FFFFFF;
    color: #1E1E1E;
    border: 1px solid #CCCCCC;
    border-radius: 3px;
}
QListWidget::item:selected {
    background-color: #0060C0;
    color: #FFFFFF;
}
QListWidget::item:hover {
    background-color: #E8E8E8;
}
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ZPL Visual Editor")
        self.setMinimumSize(1200, 800)

        self._parser = ZPLParser()
        self._generator = ZPLGenerator()
        self._syncing = False
        self._current_file = None
        self._dark_theme = True
        self._dpi = 203

        self._settings = QSettings("ZPLEditor", "ZPLEditor")

        self._init_ui()
        self._create_menus()
        self._create_shortcuts()
        self._connect_signals()
        self._apply_theme()
        self._restore_state()

        self._load_default_zpl()

    def _init_ui(self):
        self._toolbar = EditorToolBar(self)
        self.addToolBar(self._toolbar)

        self._statusbar = EditorStatusBar(self)
        self.setStatusBar(self._statusbar)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Main horizontal splitter: label list | code+tabs | canvas
        self._splitter = QSplitter(Qt.Orientation.Horizontal)

        # Far left: Label list panel
        self._label_list_panel = LabelListPanel()
        self._splitter.addWidget(self._label_list_panel)

        # Middle panel: code editor (top) + tabs (bottom) in a vertical splitter
        self._left_splitter = QSplitter(Qt.Orientation.Vertical)

        self._code_editor = CodeEditor()

        # Tabbed bottom panel with Linter and Image Analysis
        self._bottom_tabs = QTabWidget()
        self._bottom_tabs.setTabPosition(QTabWidget.TabPosition.South)
        self._linter_panel = LinterPanel()
        self._bottom_tabs.addTab(self._linter_panel, "Linter Warnings")

        self._image_analysis_view = ImageAnalysisView()
        self._bottom_tabs.addTab(self._image_analysis_view, "Image Analysis")

        self._left_splitter.addWidget(self._code_editor)
        self._left_splitter.addWidget(self._bottom_tabs)
        self._left_splitter.setSizes([500, 150])

        self._splitter.addWidget(self._left_splitter)

        # Right panel: canvas with rulers
        self._scene = CanvasScene()
        self._canvas_widget = CanvasViewWidget(self._scene)
        self._canvas_view = self._canvas_widget.canvas_view
        self._splitter.addWidget(self._canvas_widget)

        self._splitter.setSizes([180, 420, 600])
        layout.addWidget(self._splitter)

        # Property panel dock
        self._property_panel = PropertyPanel()
        dock = QDockWidget("Properties", self)
        dock.setWidget(self._property_panel)
        dock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea | Qt.DockWidgetArea.LeftDockWidgetArea)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)

    def _add_action(self, menu, text, slot, shortcut=None):
        action = QAction(text, self)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        action.triggered.connect(slot)
        menu.addAction(action)
        return action

    def _create_menus(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("File")
        self._add_action(file_menu, "New Label", self._new_label, "Ctrl+N")
        self._add_action(file_menu, "Open ZPL...", self._open_file, "Ctrl+O")
        self._add_action(file_menu, "Save ZPL...", self._save_file, "Ctrl+S")
        file_menu.addSeparator()
        self._add_action(file_menu, "Import Image...", self._import_image, "Ctrl+I")
        self._add_action(file_menu, "Paste Image from Clipboard", self._paste_image, "Ctrl+Shift+V")
        file_menu.addSeparator()
        self._add_action(file_menu, "Export PNG...", self._export_png)
        self._add_action(file_menu, "Export PDF...", self._export_pdf)
        file_menu.addSeparator()
        self._add_action(file_menu, "Exit", self.close, "Alt+F4")

        edit_menu = menubar.addMenu("Edit")
        self._add_action(edit_menu, "Undo", self._undo, "Ctrl+Z")
        self._add_action(edit_menu, "Redo", self._redo, "Ctrl+Y")
        edit_menu.addSeparator()
        self._add_action(edit_menu, "Delete", self._delete_selected, "Delete")
        self._add_action(edit_menu, "Clone", self._clone_selected, "Ctrl+D")
        self._add_action(edit_menu, "Select All", self._select_all, "Ctrl+A")
        edit_menu.addSeparator()
        self._add_action(edit_menu, "Settings...", self._show_settings)

        view_menu = menubar.addMenu("View")
        self._add_action(view_menu, "Zoom In", self._canvas_view.zoom_in, "Ctrl+=")
        self._add_action(view_menu, "Zoom Out", self._canvas_view.zoom_out, "Ctrl+-")
        self._add_action(view_menu, "Fit to Window", self._canvas_view.fit_in_view, "Ctrl+0")
        view_menu.addSeparator()
        self._grid_action = QAction("Show Grid", self)
        self._grid_action.setCheckable(True)
        self._grid_action.setChecked(True)
        self._grid_action.triggered.connect(self._toggle_grid)
        view_menu.addAction(self._grid_action)
        self._snap_action = QAction("Snap to Grid", self)
        self._snap_action.setCheckable(True)
        self._snap_action.setChecked(False)
        self._snap_action.triggered.connect(self._toggle_snap)
        view_menu.addAction(self._snap_action)
        self._ruler_action = QAction("Show Ruler", self)
        self._ruler_action.setCheckable(True)
        self._ruler_action.setChecked(True)
        self._ruler_action.triggered.connect(self._toggle_ruler)
        view_menu.addAction(self._ruler_action)
        view_menu.addSeparator()
        self._add_action(view_menu, "Dark Theme", lambda: self._set_theme(True))
        self._add_action(view_menu, "Light Theme", lambda: self._set_theme(False))

        label_menu = menubar.addMenu("Label")
        self._add_action(label_menu, "Label Size...", self._set_label_size)
        dpi_menu = label_menu.addMenu("DPI")
        for dpi in [203, 300, 600]:
            action = QAction(f"{dpi} DPI", self)
            action.triggered.connect(lambda checked, d=dpi: self._set_dpi(d))
            dpi_menu.addAction(action)

        insert_menu = menubar.addMenu("Insert")
        self._add_action(insert_menu, "Text", lambda: self._insert_element("text"))
        self._add_action(insert_menu, "Rectangle", lambda: self._insert_element("rect"))
        self._add_action(insert_menu, "Line", lambda: self._insert_element("line"))
        self._add_action(insert_menu, "Circle", lambda: self._insert_element("circle"))
        self._add_action(insert_menu, "Barcode", lambda: self._insert_element("barcode"))
        self._add_action(insert_menu, "QR Code", lambda: self._insert_element("qrcode"))

        help_menu = menubar.addMenu("Help")
        self._add_action(help_menu, "About", self._show_about)

    def _create_shortcuts(self):
        pass

    def _connect_signals(self):
        self._code_editor.code_changed.connect(self._on_code_changed)
        self._scene.element_changed.connect(self._on_canvas_changed)
        self._scene.selection_changed_signal.connect(self._on_selection_changed)
        self._canvas_view.zoom_changed.connect(self._on_zoom_changed)
        self._canvas_view.mouse_position_changed.connect(self._statusbar.update_position)
        self._toolbar.tool_selected.connect(self._on_tool_selected)
        self._toolbar.zoom_value_changed.connect(lambda v: self._canvas_view.set_zoom(v / 100.0))
        self._toolbar.action_triggered.connect(self._on_toolbar_action)
        self._property_panel.property_changed.connect(self._on_property_changed)

        # Image processing signals
        self._label_list_panel.label_selected.connect(self._on_label_selected)
        self._image_analysis_view.generate_zpl_signal.connect(self._on_generate_zpl_from_image)
        self._image_analysis_view.batch_process_signal.connect(self._batch_process_images)

    def _apply_theme(self):
        if self._dark_theme:
            self.setStyleSheet(DARK_THEME)
        else:
            self.setStyleSheet(LIGHT_THEME)

    def _set_theme(self, dark: bool):
        self._dark_theme = dark
        self._apply_theme()

    def _restore_state(self):
        try:
            geometry = self._settings.value("geometry")
            if geometry:
                self.restoreGeometry(geometry)
            state = self._settings.value("windowState")
            if state:
                self.restoreState(state)
            splitter_sizes = self._settings.value("splitterSizes")
            if splitter_sizes:
                self._splitter.restoreState(splitter_sizes)
        except Exception:
            pass

    def closeEvent(self, event):
        try:
            self._settings.setValue("geometry", self.saveGeometry())
            self._settings.setValue("windowState", self.saveState())
            self._settings.setValue("splitterSizes", self._splitter.saveState())
        except Exception:
            pass
        super().closeEvent(event)

    def _load_default_zpl(self):
        default_zpl = """^XA
^PW812
^LL1218

^FX -- Top line --
^FO50,50^GB712,0,3^FS

^FX -- Title --
^FO50,80^A0N,40,40^FDShipping Label^FS

^FX -- Box --
^FO50,140^GB712,200,2^FS

^FX -- Address --
^FO70,160^A0N,28,28^FDJohn Doe^FS
^FO70,195^A0N,24,24^FD123 Main Street^FS
^FO70,225^A0N,24,24^FDNew York, NY 10001^FS
^FO70,260^A0N,24,24^FDUnited States^FS

^FX -- Barcode --
^FO150,380^BY3
^BCN,120,Y,N,N
^FD1234567890^FS

^FX -- QR Code --
^FO550,140^BQN,2,5^FDQA,https://example.com^FS

^FX -- Bottom line --
^FO50,550^GB712,0,3^FS

^FX -- Footer --
^FO50,580^A0N,20,20^FDTracking: 1Z999AA10123456784^FS

^XZ"""
        self._code_editor.set_code(default_zpl)
        self._parse_and_render(default_zpl)

    def _on_code_changed(self, code: str):
        if not self._syncing:
            self._parse_and_render(code)

    def _parse_and_render(self, code: str):
        self._syncing = True
        try:
            print(f"[MainWindow] Parsing ZPL ({len(code)} chars)...")
            model = self._parser.parse(code)
            print(f"[MainWindow] Parsed model: {len(model.elements)} elements")
            
            print("[MainWindow] Loading model into canvas...")
            self._scene.load_from_model(model)
            
            scene_elem_count = len(self._scene.get_elements())
            print(f"[MainWindow] Canvas now has {scene_elem_count} elements")
            
            self._statusbar.update_info(f"Parsed: {len(model.elements)} elements, Canvas: {scene_elem_count}")
            
            # Update linter
            try:
                self._linter_panel.update_warnings(model)
            except Exception as e:
                print(f"[MainWindow] Linter error: {e}")
        except Exception as e:
            self._statusbar.update_info(f"Parse error: {str(e)}")
            print(f"[ZPL Parse Error] {e}\n{traceback.format_exc()}")
        finally:
            self._syncing = False

    def _on_canvas_changed(self):
        if not self._syncing:
            self._syncing = True
            try:
                model = self._scene.get_model()
                code = self._generator.generate(model)
                self._code_editor.set_code(code)
                self._statusbar.update_info(f"Elements: {len(model.elements)}")
                try:
                    self._linter_panel.update_warnings(model)
                except Exception:
                    pass
            except Exception as e:
                self._statusbar.update_info(f"Generate error: {str(e)}")
                print(f"[ZPL Generate Error] {e}\n{traceback.format_exc()}")
            finally:
                self._syncing = False

    def _on_selection_changed(self):
        try:
            selected = self._scene.selectedItems()
            if len(selected) == 1 and isinstance(selected[0], BaseElement):
                self._property_panel.set_element(selected[0])
            else:
                self._property_panel.set_element(None)
        except Exception as e:
            print(f"[Selection Error] {e}")

    def _on_property_changed(self):
        self._on_canvas_changed()

    def _on_zoom_changed(self, factor: float):
        self._statusbar.update_zoom(factor)
        self._toolbar.set_zoom_display(factor)

    def _on_tool_selected(self, tool: str):
        self._statusbar.update_info(f"Tool: {tool}")

    def _on_toolbar_action(self, action: str):
        if action == "undo":
            self._undo()
        elif action == "redo":
            self._redo()

    def _new_label(self):
        self._code_editor.set_code("^XA\n\n^XZ")
        self._parse_and_render("^XA\n\n^XZ")
        self._current_file = None
        self.setWindowTitle("ZPL Visual Editor - New Label")

    def _open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open ZPL File", "",
            "ZPL Files (*.zpl *.txt);;All Files (*.*)")
        if path:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    code = f.read()
                self._code_editor.set_code(code)
                self._parse_and_render(code)
                self._current_file = path
                self.setWindowTitle(f"ZPL Visual Editor - {path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Cannot open file:\n{e}")

    def _save_file(self):
        path = self._current_file
        if not path:
            path, _ = QFileDialog.getSaveFileName(
                self, "Save ZPL File", "",
                "ZPL Files (*.zpl);;Text Files (*.txt);;All Files (*.*)")
        if path:
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(self._code_editor.toPlainText())
                self._current_file = path
                self.setWindowTitle(f"ZPL Visual Editor - {path}")
                self._statusbar.update_info(f"Saved: {path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Cannot save file:\n{e}")

    def _export_png(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export PNG", "", "PNG Files (*.png)")
        if path:
            try:
                from PyQt6.QtGui import QImage, QPainter
                from PyQt6.QtCore import QRectF
                rect = QRectF(0, 0, self._scene._label_width, self._scene._label_height)
                image = QImage(int(rect.width()), int(rect.height()),
                              QImage.Format.Format_ARGB32_Premultiplied)
                image.fill(Qt.GlobalColor.white)
                painter = QPainter(image)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                self._scene.render(painter, rect, rect)
                painter.end()
                image.save(path, "PNG")
                self._statusbar.update_info(f"Exported: {path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Export failed:\n{e}")

    def _export_pdf(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export PDF", "", "PDF Files (*.pdf)")
        if path:
            try:
                from PyQt6.QtGui import QPainter
                from PyQt6.QtCore import QRectF, QMarginsF
                from PyQt6.QtPrintSupport import QPrinter

                printer = QPrinter(QPrinter.PrinterMode.HighResolution)
                printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
                printer.setOutputFileName(path)

                rect = QRectF(0, 0, self._scene._label_width, self._scene._label_height)
                painter = QPainter(printer)
                self._scene.render(painter, painter.viewport(), rect)
                painter.end()
                self._statusbar.update_info(f"PDF exported: {path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"PDF export failed:\n{e}")

    def _undo(self):
        self._code_editor.undo()

    def _redo(self):
        self._code_editor.redo()

    def _delete_selected(self):
        try:
            self._scene.delete_selected()
        except Exception as e:
            print(f"[Delete Error] {e}")

    def _clone_selected(self):
        try:
            self._scene.clone_selected()
        except Exception as e:
            print(f"[Clone Error] {e}")

    def _select_all(self):
        self._scene.select_all()

    def _toggle_grid(self, checked: bool):
        self._scene.set_grid_visible(checked)

    def _toggle_snap(self, checked: bool):
        self._scene.set_snap_to_grid(checked)

    def _toggle_ruler(self, checked: bool):
        self._canvas_widget.set_rulers_visible(checked)

    def _set_label_size(self):
        from .label_size_dialog import LabelSizeDialog
        dlg = LabelSizeDialog(
            self,
            current_width=self._scene._label_width,
            current_height=self._scene._label_height,
            current_dpi=getattr(self, '_dpi', 203))
        if dlg.exec():
            w, h, dpi = dlg.get_result()
            self._scene.set_label_size(w, h)
            self._set_dpi(dpi)
            # Sync selected label_item dimensions
            label_item = self._label_list_panel.get_selected_label()
            if label_item:
                label_item.label_width = w
                label_item.label_height = h
                label_item.dpi = dpi
            self._on_canvas_changed()

    def _set_dpi(self, dpi: int):
        self._dpi = dpi
        self._statusbar.update_dpi(dpi)

    def _insert_element(self, elem_type: str):
        try:
            cx = self._scene._label_width // 2
            cy = self._scene._label_height // 2

            if elem_type == "text":
                elem = TextElement(cx - 50, cy - 15, "New Text", "0", 30, 0, "N")
            elif elem_type == "rect":
                elem = BoxElement(cx - 50, cy - 50, 100, 100, 2, "B", 0)
            elif elem_type == "line":
                elem = LineElement(cx - 50, cy, 100, 0, 2, "B")
            elif elem_type == "circle":
                elem = CircleElement(cx - 50, cy - 50, 100, 2, "B")
            elif elem_type == "barcode":
                elem = BarcodeElement(cx - 80, cy - 50, "code128", "123456789", 2, 100, "N", "Y")
            elif elem_type == "qrcode":
                elem = QRElement(cx - 50, cy - 50, "https://example.com", 3, 2, "N")
            else:
                return

            self._scene.add_new_element(elem)
        except Exception as e:
            self._statusbar.update_info(f"Insert error: {str(e)}")
            print(f"[Insert Error] {e}\n{traceback.format_exc()}")

    # -- Image processing methods --

    def _import_image(self):
        """Import image(s) from file via the label list panel."""
        self._label_list_panel._add_from_file()

    def _paste_image(self):
        """Paste image from clipboard via the label list panel."""
        self._label_list_panel._add_from_clipboard()

    def _on_label_selected(self, label_item):
        """Handle label selection from the label list panel."""
        self._image_analysis_view.set_label(label_item)
        if label_item is not None:
            # Switch to Image Analysis tab
            self._bottom_tabs.setCurrentWidget(self._image_analysis_view)

    def _on_generate_zpl_from_image(self):
        """Generate ZPL from the currently analyzed image."""
        label_item = self._label_list_panel.get_selected_label()
        if label_item is None:
            QMessageBox.warning(self, "Generate ZPL",
                                "No label selected. Please select a label first.")
            return

        if not label_item.analysis_results:
            QMessageBox.warning(self, "Generate ZPL",
                                "No analysis results. Please analyze the image first.")
            return
        
        print(f"[MainWindow] Analysis results: {len(label_item.analysis_results)} regions")

        # For Smart Detection mode, use image pixel dimensions as label
        # dimensions so that detected region coordinates (in pixel space)
        # map 1:1 to ZPL dot coordinates.  This matches test_pixel_loop.py
        # and avoids non-uniform scaling distortion when image aspect ratio
        # differs from the physical label aspect ratio.
        img_h, img_w = label_item.image.shape[:2]
        dpi = label_item.dpi

        print(f"[MainWindow] Image: {img_w}x{img_h} @ {dpi} DPI")

        try:
            from ..image_processing.zpl_from_image import ZPLFromImage
            generator = ZPLFromImage()

            # Always use Smart Detection with image dimensions as label dimensions
            # (1:1 coordinate mapping) so detected regions map directly to ZPL coordinates.
            label_w = img_w
            label_h = img_h
            zpl = generator.generate(
                label_item.image, label_item.analysis_results,
                label_w, label_h, dpi)

            # Set scene to match the generated ZPL dimensions
            self._scene.set_label_size(label_w, label_h)

            # Validate generated ZPL
            if not zpl or len(zpl) < 10:
                QMessageBox.critical(self, "Error", "Generated ZPL is empty or too short!")
                return
            
            print(f"[MainWindow] Generated ZPL: {len(zpl)} characters")
            
            # Count elements in generated ZPL
            fd_count = zpl.count('^FD')
            gb_count = zpl.count('^GB')
            print(f"[MainWindow] ZPL contains: {fd_count}^FD, {gb_count}^GB commands")

            label_item.generated_zpl = zpl
            self._code_editor.set_code(zpl)
            
            # Parse and render
            print("[MainWindow] Parsing and rendering ZPL...")
            self._parse_and_render(zpl)
            
            # Count elements in scene after render
            elem_count = len(self._scene.get_elements())
            print(f"[MainWindow] Scene now has {elem_count} elements")
            
            self._statusbar.update_info(
                f"ZPL generated: {label_item.name} - {elem_count} elements")
            
            # Switch to canvas view (in case user is on code editor)
            # This ensures the render is visible
            self._scene.update()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"ZPL generation failed:\n{e}")
            import traceback
            traceback.print_exc()

    def _show_settings(self):
        """Open the settings dialog."""
        from .settings_dialog import SettingsDialog
        dlg = SettingsDialog(self)
        if dlg.exec():
            # Sync updated tesseract path to the Image Analysis view
            from ..utils.settings import AppSettings
            new_path = AppSettings().tesseract_path
            self._image_analysis_view._tess_path_edit.setText(new_path)
            self._image_analysis_view._on_tesseract_path_changed()

    def _batch_process_images(self):
        """Batch process: select images, analyze, generate ZPL, save to folder."""
        import os
        import cv2
        from PyQt6.QtWidgets import QProgressDialog

        # 1. Select images
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select Label Images for Batch Processing", "",
            "Image Files (*.png *.jpg *.jpeg *.bmp *.tiff *.gif);;All Files (*.*)")
        if not paths:
            return

        # 2. Select output folder
        output_dir = QFileDialog.getExistingDirectory(
            self, "Select Output Folder for ZPL Files")
        if not output_dir:
            return

        # 3. Get current engine settings from the analysis view
        selected_index = self._image_analysis_view._ocr_combo.currentIndex()
        _, selected_key = self._image_analysis_view._engine_options[selected_index]
        enabled_engines = {selected_key} if selected_key else None

        from ..utils.settings import AppSettings
        tess_path = AppSettings().tesseract_path

        # 4. Progress dialog
        progress = QProgressDialog("Processing images...", "Cancel", 0, len(paths), self)
        progress.setWindowTitle("Batch Processing")
        progress.setMinimumDuration(0)
        progress.setWindowModality(Qt.WindowModality.WindowModal)

        success_count = 0
        errors = []

        for i, img_path in enumerate(paths):
            if progress.wasCanceled():
                break

            base_name = os.path.splitext(os.path.basename(img_path))[0]
            progress.setLabelText(f"Processing: {base_name} ({i+1}/{len(paths)})")
            progress.setValue(i)
            QApplication.processEvents()

            try:
                # Load image
                img = cv2.imread(img_path)
                if img is None:
                    errors.append(f"{base_name}: Failed to load image")
                    continue

                img_h, img_w = img.shape[:2]

                # Analyze
                from ..image_processing.image_analyzer import ImageAnalyzer
                analyzer = ImageAnalyzer(enabled_engines=enabled_engines, tesseract_path=tess_path)
                regions = analyzer.analyze(img)

                if not regions:
                    errors.append(f"{base_name}: No regions detected")
                    continue

                # Generate ZPL
                from ..image_processing.zpl_from_image import ZPLFromImage
                generator = ZPLFromImage()
                zpl = generator.generate(img, regions, img_w, img_h, self._dpi)

                if not zpl or len(zpl) < 10:
                    errors.append(f"{base_name}: Generated ZPL is empty")
                    continue

                # Save
                out_path = os.path.join(output_dir, f"{base_name}.zpl")
                with open(out_path, 'w', encoding='utf-8') as f:
                    f.write(zpl)

                success_count += 1

            except Exception as e:
                errors.append(f"{base_name}: {e}")

        progress.setValue(len(paths))

        # Summary
        msg = f"Batch processing complete.\n\n{success_count}/{len(paths)} images processed successfully.\nOutput: {output_dir}"
        if errors:
            msg += f"\n\nErrors ({len(errors)}):\n" + "\n".join(errors[:10])
            if len(errors) > 10:
                msg += f"\n... and {len(errors) - 10} more"

        QMessageBox.information(self, "Batch Processing", msg)

    def _show_about(self):
        QMessageBox.about(self, "About ZPL Visual Editor",
                         "ZPL Visual Editor v1.0\n\n"
                         "A visual editor for Zebra Programming Language (ZPL).\n\n"
                         "Features:\n"
                         "- Bidirectional sync between code and canvas\n"
                         "- Support for text, barcodes, QR codes, shapes\n"
                         "- Real-time preview with rulers\n"
                         "- Linter warnings\n"
                         "- Image analysis and ZPL from image\n"
                         "- Dark/Light themes\n"
                         "- Export to PNG/PDF")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_G and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self._snap_action.setChecked(not self._snap_action.isChecked())
            self._toggle_snap(self._snap_action.isChecked())
        elif event.key() == Qt.Key.Key_R and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self._parse_and_render(self._code_editor.toPlainText())
        elif event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_Left, Qt.Key.Key_Right):
            self._move_selected(event)
        else:
            super().keyPressEvent(event)

    def _move_selected(self, event):
        try:
            selected = [i for i in self._scene.selectedItems() if isinstance(i, BaseElement)]
            if not selected:
                return
            step = 10 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1
            dx, dy = 0, 0
            if event.key() == Qt.Key.Key_Up:
                dy = -step
            elif event.key() == Qt.Key.Key_Down:
                dy = step
            elif event.key() == Qt.Key.Key_Left:
                dx = -step
            elif event.key() == Qt.Key.Key_Right:
                dx = step
            for item in selected:
                item.dot_x = item.dot_x + dx
                item.dot_y = item.dot_y + dy
            self._on_canvas_changed()
        except Exception as e:
            print(f"[Move Error] {e}")
