from PyQt6.QtGui import QFont
from .zebra_fonts import ZEBRA_FONT_MAP, get_font_family


def zpl_font_to_qfont(font_id: str, height: int, width: int = 0, font_name: str = "") -> QFont:
    # ZPL height = full character cell height in dots (1 dot = 1 pixel in our canvas)
    if font_id == "@" and font_name:
        # TrueType font - use height directly as pixel size
        font = QFont(font_name)
        pixel_size = max(8, height)
        font.setPixelSize(pixel_size)
        font.setStyleStrategy(QFont.StyleStrategy.NoAntialias)
        if width and width != height:
            font.setStretch(max(50, min(200, int(width / max(1, height) * 100))))
        return font

    info = ZEBRA_FONT_MAP.get(font_id.upper(), ZEBRA_FONT_MAP["0"])
    font = QFont(info["family"])
    # ZPL font height = full character cell height in dots (1 dot = 1 pixel).
    # Map directly without scaling.
    pixel_size = max(8, int(height))
    font.setPixelSize(pixel_size)
    font.setStyleStrategy(QFont.StyleStrategy.NoAntialias)
    # Zebra bitmap fonts render heavier glyphs than Consolas regular weight;
    # DemiBold better matches the original ink density.
    font.setWeight(QFont.Weight.DemiBold)
    if info["monospace"]:
        font.setStyleHint(QFont.StyleHint.Monospace)
    if width and width != height:
        font.setStretch(max(50, min(200, int(width / max(1, height) * 100))))
    return font
