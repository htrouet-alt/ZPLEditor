class CoordinateSystem:
    DPI_VALUES = {203: 203, 300: 300, 600: 600}
    MM_PER_INCH = 25.4

    def __init__(self, dpi: int = 203):
        self.dpi = dpi

    def dots_to_mm(self, dots: float) -> float:
        return dots * self.MM_PER_INCH / self.dpi

    def mm_to_dots(self, mm: float) -> float:
        return mm * self.dpi / self.MM_PER_INCH

    def dots_to_inch(self, dots: float) -> float:
        return dots / self.dpi

    def inch_to_dots(self, inch: float) -> float:
        return inch * self.dpi

    def dots_per_mm(self) -> float:
        return self.dpi / self.MM_PER_INCH
