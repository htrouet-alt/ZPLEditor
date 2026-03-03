ZEBRA_FONT_MAP = {
    "0": {"name": "Font 0 (Default)", "family": "Consolas", "default_h": 15, "default_w": 12, "monospace": True},
    "A": {"name": "Font A", "family": "Arial", "default_h": 9, "default_w": 5, "monospace": False},
    "B": {"name": "Font B", "family": "Arial", "default_h": 11, "default_w": 7, "monospace": False},
    "C": {"name": "Font C", "family": "Courier New", "default_h": 18, "default_w": 10, "monospace": True},
    "D": {"name": "Font D", "family": "Arial", "default_h": 18, "default_w": 10, "monospace": False},
    "E": {"name": "Font E", "family": "Arial", "default_h": 28, "default_w": 15, "monospace": False},
    "F": {"name": "Font F", "family": "Arial", "default_h": 26, "default_w": 13, "monospace": False},
    "G": {"name": "Font G", "family": "Arial Black", "default_h": 60, "default_w": 40, "monospace": False},
    "H": {"name": "Font H", "family": "Courier New", "default_h": 21, "default_w": 13, "monospace": True},
    "1": {"name": "Font 1", "family": "Arial", "default_h": 9, "default_w": 5, "monospace": False},
    "2": {"name": "Font 2", "family": "Arial", "default_h": 11, "default_w": 7, "monospace": False},
    "3": {"name": "Font 3", "family": "Courier New", "default_h": 18, "default_w": 10, "monospace": True},
    "4": {"name": "Font 4", "family": "Arial", "default_h": 18, "default_w": 10, "monospace": False},
    "5": {"name": "Font 5", "family": "Arial", "default_h": 28, "default_w": 15, "monospace": False},
    "6": {"name": "Font 6", "family": "Courier New", "default_h": 26, "default_w": 13, "monospace": True},
    "7": {"name": "Font 7", "family": "Arial Black", "default_h": 60, "default_w": 40, "monospace": False},
    "8": {"name": "Font 8", "family": "Courier New", "default_h": 21, "default_w": 13, "monospace": True},
    "9": {"name": "Font 9", "family": "Arial", "default_h": 15, "default_w": 12, "monospace": False},
}

# Common system fonts for ZPL TrueType support (^A@ command)
COMMON_SYSTEM_FONTS = [
    "Arial",
    "Arial Black",
    "Arial Narrow",
    "Calibri",
    "Cambria",
    "Candara",
    "Comic Sans MS",
    "Consolas",
    "Constantia",
    "Corbel",
    "Courier New",
    "Georgia",
    "Impact",
    "Lucida Console",
    "Lucida Sans Unicode",
    "Microsoft Sans Serif",
    "Palatino Linotype",
    "Segoe UI",
    "Segoe UI Semibold",
    "Tahoma",
    "Times New Roman",
    "Trebuchet MS",
    "Verdana",
]

_cached_system_fonts = None


def get_system_fonts() -> list:
    """Get list of available system font families."""
    global _cached_system_fonts
    if _cached_system_fonts is not None:
        return _cached_system_fonts
    try:
        from PyQt6.QtGui import QFontDatabase
        families = sorted(set(QFontDatabase.families()))
        _cached_system_fonts = [f for f in families if not f.startswith('@')]
        return _cached_system_fonts
    except Exception:
        _cached_system_fonts = COMMON_SYSTEM_FONTS
        return _cached_system_fonts


def get_font_family(font_id: str, font_name: str = "") -> str:
    if font_id == "@" and font_name:
        return font_name
    info = ZEBRA_FONT_MAP.get(font_id.upper(), ZEBRA_FONT_MAP["0"])
    return info["family"]


def get_font_default_size(font_id: str):
    info = ZEBRA_FONT_MAP.get(font_id.upper(), ZEBRA_FONT_MAP["0"])
    return info["default_h"], info["default_w"]
