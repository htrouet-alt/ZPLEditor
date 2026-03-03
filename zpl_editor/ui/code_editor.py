from PyQt6.QtWidgets import QPlainTextEdit, QWidget, QTextEdit
from PyQt6.QtCore import Qt, QRect, QSize, pyqtSignal, QTimer
from PyQt6.QtGui import (QColor, QTextFormat, QPainter, QFont,
                          QSyntaxHighlighter, QTextCharFormat, QTextDocument)
import re


class ZPLHighlighter(QSyntaxHighlighter):
    def __init__(self, document: QTextDocument):
        super().__init__(document)
        self._rules = []

        fmt_label = QTextCharFormat()
        fmt_label.setForeground(QColor(86, 156, 214))
        fmt_label.setFontWeight(QFont.Weight.Bold)
        self._rules.append((re.compile(r'\^XA|\^XZ'), fmt_label))

        fmt_fo = QTextCharFormat()
        fmt_fo.setForeground(QColor(78, 201, 176))
        self._rules.append((re.compile(r'\^FO\d*,?\d*|\^FT\d*,?\d*'), fmt_fo))

        fmt_fd = QTextCharFormat()
        fmt_fd.setForeground(QColor(206, 145, 120))
        self._rules.append((re.compile(r'\^FD[^^]*'), fmt_fd))

        fmt_font = QTextCharFormat()
        fmt_font.setForeground(QColor(197, 134, 192))
        self._rules.append((re.compile(r'\^A@[^^]*|\^A[0-9A-Za-z][NRIB]?,?\d*,?\d*|\^CF[^^]*'), fmt_font))

        fmt_barcode = QTextCharFormat()
        fmt_barcode.setForeground(QColor(244, 71, 71))
        self._rules.append((re.compile(
            r'\^B[0-9A-Za-z][^^]*|\^BY[^^]*'
        ), fmt_barcode))

        fmt_graphic = QTextCharFormat()
        fmt_graphic.setForeground(QColor(79, 193, 233))
        self._rules.append((re.compile(r'\^GB[^^]*|\^GC[^^]*|\^GD[^^]*|\^GFA[^^]*'), fmt_graphic))

        fmt_setting = QTextCharFormat()
        fmt_setting.setForeground(QColor(128, 128, 128))
        self._rules.append((re.compile(r'\^CI\d*|\^PQ[^^]*|\^PW\d*|\^LL\d*|\^LH[^^]*|\^FW[^^]*'), fmt_setting))

        fmt_fb = QTextCharFormat()
        fmt_fb.setForeground(QColor(220, 220, 170))
        self._rules.append((re.compile(r'\^FB[^^]*'), fmt_fb))

        fmt_fs = QTextCharFormat()
        fmt_fs.setForeground(QColor(128, 128, 128))
        self._rules.append((re.compile(r'\^FS'), fmt_fs))

        fmt_comment = QTextCharFormat()
        fmt_comment.setForeground(QColor(106, 153, 85))
        fmt_comment.setFontItalic(True)
        self._rules.append((re.compile(r'\^FX[^^]*'), fmt_comment))

        fmt_number = QTextCharFormat()
        fmt_number.setForeground(QColor(181, 206, 168))
        self._rules.append((re.compile(r'(?<=,)\d+|\b\d+\b'), fmt_number))

    def highlightBlock(self, text: str):
        for pattern, fmt in self._rules:
            for match in pattern.finditer(text):
                start = match.start()
                length = match.end() - start
                self.setFormat(start, length, fmt)


class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self) -> QSize:
        return QSize(self._editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self._editor.line_number_area_paint_event(event)


class CodeEditor(QPlainTextEdit):
    code_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._line_number_area = LineNumberArea(self)
        self._highlighter = ZPLHighlighter(self.document())
        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(500)
        self._debounce_timer.timeout.connect(self._emit_code_changed)
        self._syncing = False

        font = QFont("Consolas", 11)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)
        self.setTabStopDistance(40)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        self.blockCountChanged.connect(self._update_line_number_width)
        self.updateRequest.connect(self._update_line_number_area)
        self.cursorPositionChanged.connect(self._highlight_current_line)
        self.textChanged.connect(self._on_text_changed)

        self._update_line_number_width(0)
        self._highlight_current_line()

        self.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1E1E1E;
                color: #D4D4D4;
                selection-background-color: #264F78;
                selection-color: #FFFFFF;
                border: none;
            }
        """)

    def set_syncing(self, syncing: bool):
        self._syncing = syncing

    def set_code(self, code: str):
        self._syncing = True
        cursor_pos = self.textCursor().position()
        self.setPlainText(code)
        cursor = self.textCursor()
        cursor.setPosition(min(cursor_pos, len(code)))
        self.setTextCursor(cursor)
        self._syncing = False

    def _on_text_changed(self):
        if not self._syncing:
            self._debounce_timer.start()

    def _emit_code_changed(self):
        if not self._syncing:
            self.code_changed.emit(self.toPlainText())

    def line_number_area_width(self) -> int:
        digits = max(1, len(str(self.blockCount())))
        return 10 + self.fontMetrics().horizontalAdvance("9") * digits

    def _update_line_number_width(self, _):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def _update_line_number_area(self, rect, dy):
        if dy:
            self._line_number_area.scroll(0, dy)
        else:
            self._line_number_area.update(0, rect.y(),
                                           self._line_number_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_line_number_width(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._line_number_area.setGeometry(
            QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height()))

    def _highlight_current_line(self):
        selections = []
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            line_color = QColor(40, 40, 40)
            selection.format.setBackground(line_color)
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            selections.append(selection)
        self.setExtraSelections(selections)

    def line_number_area_paint_event(self, event):
        painter = QPainter(self._line_number_area)
        painter.fillRect(event.rect(), QColor(30, 30, 30))
        painter.setPen(QColor(100, 100, 100))
        painter.setFont(self.font())

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.drawText(0, top,
                                self._line_number_area.width() - 5,
                                self.fontMetrics().height(),
                                Qt.AlignmentFlag.AlignRight, number)
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_number += 1

        painter.end()
