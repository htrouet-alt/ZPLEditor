class ZoomController:
    MIN_ZOOM = 0.1
    MAX_ZOOM = 30.0
    ZOOM_STEP = 1.25

    def __init__(self, initial_zoom: float = 1.0):
        self._zoom = initial_zoom

    @property
    def zoom(self) -> float:
        return self._zoom

    @zoom.setter
    def zoom(self, value: float):
        self._zoom = max(self.MIN_ZOOM, min(self.MAX_ZOOM, value))

    def zoom_in(self) -> float:
        self.zoom = self._zoom * self.ZOOM_STEP
        return self._zoom

    def zoom_out(self) -> float:
        self.zoom = self._zoom / self.ZOOM_STEP
        return self._zoom

    def zoom_percent(self) -> int:
        return int(self._zoom * 100)
