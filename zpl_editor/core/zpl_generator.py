from .label_model import LabelModel
from .zpl_commands import ZPLElement
from .zpl_parser import BARCODE_TYPE_TO_CMD, BARCODE_1D_PARAM_ORDER, BARCODE_2D_COMMANDS


class ZPLGenerator:
    def generate(self, model: LabelModel) -> str:
        lines = ["^XA"]

        s = model.settings
        if s.width != 812:
            lines.append(f"^PW{s.width}")
        if s.height != 1218:
            lines.append(f"^LL{s.height}")
        if s.home_x or s.home_y:
            lines.append(f"^LH{s.home_x},{s.home_y}")
        if s.default_font != "0" or s.default_font_height != 30:
            fw = f",{s.default_font_width}" if s.default_font_width else ""
            lines.append(f"^CF{s.default_font},{s.default_font_height}{fw}")
        if s.charset != 28:
            lines.append(f"^CI{s.charset}")
        lines.append("")

        sorted_elements = sorted(model.elements, key=lambda e: (e.y, e.x))

        for elem in sorted_elements:
            elem_lines = self._generate_element(elem, model)
            if elem_lines:
                lines.extend(elem_lines)
                lines.append("")

        lines.append("^XZ")
        return "\n".join(lines)

    def _generate_element(self, elem: ZPLElement, model: LabelModel) -> list:
        lines = []
        props = elem.properties
        comment = self._element_comment(elem)
        if comment:
            lines.append(f"^FX -- {comment} --")

        pos_cmd = "^FT" if elem.use_ft else "^FO"
        lines.append(f"{pos_cmd}{elem.x},{elem.y}")

        if elem.element_type == "text":
            lines.extend(self._gen_text(elem, model))
        elif elem.element_type == "box":
            lines.extend(self._gen_box(elem))
        elif elem.element_type == "circle":
            lines.extend(self._gen_circle(elem))
        elif elem.element_type == "diagonal":
            lines.extend(self._gen_diagonal(elem))
        elif elem.element_type == "barcode":
            lines.extend(self._gen_barcode(elem, model))
        elif elem.element_type == "qrcode":
            lines.extend(self._gen_qrcode(elem))
        elif elem.element_type == "image":
            lines.extend(self._gen_image(elem))

        return lines

    def _element_comment(self, elem: ZPLElement) -> str:
        type_names = {
            "text": "Text Element",
            "box": "Box/Line Element",
            "circle": "Circle Element",
            "diagonal": "Diagonal Line",
            "barcode": "Barcode Element",
            "qrcode": "QR Code Element",
            "image": "Image/graphic region",
        }
        bc_type = elem.properties.get("barcode_type", "")
        if elem.element_type == "barcode" and bc_type:
            try:
                from ..elements.barcode_element import BARCODE_TYPES
                info = BARCODE_TYPES.get(bc_type, {})
                return info.get("name", "Barcode Element")
            except Exception:
                return "Barcode Element"
        return type_names.get(elem.element_type, "")

    def _gen_text(self, elem: ZPLElement, model: LabelModel) -> list:
        lines = []
        props = elem.properties
        font = props.get("font", model.settings.default_font)
        orientation = props.get("orientation", "N")
        height = props.get("font_height", model.settings.default_font_height)
        width = props.get("font_width", model.settings.default_font_width)

        if font == "@":
            font_name = props.get("font_name", "Arial")
            font_str = f"^A@{orientation},{height}"
            if width:
                font_str += f",{width}"
            font_str += f",E:{font_name}.TTF"
            lines.append(font_str)
        else:
            font_str = f"^A{font}{orientation},{height}"
            if width:
                font_str += f",{width}"
            lines.append(font_str)

        if "fb_width" in props and props["fb_width"]:
            fb = f"^FB{props['fb_width']}"
            fb += f",{props.get('fb_max_lines', 1)}"
            fb += f",{props.get('fb_line_spacing', 0)}"
            fb += f",{props.get('fb_alignment', 'L')}"
            fb += f",{props.get('fb_hanging', 0)}"
            lines.append(fb)

        data = props.get("data", "")
        lines.append(f"^FD{data}^FS")
        return lines

    def _gen_box(self, elem: ZPLElement) -> list:
        props = elem.properties
        w = props.get("width", 0)
        h = props.get("height", 0)
        t = props.get("thickness", 1)
        c = props.get("color", "B")
        r = props.get("rounding", 0)
        return [f"^GB{w},{h},{t},{c},{r}^FS"]

    def _gen_circle(self, elem: ZPLElement) -> list:
        props = elem.properties
        d = props.get("diameter", 0)
        t = props.get("thickness", 1)
        c = props.get("color", "B")
        return [f"^GC{d},{t},{c}^FS"]

    def _gen_diagonal(self, elem: ZPLElement) -> list:
        props = elem.properties
        w = props.get("width", 0)
        h = props.get("height", 0)
        t = props.get("thickness", 1)
        c = props.get("color", "B")
        o = props.get("orientation", "R")
        return [f"^GD{w},{h},{t},{c},{o}^FS"]

    def _gen_barcode(self, elem: ZPLElement, model: LabelModel) -> list:
        lines = []
        props = elem.properties
        barcode_type = props.get("barcode_type", "code128")
        mw = props.get("module_width", model.settings.barcode_module_width)
        ratio = props.get("ratio", model.settings.barcode_ratio)
        bh = props.get("bar_height", model.settings.barcode_height)
        orientation = props.get("orientation", "N")
        height = props.get("bar_height", 100)
        interpretation = props.get("interpretation", "Y")
        above = props.get("interpretation_above", "N")
        checkdigit = props.get("checkdigit", "N")

        lines.append(f"^BY{mw},{ratio:.0f},{bh}")

        cmd = BARCODE_TYPE_TO_CMD.get(barcode_type)

        if cmd and cmd in BARCODE_1D_PARAM_ORDER:
            param_order = BARCODE_1D_PARAM_ORDER[cmd]
            param_values = []
            for param_name in param_order:
                if param_name == "orientation":
                    param_values.append(orientation)
                elif param_name == "height":
                    param_values.append(str(height))
                elif param_name == "interpretation":
                    param_values.append(interpretation)
                elif param_name == "above":
                    param_values.append(above)
                elif param_name == "checkdigit":
                    param_values.append(checkdigit)
                elif param_name == "mode":
                    param_values.append(props.get("mode", "N"))
                else:
                    param_values.append(str(props.get(param_name, "")))
            lines.append(f"^{cmd}{','.join(param_values)}")

        elif cmd and cmd in BARCODE_2D_COMMANDS:
            lines.append(self._gen_2d_barcode_cmd(cmd, props, height, orientation))

        else:
            lines.append(f"^BC{orientation},{height},{interpretation},{above},N")

        data = props.get("data", "")
        lines.append(f"^FD{data}^FS")
        return lines

    def _gen_2d_barcode_cmd(self, cmd, props, height, orientation):
        if cmd == "B7":  # PDF417
            sec = props.get("security_level", 0)
            cols = props.get("columns", 0)
            rows = props.get("rows", 0)
            trunc = props.get("truncate", "N")
            return f"^B7{orientation},{height},{sec},{cols},{rows},{trunc}"

        elif cmd == "BX":  # DataMatrix
            quality = props.get("quality", 200)
            cols = props.get("columns", 0)
            rows = props.get("rows", 0)
            return f"^BX{orientation},{height},{quality},{cols},{rows}"

        elif cmd == "BO":  # Aztec
            mag = props.get("magnification", 3)
            ec = props.get("extended_channel", "N")
            err = props.get("error_control", 0)
            mi = props.get("menu_indicator", "N")
            return f"^BO{orientation},{mag},{ec},{err},{mi}"

        elif cmd == "BD":  # MaxiCode
            mode = props.get("mode", 2)
            sn = props.get("symbol_number", 1)
            ts = props.get("total_symbols", 1)
            return f"^BD{mode},{sn},{ts}"

        elif cmd == "B4":  # Code 49
            interp = props.get("interpretation", "N")
            sm = props.get("starting_mode", 0)
            return f"^B4{orientation},{height},{interp},{sm}"

        elif cmd == "BB":  # CODABLOCK-F
            sec = props.get("security_level", "N")
            cols = props.get("columns", 8)
            rows = props.get("rows", 0)
            mode = props.get("mode", "N")
            return f"^BB{orientation},{height},{sec},{cols},{rows},{mode}"

        elif cmd == "BF":  # Micro-PDF417
            mode = props.get("mode", 0)
            cols = props.get("columns", 0)
            return f"^BF{orientation},{height},{mode},{cols}"

        return f"^BC{orientation},{height},Y,N,N"

    def _gen_image(self, elem: ZPLElement) -> list:
        props = elem.properties
        data = props.get("data", "")
        bytes_per_row = props.get("bytes_per_row", 0)
        total_bytes = props.get("total_bytes", 0)
        if data and bytes_per_row and total_bytes:
            return [f"^GFA,{total_bytes},{total_bytes},{bytes_per_row},{data}^FS"]
        return ["^FS"]

    def _gen_qrcode(self, elem: ZPLElement) -> list:
        lines = []
        props = elem.properties
        orientation = props.get("orientation", "N")
        qr_model = props.get("qr_model", 2)
        magnification = props.get("magnification", 3)
        error_correction = props.get("error_correction", "M")
        lines.append(f"^BQ{orientation},{qr_model},{magnification},{error_correction}")
        data = props.get("data", "")
        lines.append(f"^FD{data}^FS")
        return lines
