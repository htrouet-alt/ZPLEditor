from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ZPLElement:
    element_type: str = ""
    x: int = 0
    y: int = 0
    use_ft: bool = False
    properties: dict = field(default_factory=dict)


@dataclass
class LabelSettings:
    width: int = 812
    height: int = 1218
    dpi: int = 203
    default_font: str = "0"
    default_font_height: int = 30
    default_font_width: int = 0
    charset: int = 28
    home_x: int = 0
    home_y: int = 0
    barcode_module_width: int = 2
    barcode_ratio: float = 3.0
    barcode_height: int = 10


DEFAULT_FONT_SIZES = {
    "0": (15, 12),
    "A": (9, 5), "B": (11, 7), "C": (18, 10), "D": (18, 10),
    "E": (28, 15), "F": (26, 13), "G": (60, 40), "H": (21, 13),
}
