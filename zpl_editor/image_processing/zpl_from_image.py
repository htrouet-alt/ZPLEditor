"""
Generate ZPL code from an analyzed image.
Converts detected regions to proper ZPL commands:
- Lines → ^GB (graphic box with minimal height/width)
- Boxes → ^GB (graphic box outline)
- Barcodes → ^BY + ^BC/^BQ etc.
- Text → ^CF + ^FD (with font size from region height)
- Images → ^GFA (Graphic Field ASCII)
"""
import cv2
import numpy as np
from typing import List
from .image_analyzer import DetectedRegion


class ZPLFromImage:
    def generate(self, image: np.ndarray, regions: List[DetectedRegion],
                 label_width: int = 812, label_height: int = 1218,
                 dpi: int = 203) -> str:
        """Generate ZPL from image and detected regions."""
        if image is None:
            print("[ZPLFromImage] ERROR: Image is None")
            return "^XA\n^XZ"
        
        if not regions:
            print("[ZPLFromImage] WARNING: No regions provided, generating full image bitmap")
            return self.generate_full_image(image, label_width, label_height, dpi)

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image.copy()
        img_h, img_w = gray.shape[:2]

        # Guard: if label is smaller than image in both dimensions,
        # the dimensions are likely wrong (e.g. cm entered instead of inches).
        # Fall back to standard 4x6 label at given DPI.
        if label_width < img_w and label_height < img_h:
            print(f"[ZPLFromImage] WARNING: Label {label_width}x{label_height} smaller than "
                  f"image {img_w}x{img_h}. Using standard 4x6 at {dpi} DPI.")
            label_width = round(4 * dpi)
            label_height = round(6 * dpi)

        print(f"[ZPLFromImage] Image: {img_w}x{img_h}, Label: {label_width}x{label_height}, DPI: {dpi}")
        print(f"[ZPLFromImage] Regions to process: {len(regions)}")
        from collections import Counter
        type_counts = Counter([r.region_type for r in regions])
        print(f"[ZPLFromImage] Region types: {dict(type_counts)}")

        # Scale factors: image pixels -> ZPL dots
        # When image aspect ~ label aspect -> image is the full label -> use per-axis scale
        # When very different -> image is a viewport screenshot -> use content-mapped scale
        raw_sx = label_width / img_w
        raw_sy = label_height / img_h

        aspect_img = img_w / max(img_h, 1)
        aspect_lbl = label_width / max(label_height, 1)

        if max(raw_sx, raw_sy) / max(min(raw_sx, raw_sy), 0.01) < 1.3:
            # Scales within 30% → image represents full label
            scale_x, scale_y, y_offset = raw_sx, raw_sy, 0
        else:
            # Viewport capture: image aspect ratio differs from label.
            # X: use label_width/img_width (full width is captured)
            # Y: use label_height/img_height (distributes content across label)
            # Y-offset: shift content so first element gets a small top margin
            scale_x = raw_sx
            scale_y = raw_sy
            y_offset = 0
            if regions:
                first_y = min(r.y for r in regions)
                first_y_label = first_y * scale_y
                # Push content so first element starts near y=50 (standard margin)
                desired_top = max(30, min(50, first_y * scale_x))
                y_offset = desired_top - first_y_label

        lines = ["^XA"]
        lines.append(f"^PW{label_width}")
        lines.append(f"^LL{label_height}")
        lines.append("")

        # Sort regions top-to-bottom, left-to-right
        sorted_regions = sorted(regions, key=lambda r: (r.y, r.x))

        for region in sorted_regions:
            zpl_x = int(region.x * scale_x)
            zpl_y = int(region.y * scale_y + y_offset)
            zpl_w = max(1, int(region.width * scale_x))
            zpl_h = max(1, int(region.height * scale_y))

            if region.region_type == "hline":
                thickness = region.extra.get("thickness", 3)
                zpl_thick = max(1, int(thickness * scale_y))
                lines.append(f"^FO{zpl_x},{zpl_y}^GB{zpl_w},{zpl_thick},{zpl_thick}^FS")

            elif region.region_type == "vline":
                thickness = region.extra.get("thickness", 3)
                zpl_thick = max(1, int(thickness * scale_x))
                lines.append(f"^FO{zpl_x},{zpl_y}^GB{zpl_thick},{zpl_h},{zpl_thick}^FS")

            elif region.region_type == "box":
                thickness = region.extra.get("thickness", 3)
                zpl_thick = max(1, int(thickness * min(scale_x, scale_y)))
                lines.append(f"^FO{zpl_x},{zpl_y}^GB{zpl_w},{zpl_h},{zpl_thick}^FS")

            elif region.region_type == "barcode":
                if region.data:
                    lines.append(f"^FX Barcode ({region.barcode_type})")
                    lines.extend(self._gen_barcode(zpl_x, zpl_y, zpl_w, zpl_h, region))
                else:
                    # Barcode detected but not decoded - fall back to bitmap
                    gfa_bytes = ((zpl_w + 7) // 8) * zpl_h
                    if gfa_bytes <= 20000:
                        lines.append(f"^FX Barcode region (bitmap - not decoded)")
                        lines.extend(self._gen_graphic_region(
                            gray, region, zpl_x, zpl_y, zpl_w, zpl_h, label_width))

            elif region.region_type == "qrcode":
                if region.data:
                    lines.append(f"^FX QR Code")
                    lines.extend(self._gen_qrcode(zpl_x, zpl_y, zpl_w, region))
                else:
                    gfa_bytes = ((zpl_w + 7) // 8) * zpl_h
                    if gfa_bytes <= 20000:
                        lines.append(f"^FX QR Code region (bitmap - not decoded)")
                        lines.extend(self._gen_graphic_region(
                            gray, region, zpl_x, zpl_y, zpl_w, zpl_h, label_width))

            elif region.region_type == "text":
                if region.data:
                    text = self._sanitize_text(region.data)
                    if not text:
                        continue

                    fit = self._fit_text_to_region(zpl_w, zpl_h, text)
                    font_h = fit["font_h"]
                    font_w = fit["font_w"]
                    text_x = zpl_x + fit["offset_x"]
                    text_y = zpl_y + fit["offset_y"]

                    # If text is extremely condensed (many chars in a tiny area),
                    # bitmap rendering is usually closer to the source image than ^A0.
                    if fit["prefer_bitmap"]:
                        gfa_bytes = ((zpl_w + 7) // 8) * zpl_h
                        if gfa_bytes <= 20000:
                            lines.append(f"^FX Text region (bitmap - tight fit)")
                            lines.extend(self._gen_graphic_region(
                                gray, region, zpl_x, zpl_y, zpl_w, zpl_h, label_width))
                            lines.append("")
                            continue

                    # If this text was OCR'd from an image region and is very short,
                    # render as bitmap in large boxes to avoid logo->text false conversions.
                    if (region.extra.get("from_image_ocr")
                            and len(text) <= 3
                            and (zpl_w * zpl_h) > 7000):
                        gfa_bytes = ((zpl_w + 7) // 8) * zpl_h
                        if gfa_bytes <= 20000:
                            lines.append(f"^FX Text region (bitmap - image OCR safety)")
                            lines.extend(self._gen_graphic_region(
                                gray, region, zpl_x, zpl_y, zpl_w, zpl_h, label_width))
                            lines.append("")
                            continue

                    if region.extra.get("reverse"):
                        # Reverse-video: use GFA bitmap to exactly reproduce the black
                        # background + white text pixels (including emojis/special chars).
                        gfa_bytes = ((zpl_w + 7) // 8) * zpl_h
                        if gfa_bytes <= 20000:
                            lines.append(f"^FX Reverse banner (bitmap)")
                            lines.extend(self._gen_graphic_region(
                                gray, region, zpl_x, zpl_y, zpl_w, zpl_h, label_width))
                        else:
                            # Fallback: filled box + white text for very large banners
                            lines.append(f"^FX Reverse banner text")
                            lines.append(f"^FO{zpl_x},{zpl_y}^GB{zpl_w},{zpl_h},{zpl_h},B^FS")
                            lines.append(f"^FO{text_x},{text_y}")
                            lines.append(f"^A0N,{font_h},{font_w}")
                            lines.append(f"^FR^FD{text}^FS")
                    else:
                        lines.append(f"^FO{text_x},{text_y}")
                        lines.append(f"^A0N,{font_h},{font_w}")
                        lines.append(f"^FD{text}^FS")
                else:
                    gfa_bytes = ((zpl_w + 7) // 8) * zpl_h
                    if gfa_bytes > 20000:
                        lines.append(f"^FX Skipped large text bitmap ({gfa_bytes} bytes)")
                        continue
                    lines.append(f"^FX Text region (bitmap)")
                    lines.extend(self._gen_graphic_region(
                        gray, region, zpl_x, zpl_y, zpl_w, zpl_h, label_width))

            elif region.region_type == "image":
                # Skip image regions that would produce oversized GFA
                gfa_bytes = ((zpl_w + 7) // 8) * zpl_h
                if gfa_bytes > 20000:
                    lines.append(f"^FX Skipped large image region ({gfa_bytes} bytes)")
                    continue
                lines.append(f"^FX Image/graphic region")
                lines.extend(self._gen_graphic_region(
                    gray, region, zpl_x, zpl_y, zpl_w, zpl_h, label_width))

            lines.append("")

        lines.append("^XZ")
        zpl = "\n".join(lines)
        
        # Count generated commands
        fd_count = zpl.count('^FD')
        gb_count = zpl.count('^GB')
        gfa_count = zpl.count('^GFA')
        bq_count = zpl.count('^BQ')
        bc_count = zpl.count('^BC')
        print(f"[ZPLFromImage] Generated ZPL: {len(zpl)} chars, {fd_count}^FD, {gb_count}^GB, "
              f"{gfa_count}^GFA, {bq_count}^BQ, {bc_count}^BC")
        
        return zpl

    def generate_full_image(self, image: np.ndarray,
                            label_width: int = 812, label_height: int = 1218,
                            dpi: int = 203) -> str:
        """Convert entire image to ZPL ^GFA graphic."""
        if image is None:
            return "^XA\n^XZ"

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image.copy()
        img_h, img_w = gray.shape[:2]
        if label_width < img_w and label_height < img_h:
            label_width = round(4 * dpi)
            label_height = round(6 * dpi)
        resized = cv2.resize(gray, (label_width, label_height), interpolation=cv2.INTER_AREA)
        _, binary255 = cv2.threshold(resized, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        binary = (binary255 > 0).astype(np.uint8)
        gfa = self._bitmap_to_gfa(binary, 0, 0)

        return "\n".join([
            "^XA",
            f"^PW{label_width}",
            f"^LL{label_height}",
            "",
            "^FX Full image",
            gfa,
            "",
            "^XZ",
        ])

    @staticmethod
    def _calculate_font_size(height: int, text: str = '') -> int:
        """Map text region height (in ZPL dots) to appropriate font size.
        Uses actual region height for accurate rendering."""
        # Minimum font size
        if height < 15:
            return 15
        # Use actual region height - ZPL font 0 renders at specified height
        return height

    @staticmethod
    def _sanitize_text(text: str) -> str:
        """Sanitize text for ^FD usage by removing unsupported control chars."""
        if text is None:
            return ""
        # ^ and ~ are command introducers in ZPL; remove to avoid command breaks.
        cleaned = text.replace('^', '').replace('~', '')
        cleaned = ''.join(ch for ch in cleaned if ch == '\t' or ch == ' ' or 32 <= ord(ch) < 127)
        return cleaned.strip()

    @staticmethod
    def _text_width_factor(text: str) -> float:
        """Estimate average glyph width / height ratio for ZPL font 0."""
        if not text:
            return 0.56
        digits = sum(ch.isdigit() for ch in text)
        upper = sum(ch.isalpha() and ch.isupper() for ch in text)
        lower = sum(ch.isalpha() and ch.islower() for ch in text)
        spaces = sum(ch.isspace() for ch in text)
        n = max(len(text), 1)

        ratio = 0.56
        ratio -= (digits / n) * 0.03
        ratio += (upper / n) * 0.03
        ratio -= (lower / n) * 0.01
        ratio -= (spaces / n) * 0.02
        return max(0.46, min(0.66, ratio))

    def _fit_text_to_region(self, box_w: int, box_h: int, text: str) -> dict:
        """Fit text to a target region and return ZPL font params + offsets."""
        n_chars = max(len(text), 1)
        pad_x = max(1, min(8, box_w // 20))
        pad_y = max(1, min(6, box_h // 15))

        avail_w = max(8, box_w - 2 * pad_x)
        avail_h = max(10, box_h - 2 * pad_y)

        width_factor = self._text_width_factor(text)
        max_h_from_width = int(avail_w / max(width_factor * n_chars, 0.01))

        font_h = max(10, min(avail_h, max_h_from_width))
        font_w = max(5, int(round(font_h * width_factor)))

        # Safety loop: ensure text fits width
        while n_chars * font_w > avail_w and font_w > 4:
            font_w -= 1

        # If very narrow, reduce height proportionally to avoid heavy strokes
        if font_w < max(6, int(font_h * 0.35)):
            font_h = max(9, int(round(font_w / max(width_factor, 0.2))))

        text_w_est = n_chars * font_w
        offset_x = pad_x + max(0, (avail_w - text_w_est) // 2)
        offset_y = pad_y + max(0, (avail_h - font_h) // 2)

        compact_ratio = avail_w / max(n_chars, 1)
        prefer_bitmap = (font_h < 12 and n_chars >= 12) or compact_ratio < 5.0

        return {
            "font_h": font_h,
            "font_w": font_w,
            "offset_x": offset_x,
            "offset_y": offset_y,
            "prefer_bitmap": prefer_bitmap,
        }

    def _measure_region_ink_height(self, gray: np.ndarray, region) -> int:
        """Measure actual ink height of a text region from binary image.
        
        This fixes the systematic underestimation where Tesseract reports
        only the main body of text but misses descenders (g, y, p, q).
        
        Returns:
            Actual ink height in pixels, or 0 if can't measure.
        """
        try:
            # Extract region with padding below to catch descenders
            pad_below = max(20, int(region.height * 0.5))
            pad_sides = max(5, int(region.width * 0.02))
            
            x1 = max(0, region.x - pad_sides)
            y1 = max(0, region.y)
            x2 = min(gray.shape[1], region.x + region.width + pad_sides)
            y2 = min(gray.shape[0], region.y + region.height + pad_below)
            
            if x2 <= x1 or y2 <= y1:
                return 0
            
            # Get ROI and threshold
            roi = gray[y1:y2, x1:x2]
            _, binary = cv2.threshold(roi, 128, 1, cv2.THRESH_BINARY_INV)
            
            # Find ink rows
            row_sums = np.sum(binary, axis=1)
            ink_rows = np.where(row_sums > 0)[0]
            
            if len(ink_rows) == 0:
                return 0
            
            # Get ink bounds
            ink_top = ink_rows[0]
            ink_bottom = ink_rows[-1]
            ink_height = ink_bottom - ink_top + 1
            
            # Validate: should be reasonable
            if ink_height < region.height * 0.5:
                return 0
            if ink_height > region.height * 3:
                return 0
            
            return ink_height
        except Exception:
            return 0

    def _check_for_descenders(self, gray: np.ndarray, region) -> int:
        """Check if there are ink pixels below the detected region (descenders).
        
        Returns extended height if descenders found, otherwise returns original height.
        """
        try:
            # Look below the detected region
            check_depth = max(15, int(region.height * 0.4))  # Check 40% or at least 15px below
            
            y_start = region.y + region.height
            y_end = min(gray.shape[0], y_start + check_depth)
            
            if y_end <= y_start:
                return region.height
            
            # Get region below
            x1 = max(0, region.x)
            x2 = min(gray.shape[1], region.x + region.width)
            region_below = gray[y_start:y_end, x1:x2]
            
            if region_below.size == 0:
                return region.height
            
            # Threshold and check for ink
            _, binary = cv2.threshold(region_below, 128, 1, cv2.THRESH_BINARY_INV)
            
            # Find ink rows from top (closest to detected region)
            row_sums = np.sum(binary, axis=1)
            
            # Check if there's significant ink in the first few rows below
            # This indicates descenders that would be cut off
            first_rows_ink = np.sum(row_sums[:5] > 0)
            
            if first_rows_ink >= 2:  # At least 2 of first 5 rows have ink
                # Find last ink row
                ink_rows = np.where(row_sums > 0)[0]
                if len(ink_rows) > 0:
                    last_ink = ink_rows[-1]
                    # Extend height to include all descenders
                    new_height = region.height + last_ink + 1
                    # Convert to font cell height (Labelary: ink = 75% of font_h)
                    return round(new_height / 0.75)
            
            return region.height
            
        except Exception:
            return region.height

    def _gen_barcode(self, x: int, y: int, w: int, h: int, region: DetectedRegion) -> list:
        lines = []
        bc_type = region.barcode_type
        data = region.data
        bar_h = max(30, h)
        data_len = max(len(data), 1)

        bc_upper = bc_type.upper() if bc_type else ""
        is_ean13 = "EAN13" in bc_upper or ("EAN" in bc_upper and data_len >= 12)

        # Module width: prefer measured scanline value (most reliable), analytic as fallback.
        # The scanline measurement in image_analyzer._measure_module_width samples the narrowest
        # bar run in the actual image, giving the true module width regardless of encoding.
        module_w = region.extra.get("module_width", 0)
        if not module_w:
            # Analytic fallback: Code 128 uses ~20 quiet-zone modules per side (Labelary standard),
            # EAN-13 pyzbar bbox = bars only (no quiet zone).
            if is_ean13:
                module_w = max(1, min(10, round(w / 95)))
            elif "CODE39" in bc_upper or "39" in bc_upper:
                total_modules = (data_len + 2) * 13
                module_w = max(1, min(10, round(w / max(total_modules, 1))))
            else:
                is_code_c = (data.isdigit() and len(data) % 2 == 0)
                if is_code_c:
                    n_modules = (len(data) // 2) * 11 + 35
                else:
                    n_modules = len(data) * 11 + 35
                module_w = max(1, min(10, round(w / (n_modules + 40))))
        module_w = max(1, module_w)

        # Print human-readable interpretation line only if it was present in the original
        hri = "Y" if region.extra.get("has_hr_text", False) else "N"

        from ..core.zpl_parser import BARCODE_TYPE_TO_CMD, BARCODE_1D_PARAM_ORDER
        cmd = BARCODE_TYPE_TO_CMD.get(bc_type, "BC")
        # For Code 128 (^BC): determine whether the original used Code B or Code C
        # by comparing the measured barcode width against Code B and Code C predictions.
        # Code C (pairs): (N/2)*11 + 35 modules; Code B (chars): N*11 + 35 modules.
        # Using measured width (w) + module_w gives a reliable discriminator.
        if cmd == "BC" and data.isdigit() and len(data) % 2 == 0:
            n_pairs = len(data) // 2
            mods_c = n_pairs * 11 + 35
            mods_b = len(data) * 11 + 35
            err_c = abs(w - mods_c * module_w)
            err_b = abs(w - mods_b * module_w)
            is_code_c = err_c < err_b
        else:
            is_code_c = False
        fd_data = (">7" + data) if is_code_c else data

        # pyzbar for Code 128 reports x at start-of-first-space (after 2-module START bar),
        # so the actual first bar is 2 modules to the LEFT of pyzbar's bbox x.
        # Confirmed via pixel run-length analysis on all 3 barcode labels:
        #   label_1: actual_x=30, pyzbar_x=36, mw=3 → offset=6=2×3
        #   label_2: actual_x=30, pyzbar_x=34, mw=2 → offset=4=2×2
        #   label_3: actual_x=100, pyzbar_x=110, mw=5 → offset=10=2×5
        bc_x = max(0, x - 2 * module_w) if cmd == "BC" else x

        lines.append(f"^BY{module_w},2,{bar_h}")
        lines.append(f"^FO{bc_x},{y}")
        if is_ean13:
            lines.append(f"^BEN,{bar_h},{hri},N")
            lines.append(f"^FD{data}^FS")
        elif cmd in BARCODE_1D_PARAM_ORDER:
            lines.append(f"^{cmd}N,{bar_h},{hri},N")
            lines.append(f"^FD{fd_data}^FS")
        else:
            lines.append(f"^BCN,{bar_h},{hri},N")
            lines.append(f"^FD{fd_data}^FS")
        return lines

    # QR byte-mode capacity per version per ECC level (L, M, Q, H).
    # Source: ISO/IEC 18004 Table 7. Used to match the original QR's ECC level.
    _QR_BYTE_CAP = {
        1: (17, 14, 11, 7),   2: (32, 26, 20, 14),   3: (53, 42, 32, 24),
        4: (78, 62, 46, 34),  5: (106, 86, 60, 46),  6: (134, 110, 74, 58),
        7: (154, 122, 86, 69), 8: (192, 154, 108, 79), 9: (230, 182, 130, 97),
        10: (271, 213, 151, 115),
    }

    def _gen_qrcode(self, x: int, y: int, w: int, region: DetectedRegion) -> list:
        data = region.data
        n = len(data.encode('utf-8'))  # byte count for capacity lookup
        # pyzbar reports bbox as (min_x, min_y, max_x-min_x, max_y-min_y) — off-by-one.
        # Actual data span = w+1 pixels = vm * mag (where vm = 4*V+17 = data modules only,
        # no quiet zone). Match data span directly, not including quiet zone.
        actual_span = w + 1

        best_mag = 4
        best_v = 4
        best_err = float('inf')
        for v in range(1, 11):  # QR version 1-10
            vm = 4 * v + 17  # version modules (data only, no quiet zone)
            for mag in range(1, 11):
                err = abs(vm * mag - actual_span)
                if err < best_err:
                    best_err = err
                    best_mag = mag
                    best_v = v
                if err == 0:
                    break
            if best_err == 0:
                break

        # Determine the ECC level that matches the original QR code.
        # ZPL default ECC is 'M'. Most label printers use M unless explicitly specified.
        # Use M when data fits, fall back to L only when M capacity is exceeded.
        # If the detected version is uncertain (best_err > 0), fall back to M.
        ecc = 'M'
        if best_err == 0:
            caps = self._QR_BYTE_CAP.get(best_v, (n, n, n, n))
            # caps = (L, M, Q, H) capacities
            if n <= caps[1]:     # fits in M (covers L too) - use M as default
                ecc = 'M'
            elif n <= caps[0]:   # fits in L but not M
                ecc = 'L'
            else:
                ecc = 'L'        # shouldn't happen; fallback

        # pyzbar reports the bbox starting at the data (finder pattern), no quiet zone.
        # Labelary adds a fixed 10px top quiet zone above the data for any magnification.
        # Subtract 10 from y so the rendered data aligns with pyzbar's reported position.
        # No x offset: Labelary left-aligns data at the ^FO x position.
        adj_y = max(0, y - 10)
        return [
            f"^FO{x},{adj_y}",
            f"^BQN,2,{best_mag}",
            f"^FD{ecc}A,{data}^FS",
        ]

    def _gen_graphic_region(self, gray: np.ndarray, region: DetectedRegion,
                            zpl_x: int, zpl_y: int,
                            zpl_w: int, zpl_h: int,
                            label_width: int) -> list:
        """Convert an image region to ^GFA graphic field."""
        ry = max(0, region.y)
        rx = max(0, region.x)
        rh = min(region.height, gray.shape[0] - ry)
        rw = min(region.width, gray.shape[1] - rx)

        if rw <= 0 or rh <= 0:
            return []

        roi = gray[ry:ry + rh, rx:rx + rw]
        target_w = max(1, zpl_w)
        target_h = max(1, zpl_h)
        resized = cv2.resize(roi, (target_w, target_h), interpolation=cv2.INTER_AREA)
        _, binary255 = cv2.threshold(resized, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        binary = (binary255 > 0).astype(np.uint8)
        return [self._bitmap_to_gfa(binary, zpl_x, zpl_y)]

    def _bitmap_to_gfa(self, binary: np.ndarray, x: int, y: int) -> str:
        """Convert binary bitmap to ^GFA command string."""
        h, w = binary.shape
        bytes_per_row = (w + 7) // 8
        total_bytes = bytes_per_row * h

        hex_rows = []
        for row in range(h):
            row_hex = ""
            for col_byte in range(bytes_per_row):
                byte_val = 0
                for bit in range(8):
                    px_col = col_byte * 8 + bit
                    if px_col < w and binary[row, px_col] > 0:
                        byte_val |= (1 << (7 - bit))
                row_hex += f"{byte_val:02X}"
            hex_rows.append(row_hex)

        hex_data = "".join(hex_rows)
        return f"^FO{x},{y}^GFA,{total_bytes},{total_bytes},{bytes_per_row},{hex_data}^FS"
