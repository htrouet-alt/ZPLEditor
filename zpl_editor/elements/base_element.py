from PyQt6.QtWidgets import QGraphicsItem, QGraphicsRectItem, QStyleOptionGraphicsItem, QWidget, QMenu
from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal, QObject
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QCursor
from typing import Optional, List


class ElementSignals(QObject):
    position_changed = pyqtSignal(object)
    size_changed = pyqtSignal(object)
    property_changed = pyqtSignal(object, str, object)
    selected_changed = pyqtSignal(object, bool)


HANDLE_SIZE = 8
HANDLE_HALF = HANDLE_SIZE / 2


class ResizeHandle:
    TOP_LEFT = 0
    TOP = 1
    TOP_RIGHT = 2
    RIGHT = 3
    BOTTOM_RIGHT = 4
    BOTTOM = 5
    BOTTOM_LEFT = 6
    LEFT = 7


class BaseElement(QGraphicsItem):
    def __init__(self, x: int = 0, y: int = 0, parent=None):
        super().__init__(parent)
        self.signals = ElementSignals()
        self._element_type = ""
        self._dot_x = x
        self._dot_y = y
        self._dot_width = 100
        self._dot_height = 50
        self._properties = {}
        self._resizing = False
        self._resize_handle = -1
        self._resize_start_rect = QRectF()
        self._resize_start_pos = QPointF()
        self._hover = False
        self._snap_to_grid = False
        self._grid_size = 10
        self._min_size = 5

        self.setPos(x, y)
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)

    @property
    def element_type(self) -> str:
        return self._element_type

    @property
    def dot_x(self) -> int:
        return self._dot_x

    @dot_x.setter
    def dot_x(self, value: int):
        self._dot_x = int(value)
        self.setPos(self._dot_x, self._dot_y)

    @property
    def dot_y(self) -> int:
        return self._dot_y

    @dot_y.setter
    def dot_y(self, value: int):
        self._dot_y = int(value)
        self.setPos(self._dot_x, self._dot_y)

    @property
    def dot_width(self) -> int:
        return self._dot_width

    @dot_width.setter
    def dot_width(self, value: int):
        self._dot_width = max(self._min_size, int(value))
        self.prepareGeometryChange()

    @property
    def dot_height(self) -> int:
        return self._dot_height

    @dot_height.setter
    def dot_height(self, value: int):
        self._dot_height = max(self._min_size, int(value))
        self.prepareGeometryChange()

    def set_snap_to_grid(self, enabled: bool, grid_size: int = 10):
        self._snap_to_grid = enabled
        self._grid_size = grid_size

    def snap_value(self, value: float) -> int:
        if self._snap_to_grid:
            return round(value / self._grid_size) * self._grid_size
        return int(round(value))

    def get_zpl_element(self):
        from ..core.zpl_commands import ZPLElement
        elem = ZPLElement()
        elem.element_type = self._element_type
        elem.x = self._dot_x
        elem.y = self._dot_y
        elem.properties = dict(self._properties)
        return elem

    def update_from_zpl(self, zpl_elem):
        self._dot_x = zpl_elem.x
        self._dot_y = zpl_elem.y
        self._properties = dict(zpl_elem.properties)
        self.setPos(self._dot_x, self._dot_y)
        self._update_size_from_properties()
        self.update()

    def _update_size_from_properties(self):
        pass

    def boundingRect(self) -> QRectF:
        margin = HANDLE_HALF + 2
        return QRectF(-margin, -margin,
                       self._dot_width + margin * 2,
                       self._dot_height + margin * 2)

    def content_rect(self) -> QRectF:
        return QRectF(0, 0, self._dot_width, self._dot_height)

    def shape(self):
        from PyQt6.QtGui import QPainterPath
        path = QPainterPath()
        path.addRect(self.content_rect())
        return path

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget] = None):
        self._draw_content(painter)

        if self._hover and not self.isSelected():
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(0, 122, 204, 30)))
            painter.drawRect(self.content_rect())

        if self.isSelected():
            pen = QPen(QColor(0, 122, 204), 1.5, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(self.content_rect())
            self._draw_handles(painter)

    def _draw_content(self, painter: QPainter):
        pass

    def _draw_handles(self, painter: QPainter):
        painter.setPen(QPen(QColor(0, 122, 204), 1))
        painter.setBrush(QBrush(QColor(0, 122, 204)))
        for i in range(8):
            rect = self._handle_rect(i)
            painter.drawRect(rect)

    def _handle_rect(self, index: int) -> QRectF:
        r = self.content_rect()
        cx, cy = r.center().x(), r.center().y()
        positions = [
            (r.left(), r.top()),
            (cx, r.top()),
            (r.right(), r.top()),
            (r.right(), cy),
            (r.right(), r.bottom()),
            (cx, r.bottom()),
            (r.left(), r.bottom()),
            (r.left(), cy),
        ]
        px, py = positions[index]
        return QRectF(px - HANDLE_HALF, py - HANDLE_HALF, HANDLE_SIZE, HANDLE_SIZE)

    def _handle_at(self, pos: QPointF) -> int:
        if not self.isSelected():
            return -1
        for i in range(8):
            if self._handle_rect(i).contains(pos):
                return i
        return -1

    def _cursor_for_handle(self, handle: int) -> QCursor:
        cursors = {
            ResizeHandle.TOP_LEFT: Qt.CursorShape.SizeFDiagCursor,
            ResizeHandle.TOP: Qt.CursorShape.SizeVerCursor,
            ResizeHandle.TOP_RIGHT: Qt.CursorShape.SizeBDiagCursor,
            ResizeHandle.RIGHT: Qt.CursorShape.SizeHorCursor,
            ResizeHandle.BOTTOM_RIGHT: Qt.CursorShape.SizeFDiagCursor,
            ResizeHandle.BOTTOM: Qt.CursorShape.SizeVerCursor,
            ResizeHandle.BOTTOM_LEFT: Qt.CursorShape.SizeBDiagCursor,
            ResizeHandle.LEFT: Qt.CursorShape.SizeHorCursor,
        }
        return QCursor(cursors.get(handle, Qt.CursorShape.ArrowCursor))

    def hoverMoveEvent(self, event):
        handle = self._handle_at(event.pos())
        if handle >= 0:
            self.setCursor(self._cursor_for_handle(handle))
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        self._hover = True
        self.update()
        super().hoverMoveEvent(event)

    def hoverEnterEvent(self, event):
        self._hover = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self._hover = False
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.update()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self._handle_at(event.pos())
            if handle >= 0:
                self._resizing = True
                self._resize_handle = handle
                self._resize_start_rect = self.content_rect()
                self._resize_start_pos = event.scenePos()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._resizing:
            delta = event.scenePos() - self._resize_start_pos
            self._apply_resize(delta)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._resizing:
            self._resizing = False
            self._resize_handle = -1
            self.signals.size_changed.emit(self)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _apply_resize(self, delta: QPointF):
        r = QRectF(self._resize_start_rect)
        h = self._resize_handle
        dx, dy = delta.x(), delta.y()

        new_x, new_y = self._dot_x, self._dot_y
        new_w, new_h = self._dot_width, self._dot_height
        start_x = int(self.pos().x() - (self.content_rect().width() - self._resize_start_rect.width()))

        if h in (ResizeHandle.TOP_LEFT, ResizeHandle.LEFT, ResizeHandle.BOTTOM_LEFT):
            new_w = max(self._min_size, int(r.width() - dx))
            new_x = self.snap_value(self._dot_x + int(dx)) if new_w > self._min_size else self._dot_x
        if h in (ResizeHandle.TOP_RIGHT, ResizeHandle.RIGHT, ResizeHandle.BOTTOM_RIGHT):
            new_w = max(self._min_size, int(r.width() + dx))
        if h in (ResizeHandle.TOP_LEFT, ResizeHandle.TOP, ResizeHandle.TOP_RIGHT):
            new_h = max(self._min_size, int(r.height() - dy))
            new_y = self.snap_value(self._dot_y + int(dy)) if new_h > self._min_size else self._dot_y
        if h in (ResizeHandle.BOTTOM_LEFT, ResizeHandle.BOTTOM, ResizeHandle.BOTTOM_RIGHT):
            new_h = max(self._min_size, int(r.height() + dy))

        self.prepareGeometryChange()
        self._dot_x = new_x
        self._dot_y = new_y
        self._dot_width = self.snap_value(new_w)
        self._dot_height = self.snap_value(new_h)
        self.setPos(self._dot_x, self._dot_y)
        self._sync_properties_from_size()
        self.update()

    def _sync_properties_from_size(self):
        pass

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            new_pos = value
            self._dot_x = self.snap_value(new_pos.x())
            self._dot_y = self.snap_value(new_pos.y())
            self.signals.position_changed.emit(self)
        elif change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            self.signals.selected_changed.emit(self, bool(value))
        return super().itemChange(change, value)

    def contextMenuEvent(self, event):
        menu = QMenu()
        menu.addAction("Cut\tCtrl+X")
        menu.addAction("Copy\tCtrl+C")
        menu.addAction("Paste\tCtrl+V")
        menu.addSeparator()
        menu.addAction("Clone\tCtrl+D")
        menu.addAction("Delete\tDel")
        menu.addSeparator()
        menu.addAction("Bring to Front")
        menu.addAction("Send to Back")

        action = menu.exec(event.screenPos())
        if action:
            text = action.text().split("\t")[0]
            scene = self.scene()
            if scene and hasattr(scene, "handle_context_action"):
                scene.handle_context_action(text, self)
