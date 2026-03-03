import re
from typing import List, Optional, Tuple
from .label_model import LabelModel
from .zpl_commands import ZPLElement, LabelSettings

KNOWN_COMMANDS = [
    "GFA",
    "XA", "XZ", "FO", "FD", "FS", "FT", "FW", "FX", "FB", "FH",
    "CF", "CI", "PW", "LL", "LH", "PQ", "BY",
    "PO", "PM", "PR", "MD", "MN", "MC", "MM", "MT",
    "SN", "SE",
    # 1D Barcodes
    "B1", "B2", "B3", "B5", "B8", "B9",
    "BA", "BC", "BE", "BI", "BJ", "BK", "BL", "BM",
    "BP", "BR", "BS", "BU", "BZ",
    # 2D Barcodes
    "B4", "B7", "BB", "BD", "BF", "BO", "BQ", "BX",
    # Graphics
    "GB", "GC", "GD",
]

# Maps ZPL ^B* command to internal barcode_type name
BARCODE_CMD_TO_TYPE = {
    "B1": "code11",
    "B2": "i2of5",
    "B3": "code39",
    "B4": "code49",
    "B5": "planet",
    "B7": "pdf417",
    "B8": "ean8",
    "B9": "upce",
    "BA": "code93",
    "BB": "codablockf",
    "BC": "code128",
    "BD": "maxicode",
    "BE": "ean13",
    "BF": "micropdf417",
    "BI": "industrial2of5",
    "BJ": "standard2of5",
    "BK": "codabar",
    "BL": "logmars",
    "BM": "msi",
    "BO": "aztec",
    "BP": "plessey",
    "BR": "gs1databar",
    "BS": "upcean_ext",
    "BU": "upca",
    "BX": "datamatrix",
    "BZ": "postnet",
}

# Reverse mapping: barcode_type -> ZPL command code
BARCODE_TYPE_TO_CMD = {v: k for k, v in BARCODE_CMD_TO_TYPE.items()}

# Parameter order for 1D barcode commands
BARCODE_1D_PARAM_ORDER = {
    "B1": ["orientation", "checkdigit", "height", "interpretation", "above"],
    "B2": ["orientation", "height", "interpretation", "above", "checkdigit"],
    "B3": ["orientation", "checkdigit", "height", "interpretation", "above"],
    "B5": ["orientation", "height", "interpretation", "above"],
    "B8": ["orientation", "height", "interpretation", "above"],
    "B9": ["orientation", "height", "interpretation", "above", "checkdigit"],
    "BA": ["orientation", "height", "interpretation", "above", "checkdigit"],
    "BC": ["orientation", "height", "interpretation", "above", "checkdigit", "mode"],
    "BE": ["orientation", "height", "interpretation", "above"],
    "BI": ["orientation", "height", "interpretation", "above"],
    "BJ": ["orientation", "height", "interpretation", "above"],
    "BK": ["orientation", "checkdigit", "height", "interpretation", "above", "start_char", "stop_char"],
    "BL": ["orientation", "height", "interpretation", "above"],
    "BM": ["orientation", "checkdigit", "height", "interpretation", "above", "check_type"],
    "BP": ["orientation", "checkdigit", "height", "interpretation"],
    "BR": ["orientation", "symbology_type", "magnification", "separator_height", "max_height", "segment_width"],
    "BS": ["orientation", "height", "interpretation", "above"],
    "BU": ["orientation", "height", "interpretation", "above", "checkdigit"],
    "BZ": ["orientation", "height", "interpretation", "above"],
}

# 2D barcode commands (need special parsing)
BARCODE_2D_COMMANDS = {"B4", "B7", "BB", "BD", "BF", "BO", "BX"}


class ZPLParser:
    def __init__(self):
        self._errors: List[Tuple[int, str]] = []

    @property
    def errors(self):
        return self._errors

    def parse(self, zpl_code: str) -> LabelModel:
        self._errors = []
        model = LabelModel()

        zpl_code = self._strip_comments(zpl_code)

        body = self._extract_body(zpl_code)
        if body is None:
            body = zpl_code

        commands = self._split_commands(body)
        self._process_commands(commands, model)
        return model

    @staticmethod
    def _strip_comments(zpl_code: str) -> str:
        """Remove lines starting with # (comment lines) from ZPL code."""
        lines = zpl_code.split('\n')
        filtered = [line for line in lines if not line.strip().startswith('#')]
        return '\n'.join(filtered)

    def _extract_body(self, zpl_code: str) -> Optional[str]:
        match = re.search(r'\^XA(.*?)\^XZ', zpl_code, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    def _split_commands(self, body: str) -> List[Tuple[str, str]]:
        commands = []
        i = 0
        while i < len(body):
            if body[i] == '^':
                i += 1
                cmd_code, cmd_len = self._identify_command(body, i)
                if cmd_code:
                    i += cmd_len
                    param_end = body.find('^', i)
                    if param_end == -1:
                        param_end = len(body)
                    params = body[i:param_end].strip()
                    commands.append((cmd_code, params))
                    i = param_end
                else:
                    i += 1
            else:
                i += 1
        return commands

    def _identify_command(self, body: str, pos: int) -> Tuple[str, int]:
        remaining = body[pos:]
        upper_remaining = remaining.upper()

        for cmd in KNOWN_COMMANDS:
            if upper_remaining.startswith(cmd):
                return cmd, len(cmd)

        # Handle ^A@ (TrueType font)
        if len(remaining) >= 2 and remaining[0].upper() == 'A' and remaining[1] == '@':
            return "A@", 2

        # Handle ^A<font_id> (built-in font)
        if remaining and remaining[0].upper() == 'A':
            return "A", 1

        return "", 0

    def _parse_params(self, param_str: str) -> List[str]:
        if not param_str:
            return []
        params = param_str.split(',')
        return [p.strip() for p in params]

    def _safe_int(self, value: str, default: int = 0) -> int:
        if not value:
            return default
        try:
            return int(value)
        except ValueError:
            return default

    def _safe_float(self, value: str, default: float = 0.0) -> float:
        if not value:
            return default
        try:
            return float(value)
        except ValueError:
            return default

    @staticmethod
    def _decode_hex_field(data: str) -> str:
        """Decode ^FH hex escapes: _XX patterns become the corresponding character."""
        result = []
        i = 0
        while i < len(data):
            if data[i] == '_' and i + 2 < len(data):
                hex_chars = data[i+1:i+3]
                try:
                    result.append(chr(int(hex_chars, 16)))
                    i += 3
                    continue
                except ValueError:
                    pass
            result.append(data[i])
            i += 1
        return ''.join(result)

    def _process_commands(self, commands: List[Tuple[str, str]], model: LabelModel):
        current_element: Optional[ZPLElement] = None
        settings = model.settings

        barcode_module_width = settings.barcode_module_width
        barcode_ratio = settings.barcode_ratio
        barcode_height = settings.barcode_height

        for cmd_code, param_str in commands:

            if cmd_code in ("XA", "XZ", "FX"):
                continue

            elif cmd_code == "PW":
                settings.width = self._safe_int(param_str, settings.width)

            elif cmd_code == "LL":
                params = self._parse_params(param_str)
                settings.height = self._safe_int(params[0] if params else "", settings.height)

            elif cmd_code == "LH":
                params = self._parse_params(param_str)
                settings.home_x = self._safe_int(params[0] if params else "", 0)
                settings.home_y = self._safe_int(params[1] if len(params) > 1 else "", 0)

            elif cmd_code == "CF":
                params = self._parse_params(param_str)
                if params:
                    settings.default_font = params[0] if params[0] else settings.default_font
                if len(params) > 1:
                    settings.default_font_height = self._safe_int(params[1], settings.default_font_height)
                if len(params) > 2:
                    settings.default_font_width = self._safe_int(params[2], settings.default_font_width)

            elif cmd_code == "CI":
                settings.charset = self._safe_int(param_str, settings.charset)

            elif cmd_code == "BY":
                params = self._parse_params(param_str)
                if params and params[0]:
                    barcode_module_width = self._safe_int(params[0], barcode_module_width)
                if len(params) > 1 and params[1]:
                    barcode_ratio = self._safe_float(params[1], barcode_ratio)
                if len(params) > 2 and params[2]:
                    barcode_height = self._safe_int(params[2], barcode_height)
                if current_element:
                    current_element.properties["module_width"] = barcode_module_width
                    current_element.properties["ratio"] = barcode_ratio
                    current_element.properties["bar_height"] = barcode_height

            elif cmd_code == "FH":
                # Field Hexadecimal Indicator - mark current element for hex decoding
                if current_element is not None:
                    current_element.properties["_hex_indicator"] = True

            elif cmd_code == "FW":
                pass

            elif cmd_code in ("PO", "PM", "PR", "MD", "MN", "MC", "MM", "MT", "SN", "SE"):
                # Known commands that don't affect rendering - silently skip
                pass

            elif cmd_code == "FO":
                if current_element and current_element.element_type:
                    model.add_element(current_element)
                current_element = ZPLElement()
                params = self._parse_params(param_str)
                current_element.x = self._safe_int(params[0] if params else "", 0)
                current_element.y = self._safe_int(params[1] if len(params) > 1 else "", 0)
                current_element.use_ft = False

            elif cmd_code == "FT":
                if current_element and current_element.element_type:
                    model.add_element(current_element)
                current_element = ZPLElement()
                params = self._parse_params(param_str)
                current_element.x = self._safe_int(params[0] if params else "", 0)
                current_element.y = self._safe_int(params[1] if len(params) > 1 else "", 0)
                current_element.use_ft = True

            elif cmd_code == "A":
                if current_element is None:
                    continue
                font_id, orientation, height, width = self._parse_font(param_str, settings)
                current_element.properties["font"] = font_id
                current_element.properties["orientation"] = orientation
                current_element.properties["font_height"] = height
                current_element.properties["font_width"] = width
                current_element.element_type = "text"

            elif cmd_code == "A@":
                if current_element is None:
                    continue
                orientation, height, width, font_name = self._parse_truetype_font(param_str, settings)
                current_element.properties["font"] = "@"
                current_element.properties["font_name"] = font_name
                current_element.properties["orientation"] = orientation
                current_element.properties["font_height"] = height
                current_element.properties["font_width"] = width
                current_element.element_type = "text"

            elif cmd_code == "FD":
                if current_element is None:
                    continue
                data = param_str
                # Decode hex escapes if ^FH was used
                if current_element.properties.get("_hex_indicator"):
                    data = self._decode_hex_field(data)
                    del current_element.properties["_hex_indicator"]
                current_element.properties["data"] = data
                if not current_element.element_type:
                    current_element.element_type = "text"

            elif cmd_code == "FB":
                if current_element is None:
                    continue
                params = self._parse_params(param_str)
                current_element.properties["fb_width"] = self._safe_int(params[0] if params else "", 0)
                current_element.properties["fb_max_lines"] = self._safe_int(params[1] if len(params) > 1 else "", 1)
                current_element.properties["fb_line_spacing"] = self._safe_int(params[2] if len(params) > 2 else "", 0)
                current_element.properties["fb_alignment"] = params[3] if len(params) > 3 and params[3] else "L"
                current_element.properties["fb_hanging"] = self._safe_int(params[4] if len(params) > 4 else "", 0)

            elif cmd_code == "GB":
                if current_element is None:
                    continue
                params = self._parse_params(param_str)
                w = self._safe_int(params[0] if params else "", 0)
                h = self._safe_int(params[1] if len(params) > 1 else "", 0)
                thickness = self._safe_int(params[2] if len(params) > 2 else "", 1)
                color = params[3].upper() if len(params) > 3 and params[3] else "B"
                rounding = self._safe_int(params[4] if len(params) > 4 else "", 0)

                current_element.element_type = "box"
                current_element.properties["width"] = w
                current_element.properties["height"] = h
                current_element.properties["thickness"] = thickness
                current_element.properties["color"] = color
                current_element.properties["rounding"] = rounding

            elif cmd_code == "GC":
                if current_element is None:
                    continue
                params = self._parse_params(param_str)
                diameter = self._safe_int(params[0] if params else "", 0)
                thickness = self._safe_int(params[1] if len(params) > 1 else "", 1)
                color = params[2].upper() if len(params) > 2 and params[2] else "B"

                current_element.element_type = "circle"
                current_element.properties["diameter"] = diameter
                current_element.properties["thickness"] = thickness
                current_element.properties["color"] = color

            elif cmd_code == "GD":
                if current_element is None:
                    continue
                params = self._parse_params(param_str)
                w = self._safe_int(params[0] if params else "", 0)
                h = self._safe_int(params[1] if len(params) > 1 else "", 0)
                thickness = self._safe_int(params[2] if len(params) > 2 else "", 1)
                color = params[3].upper() if len(params) > 3 and params[3] else "B"
                orientation = params[4].upper() if len(params) > 4 and params[4] else "R"

                current_element.element_type = "diagonal"
                current_element.properties["width"] = w
                current_element.properties["height"] = h
                current_element.properties["thickness"] = thickness
                current_element.properties["color"] = color
                current_element.properties["orientation"] = orientation

            # --- 1D Barcode commands ---
            elif cmd_code in BARCODE_1D_PARAM_ORDER:
                if current_element is None:
                    continue
                self._parse_1d_barcode(cmd_code, param_str, current_element,
                                       barcode_height, barcode_module_width, barcode_ratio)

            # --- 2D Barcode commands ---
            elif cmd_code in BARCODE_2D_COMMANDS:
                if current_element is None:
                    continue
                self._parse_2d_barcode(cmd_code, param_str, current_element,
                                       barcode_height, barcode_module_width, barcode_ratio)

            elif cmd_code == "BQ":
                if current_element is None:
                    continue
                params = self._parse_params(param_str)
                orientation = params[0].upper() if params and params[0] else "N"
                qr_model = self._safe_int(params[1] if len(params) > 1 else "", 2)
                magnification = self._safe_int(params[2] if len(params) > 2 else "", 3)
                error_correction = params[3].upper() if len(params) > 3 and params[3] else "M"

                current_element.element_type = "qrcode"
                current_element.properties["orientation"] = orientation
                current_element.properties["qr_model"] = qr_model
                current_element.properties["magnification"] = magnification
                current_element.properties["error_correction"] = error_correction

            elif cmd_code == "FS":
                if current_element and current_element.element_type:
                    # Apply current default font to text elements without explicit ^A
                    if current_element.element_type == "text":
                        current_element.properties.setdefault("font", settings.default_font)
                        current_element.properties.setdefault("font_height", settings.default_font_height)
                        current_element.properties.setdefault("font_width", settings.default_font_width)
                        current_element.properties.setdefault("orientation", "N")
                    model.add_element(current_element)
                    current_element = None
                elif current_element:
                    current_element = None

        if current_element and current_element.element_type:
            model.add_element(current_element)

    def _parse_1d_barcode(self, cmd_code, param_str, current_element,
                          barcode_height, barcode_module_width, barcode_ratio):
        params = self._parse_params(param_str)
        param_order = BARCODE_1D_PARAM_ORDER.get(cmd_code, [])
        barcode_type = BARCODE_CMD_TO_TYPE.get(cmd_code, "code128")

        current_element.element_type = "barcode"
        current_element.properties["barcode_type"] = barcode_type
        current_element.properties.setdefault("module_width", barcode_module_width)
        current_element.properties.setdefault("ratio", barcode_ratio)

        for i, param_name in enumerate(param_order):
            val = params[i] if i < len(params) and params[i] else ""
            if not val:
                continue
            if param_name == "orientation":
                current_element.properties["orientation"] = val.upper()
            elif param_name == "height":
                current_element.properties["bar_height"] = self._safe_int(val, barcode_height)
            elif param_name == "interpretation":
                current_element.properties["interpretation"] = val.upper()
            elif param_name == "above":
                current_element.properties["interpretation_above"] = val.upper()
            elif param_name == "checkdigit":
                current_element.properties["checkdigit"] = val.upper()
            else:
                current_element.properties[param_name] = val

        current_element.properties.setdefault("orientation", "N")
        current_element.properties.setdefault("bar_height", barcode_height)
        current_element.properties.setdefault("interpretation", "Y")
        current_element.properties.setdefault("interpretation_above", "N")

    def _parse_2d_barcode(self, cmd_code, param_str, current_element,
                          barcode_height, barcode_module_width, barcode_ratio):
        params = self._parse_params(param_str)
        barcode_type = BARCODE_CMD_TO_TYPE.get(cmd_code, "code128")

        current_element.element_type = "barcode"
        current_element.properties["barcode_type"] = barcode_type
        current_element.properties.setdefault("module_width", barcode_module_width)

        if cmd_code == "B7":  # PDF417
            current_element.properties["orientation"] = params[0].upper() if params and params[0] else "N"
            current_element.properties["bar_height"] = self._safe_int(params[1] if len(params) > 1 else "", barcode_height)
            current_element.properties["security_level"] = self._safe_int(params[2] if len(params) > 2 else "", 0)
            current_element.properties["columns"] = self._safe_int(params[3] if len(params) > 3 else "", 0)
            current_element.properties["rows"] = self._safe_int(params[4] if len(params) > 4 else "", 0)
            current_element.properties["truncate"] = params[5].upper() if len(params) > 5 and params[5] else "N"

        elif cmd_code == "BX":  # DataMatrix
            current_element.properties["orientation"] = params[0].upper() if params and params[0] else "N"
            current_element.properties["bar_height"] = self._safe_int(params[1] if len(params) > 1 else "", 10)
            current_element.properties["quality"] = self._safe_int(params[2] if len(params) > 2 else "", 200)
            current_element.properties["columns"] = self._safe_int(params[3] if len(params) > 3 else "", 0)
            current_element.properties["rows"] = self._safe_int(params[4] if len(params) > 4 else "", 0)

        elif cmd_code == "BO":  # Aztec
            current_element.properties["orientation"] = params[0].upper() if params and params[0] else "N"
            current_element.properties["magnification"] = self._safe_int(params[1] if len(params) > 1 else "", 3)
            current_element.properties["extended_channel"] = params[2].upper() if len(params) > 2 and params[2] else "N"
            current_element.properties["error_control"] = self._safe_int(params[3] if len(params) > 3 else "", 0)
            current_element.properties["menu_indicator"] = params[4].upper() if len(params) > 4 and params[4] else "N"

        elif cmd_code == "BD":  # MaxiCode
            current_element.properties["mode"] = self._safe_int(params[0] if params else "", 2)
            current_element.properties["symbol_number"] = self._safe_int(params[1] if len(params) > 1 else "", 1)
            current_element.properties["total_symbols"] = self._safe_int(params[2] if len(params) > 2 else "", 1)

        elif cmd_code == "B4":  # Code 49
            current_element.properties["orientation"] = params[0].upper() if params and params[0] else "N"
            current_element.properties["bar_height"] = self._safe_int(params[1] if len(params) > 1 else "", barcode_height)
            current_element.properties["interpretation"] = params[2].upper() if len(params) > 2 and params[2] else "N"
            current_element.properties["starting_mode"] = self._safe_int(params[3] if len(params) > 3 else "", 0)

        elif cmd_code == "BB":  # CODABLOCK-F
            current_element.properties["orientation"] = params[0].upper() if params and params[0] else "N"
            current_element.properties["bar_height"] = self._safe_int(params[1] if len(params) > 1 else "", barcode_height)
            current_element.properties["security_level"] = params[2].upper() if len(params) > 2 and params[2] else "N"
            current_element.properties["columns"] = self._safe_int(params[3] if len(params) > 3 else "", 8)
            current_element.properties["rows"] = self._safe_int(params[4] if len(params) > 4 else "", 0)
            current_element.properties["mode"] = params[5].upper() if len(params) > 5 and params[5] else "N"

        elif cmd_code == "BF":  # Micro-PDF417
            current_element.properties["orientation"] = params[0].upper() if params and params[0] else "N"
            current_element.properties["bar_height"] = self._safe_int(params[1] if len(params) > 1 else "", barcode_height)
            current_element.properties["mode"] = self._safe_int(params[2] if len(params) > 2 else "", 0)
            current_element.properties["columns"] = self._safe_int(params[3] if len(params) > 3 else "", 0)

        current_element.properties.setdefault("orientation", "N")
        current_element.properties.setdefault("bar_height", barcode_height)

    def _parse_font(self, param_str: str, settings: LabelSettings):
        font_id = settings.default_font
        orientation = "N"
        height = settings.default_font_height
        width = settings.default_font_width

        if not param_str:
            return font_id, orientation, height, width

        pos = 0
        if pos < len(param_str) and param_str[pos] not in (',',):
            font_id = param_str[pos]
            pos += 1

        if pos < len(param_str) and param_str[pos].upper() in ('N', 'R', 'I', 'B'):
            orientation = param_str[pos].upper()
            pos += 1

        if pos < len(param_str) and param_str[pos] == ',':
            pos += 1

        remaining = param_str[pos:]
        params = remaining.split(',') if remaining else []

        if params and params[0]:
            height = self._safe_int(params[0], height)
        if len(params) > 1 and params[1]:
            width = self._safe_int(params[1], width)

        return font_id, orientation, height, width

    def _parse_truetype_font(self, param_str: str, settings: LabelSettings):
        orientation = "N"
        height = settings.default_font_height
        width = settings.default_font_width
        font_name = "Arial"

        if not param_str:
            return orientation, height, width, font_name

        params = self._parse_params(param_str)

        if params and params[0]:
            orientation = params[0].upper() if params[0].upper() in ('N', 'R', 'I', 'B') else "N"
        if len(params) > 1 and params[1]:
            height = self._safe_int(params[1], height)
        if len(params) > 2 and params[2]:
            width = self._safe_int(params[2], width)
        if len(params) > 3 and params[3]:
            # Format: drive:fontname.ext -> extract font name
            font_path = params[3]
            # Remove drive letter prefix like "E:" or "R:"
            if len(font_path) > 2 and font_path[1] == ':':
                font_path = font_path[2:]
            # Remove extension
            if '.' in font_path:
                font_name = font_path[:font_path.rfind('.')]
            else:
                font_name = font_path

        return orientation, height, width, font_name
