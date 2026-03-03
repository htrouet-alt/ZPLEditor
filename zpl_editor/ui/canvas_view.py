from PyQt6.QtWidgets import QGraphicsView, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout
from PyQt6.QtCore import Qt, pyqtSignal, QPointF, QTimer
from PyQt6.QtGui import QPainter, QWheelEvent, QMouseEvent, QKeyEvent
from .canvas_scene import CanvasScene
from ..graphics.ruler import Ruler, RulerCorner


class CanvasViewWidget(QWidget):
    """Container widget that wraps a CanvasView with horizontal and vertical rulers."""

    def __init__(self, scene: CanvasScene, parent=None):
        super().__init__(parent)
        self._scene = scene

        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(0)

        self._corner = RulerCorner()
        self._h_ruler = Ruler(Ruler.HORIZONTAL)
        self._v_ruler = Ruler(Ruler.VERTICAL)
        self._canvas_view = CanvasView(scene)

        grid.addWidget(self._corner, 0, 0)
        grid.addWidget(self._h_ruler, 0, 1)
        grid.addWidget(self._v_ruler, 1, 0)
        grid.addWidget(self._canvas_view, 1, 1)

        self._rulers_visible = True

        self._canvas_view.zoom_changed.connect(self._update_rulers)
        self._canvas_view.mouse_position_changed.connect(self._on_mouse_moved)
        self._canvas_view.scrolled.connect(self._update_rulers)

        self._ruler_timer = QTimer()
        self._ruler_timer.setInterval(50)
        self._ruler_timer.timeout.connect(self._update_rulers)
        self._ruler_timer.start()

    @property
    def canvas_view(self) -> 'CanvasView':
        return self._canvas_view

    def set_rulers_visible(self, visible: bool):
        self._rulers_visible = visible
        self._corner.setVisible(visible)
        self._h_ruler.setVisible(visible)
        self._v_ruler.setVisible(visible)

    def _on_mouse_moved(self, sx, sy):
        self._h_ruler.set_mouse_position(sx)
        self._v_ruler.set_mouse_position(sy)

    def _update_rulers(self):
        view = self._canvas_view
        zoom = view.zoom_level()
        top_left = view.mapToScene(0, 0)
        self._h_ruler.set_params(zoom, top_left.x(), 203)
        self._v_ruler.set_params(zoom, top_left.y(), 203)


class CanvasView(QGraphicsView):
    zoom_changed = pyqtSignal(float)
    mouse_position_changed = pyqtSignal(float, float)
    scrolled = pyqtSignal()

    MIN_ZOOM = 0.1
    MAX_ZOOM = 30.0

    def __init__(self, scene: CanvasScene, parent: QWidget = None):
        super().__init__(scene, parent)
        self._scene = scene
        self._zoom_factor = 1.0
        self._panning = False
        self._pan_start = QPointF()
        self._space_pressed = False

        self.setRenderHints(
            QPainter.RenderHint.Antialiasing |
            QPainter.RenderHint.SmoothPixmapTransform |
            QPainter.RenderHint.TextAntialiasing
        )
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.SmartViewportUpdate)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        from PyQt6.QtGui import QColor
        self.setBackgroundBrush(QColor(240, 240, 240))

        self.horizontalScrollBar().valueChanged.connect(lambda: self.scrolled.emit())
        self.verticalScrollBar().valueChanged.connect(lambda: self.scrolled.emit())

    def zoom_level(self) -> float:
        return self._zoom_factor

    def set_zoom(self, factor: float):
        factor = max(self.MIN_ZOOM, min(self.MAX_ZOOM, factor))
        scale = factor / self._zoom_factor
        self._zoom_factor = factor
        self.scale(scale, scale)
        self.zoom_changed.emit(self._zoom_factor)

    def zoom_in(self):
        self.set_zoom(self._zoom_factor * 1.25)

    def zoom_out(self):
        self.set_zoom(self._zoom_factor / 1.25)

    def fit_in_view(self):
        label_rect = self._scene.sceneRect()
        self.fitInView(label_rect, Qt.AspectRatioMode.KeepAspectRatio)
        transform = self.transform()
        self._zoom_factor = transform.m11()
        self.zoom_changed.emit(self._zoom_factor)

    def wheelEvent(self, event: QWheelEvent):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom_in()
            elif delta < 0:
                self.zoom_out()
            event.accept()
        else:
            super().wheelEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_pressed = True
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_pressed = False
            self._panning = False
            self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return
        super().keyReleaseEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        if self._space_pressed and event.button() == Qt.MouseButton.LeftButton:
            self._panning = True
            self._pan_start = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = True
            self._pan_start = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        scene_pos = self.mapToScene(event.position().toPoint())
        self.mouse_position_changed.emit(scene_pos.x(), scene_pos.y())

        if self._panning:
            delta = event.position() - self._pan_start
            self._pan_start = event.position()
            self.horizontalScrollBar().setValue(
                int(self.horizontalScrollBar().value() - delta.x()))
            self.verticalScrollBar().setValue(
                int(self.verticalScrollBar().value() - delta.y()))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self._panning:
            self._panning = False
            if self._space_pressed:
                self.setCursor(Qt.CursorShape.OpenHandCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)
