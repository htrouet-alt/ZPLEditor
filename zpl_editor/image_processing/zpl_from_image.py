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
from typing import List, Optional
from .image_analyzer import DetectedRegion


class ZPLFromImage:
    def __init__(self, text_h_scale: float = 1.0, text_w_scale: float = 1.0, text_y_bias: int = 0):
        self.text_h_scale = text_h_scale
        self.text_w_scale = text_w_scale
        self.text_y_bias = text_y_bias

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

        # Collect image regions for overlap checks — text inside an image
        # region should be skipped (the GFA bitmap is more reliable than OCR).
        image_regions = [r for r in sorted_regions if r.region_type == "image"]

        for region in sorted_regions:
            # Skip text regions that overlap significantly with an image region
            if region.region_type == "text" and image_regions:
                r_area = max(region.width * region.height, 1)
                skip = False
                for img_r in image_regions:
                    ox1 = max(region.x, img_r.x)
                    oy1 = max(region.y, img_r.y)
                    ox2 = min(region.x + region.width, img_r.x + img_r.width)
                    oy2 = min(region.y + region.height, img_r.y + img_r.height)
                    if ox1 < ox2 and oy1 < oy2:
                        overlap = (ox2 - ox1) * (oy2 - oy1)
                        if overlap / r_area > 0.4:
                            skip = True
                            break
                if skip:
                    lines.append(f"^FX Skipped text inside image region")
                    lines.append("")
                    continue
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
                    # Check if barcode module width has non-integer actual value.
                    # Progressive bar misalignment makes ^BC inaccurate when the
                    # actual module width differs significantly from any integer.
                    # Fall back to GFA bitmap for pixel-accurate reproduction.
                    use_gfa = self._barcode_needs_gfa(zpl_w, zpl_h, region)
                    if use_gfa:
                        lines.append(f"^FX Barcode GFA ({region.barcode_type})")
                        lines.extend(self._gen_graphic_region(
                            gray, region, zpl_x, zpl_y, zpl_w, zpl_h, label_width))
                    else:
                        lines.append(f"^FX Barcode ({region.barcode_type})")
                        lines.extend(self._gen_barcode(zpl_x, zpl_y, zpl_w, zpl_h, region))
                else:
                    lines.append("^FX Skipped barcode region (not decoded)")
                    continue

            elif region.region_type == "qrcode":
                if region.data:
                    lines.append(f"^FX QR Code (GFA bitmap)")
                    # Use GFA bitmap for QR codes to preserve exact module pattern
                    # from the original image (different QR encoders produce different
                    # patterns for the same data, causing ~40% pixel mismatch).
                    lines.extend(self._gen_graphic_region(
                        gray, region, zpl_x, zpl_y, zpl_w, zpl_h, label_width))
                else:
                    lines.append("^FX Skipped QR region (not decoded)")
                    continue

            elif region.region_type == "text":
                if region.data:
                    text = self._sanitize_text(region.data)
                    if not text:
                        continue

                    # Regions originally detected as images and converted to text
                    # by OCR: only render as GFA if the OCR text is garbage.
                    # Clean text (e.g. "EKOL-TR-WTFH") should render as ^FD.
                    if region.extra.get("from_image_ocr"):
                        if self._is_garbage_ocr(text):
                            gfa_bytes = ((zpl_w + 7) // 8) * zpl_h
                            if gfa_bytes <= 50000:
                                lines.append(f"^FX Image-OCR garbage as bitmap")
                                lines.extend(self._gen_graphic_region(
                                    gray, region, zpl_x, zpl_y, zpl_w, zpl_h, label_width))
                                continue

                    # Vertical text: region much taller than wide → OCR is unreliable
                    # for rotated text, so use GFA bitmap for pixel-accuracy.
                    if zpl_h > zpl_w * 2.5 and zpl_h > 40:
                        gfa_bytes = ((zpl_w + 7) // 8) * zpl_h
                        if gfa_bytes <= 50000:
                            lines.append(f"^FX Vertical text as bitmap")
                            lines.extend(self._gen_graphic_region(
                                gray, region, zpl_x, zpl_y, zpl_w, zpl_h, label_width))
                            continue

                    ink_profile = None
                    if not region.extra.get("reverse"):
                        ink_profile = self._measure_text_ink_profile(gray, region)

                    fit = self._fit_text_to_region(zpl_w, zpl_h, text, ink_profile)
                    font_h = fit["font_h"]
                    font_w = fit["font_w"]
                    text_x = zpl_x + fit["offset_x"]
                    text_y = zpl_y + fit["offset_y"]
                    num_lines = fit.get("num_lines", 1)

                    # Only fall back to GFA when text is garbage OCR AND
                    # needs heavy wrapping — clean multi-line text stays as ^FD.
                    if num_lines >= 3 and not region.extra.get("reverse"):
                        if self._is_garbage_ocr(text):
                            gfa_bytes = ((zpl_w + 7) // 8) * zpl_h
                            if gfa_bytes <= 50000:
                                lines.append(f"^FX Garbage OCR as bitmap ({num_lines} lines)")
                                lines.extend(self._gen_graphic_region(
                                    gray, region, zpl_x, zpl_y, zpl_w, zpl_h, label_width))
                                continue

                    # Clamp to keep text within detected region bounds.
                    max_x = zpl_x + max(0, zpl_w - fit["text_w_est"])
                    max_y = zpl_y + max(0, zpl_h - fit["ink_h_est"])
                    text_x = min(max(zpl_x, text_x), max_x)
                    text_y = min(max(0, text_y), max_y)

                    if region.extra.get("reverse"):
                        lines.append(f"^FX Reverse banner text")
                        lines.append(f"^FO{zpl_x},{zpl_y}^GB{zpl_w},{zpl_h},{zpl_h},B^FS")
                        lines.append(f"^FO{text_x},{text_y}")
                        lines.append(f"^A0N,{font_h},{font_w}")
                        if num_lines > 1:
                            lines.append(f"^FB{zpl_w},{num_lines + 2},,")
                        lines.append(f"^FR^FD{text}^FS")
                    elif num_lines > 1:
                        lines.append(f"^FO{text_x},{text_y}")
                        lines.append(f"^A0N,{font_h},{font_w}")
                        lines.append(f"^FB{zpl_w},{num_lines + 2},,")
                        lines.append(f"^FD{text}^FS")
                    else:
                        lines.append(f"^FO{text_x},{text_y}")
                        lines.append(f"^A0N,{font_h},{font_w}")
                        lines.append(f"^FD{text}^FS")
                else:
                    lines.append("^FX Skipped text region (no OCR data)")
                    continue

            elif region.region_type == "image":
                # Skip image regions that would produce oversized GFA
                gfa_bytes = ((zpl_w + 7) // 8) * zpl_h
                if gfa_bytes > 50000:
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
    def _is_garbage_ocr(text: str) -> bool:
        """Check if OCR text appears to be garbage/unreliable."""
        if not text or len(text) < 2:
            return True
        # High special character ratio
        normal = sum(1 for c in text if c.isalnum() or c in ' .,:-/()&')
        if len(text) > 5 and normal / len(text) < 0.6:
            return True
        # Many single-character words (noise pattern like "= = a # = z")
        words = text.split()
        if len(words) >= 3:
            single_chars = sum(1 for w in words if len(w) == 1 and not w.isdigit())
            if single_chars / len(words) > 0.4:
                return True
        # Contains unusual characters that indicate OCR noise
        if any(c in text for c in '#=~`|'):
            return True
        return False

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

    @staticmethod
    def _effective_text_length(text: str) -> float:
        """Estimate visual character count (spaces/punctuation are narrower)."""
        if not text:
            return 1.0

        narrow = set("ilI1|!.,:;'`")
        wide = set("MW@#%&")

        total = 0.0
        for ch in text:
            if ch.isspace():
                total += 0.45
            elif ch in narrow:
                total += 0.60
            elif ch in wide:
                total += 1.25
            else:
                total += 1.0
        return max(total, 1.0)

    def _fit_text_to_region(self, box_w: int, box_h: int, text: str,
                            ink_profile: Optional[dict] = None) -> dict:
        """Fit text to a target region and return ZPL font params + offsets.

        Uses natural ZPL font 0 proportions (w/h ~ 0.56) instead of cramming
        all characters into one line.  When text doesn't fit on one line,
        returns num_lines > 1 so the caller can use ^FB wrapping.
        """
        char_count = max(len(text.strip()), 1)
        NATURAL_WH = 0.56  # ZPL font 0 natural width/height ratio

        if ink_profile and ink_profile.get("ink_h"):
            ink_h = ink_profile["ink_h"]
            ink_w = ink_profile.get("ink_w", box_w)
            offset_x = ink_profile.get("ink_x_offset", 0)
            offset_y = ink_profile.get("ink_y_offset", 0)
        else:
            ink_h = box_h
            ink_w = box_w
            offset_x = 0
            offset_y = 0

        # Use full region width (box_w) for the fit check, not the tighter
        # ink_w, because text rendering has the entire region width available.
        available_w = box_w

        # Single-line attempt
        font_h = max(9, int(ink_h * self.text_h_scale))
        natural_fw = max(4, int(round(font_h * NATURAL_WH)))
        single_line_w = natural_fw * char_count

        num_lines = 1
        if single_line_w > available_w * 1.5 and font_h > 15:
            # Text doesn't fit on one line → find smallest num_lines that works
            for n in range(2, 12):
                trial_h = max(9, int(ink_h / n * self.text_h_scale))
                trial_w = max(4, int(round(trial_h * NATURAL_WH)))
                chars_per_line = max(1, int(available_w / trial_w))
                if chars_per_line * n >= char_count:
                    num_lines = n
                    font_h = trial_h
                    break
            else:
                num_lines = 10
                font_h = max(9, int(ink_h / 10))

        font_w = max(4, int(round(font_h * NATURAL_WH)))
        offset_x += self.text_y_bias

        text_w_est = font_w * min(char_count, max(1, ink_w // max(font_w, 1)))
        ink_h_est = font_h * num_lines

        return {
            "font_h": font_h,
            "font_w": font_w,
            "offset_x": offset_x,
            "offset_y": offset_y,
            "text_w_est": text_w_est,
            "ink_h_est": ink_h_est,
            "num_lines": num_lines,
        }

    def _measure_text_ink_profile(self, gray: np.ndarray, region: DetectedRegion) -> Optional[dict]:
        """Measure text ink occupancy inside detected region using image processing."""
        try:
            x1 = max(0, int(region.x))
            y1 = max(0, int(region.y))
            x2 = min(gray.shape[1], int(region.x + region.width))
            y2 = min(gray.shape[0], int(region.y + region.height))
            if x2 <= x1 or y2 <= y1:
                return None

            roi = gray[y1:y2, x1:x2]
            if roi.size == 0:
                return None

            _, binary = cv2.threshold(roi, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            ys, xs = np.where(binary > 0)
            if len(xs) == 0 or len(ys) == 0:
                return None

            ink_x_min = int(xs.min())
            ink_w = int(xs.max() - ink_x_min + 1)
            ink_y_min = int(ys.min())
            ink_h = int(ys.max() - ink_y_min + 1)
            roi_w = max(1, roi.shape[1])
            roi_h = max(1, roi.shape[0])

            return {
                "fill_w": float(np.clip(ink_w / roi_w, 0.0, 1.0)),
                "fill_h": float(np.clip(ink_h / roi_h, 0.0, 1.0)),
                "ink_x_offset": ink_x_min,
                "ink_y_offset": ink_y_min,
                "ink_w": ink_w,
                "ink_h": ink_h,
            }
        except Exception:
            return None

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

    def _barcode_needs_gfa(self, w: int, h: int, region: DetectedRegion) -> bool:
        """Check if a barcode should use GFA bitmap due to module width mismatch.

        When the actual module width is significantly non-integer (fractional part > 0.1),
        progressive bar misalignment causes massive pixel errors (~70% miss rate).
        In those cases, GFA bitmap provides accurate reproduction.
        """
        data = region.data or ""
        bc_type = (region.barcode_type or "").upper()
        data_len = max(len(data), 1)

        # Determine orientation and module span
        orientation = region.extra.get("zpl_orientation", "")
        if orientation not in {"N", "R", "I", "B"}:
            orientation = "R" if h > w * 1.35 else "N"
        rotated = orientation in ("R", "B")
        module_span = h if rotated else w

        # Calculate expected module count based on barcode type
        is_ean13 = "EAN13" in bc_type or ("EAN" in bc_type and data_len >= 12)
        if is_ean13:
            n_modules = 95  # EAN-13 fixed
        elif "CODE39" in bc_type or "39" in bc_type:
            n_modules = (data_len + 2) * 13
        else:
            # Code 128
            can_code_c = data.isdigit() and len(data) % 2 == 0
            mods_b = data_len * 11 + 35
            mods_c = (data_len // 2) * 11 + 35 if can_code_c else mods_b
            # Use the encoding that gives the best integer module width match
            n_modules = mods_b
            if can_code_c:
                actual_mw_b = module_span / max(mods_b, 1)
                actual_mw_c = module_span / max(mods_c, 1)
                frac_b = abs(actual_mw_b - round(actual_mw_b))
                frac_c = abs(actual_mw_c - round(actual_mw_c))
                if frac_c < frac_b:
                    n_modules = mods_c

        if n_modules <= 0:
            return False

        actual_mw = module_span / n_modules
        integer_mw = max(1, round(actual_mw))
        frac = abs(actual_mw - integer_mw)

        # GFA byte size check: only use GFA if it fits in reasonable size
        gfa_bytes = ((w + 7) // 8) * h
        if gfa_bytes > 20000:
            return False

        # Use cumulative position error at barcode end vs module width tolerance.
        # For small mw (2px), even tiny fractional errors accumulate into full-bar
        # misalignment. For large mw (5px+), bars are wide enough to tolerate more drift.
        cumulative_error = n_modules * frac
        tolerance = 5 * integer_mw
        return cumulative_error > tolerance

    def _gen_barcode(self, x: int, y: int, w: int, h: int, region: DetectedRegion) -> list:
        lines = []
        bc_type = region.barcode_type
        data = region.data
        data_len = max(len(data), 1)
        orientation = region.extra.get("zpl_orientation", "")
        if orientation not in {"N", "R", "I", "B"}:
            orientation = "R" if h > w * 1.35 else "N"

        # For rotated barcodes, swap module-direction and bar-length direction
        rotated = orientation in ("R", "B")
        module_span = h if rotated else w   # dimension along module (bar-width) direction
        bar_span = w if rotated else h      # dimension along bar-length direction

        bc_upper = bc_type.upper() if bc_type else ""
        is_ean13 = "EAN13" in bc_upper or ("EAN" in bc_upper and data_len >= 12)

        from ..core.zpl_parser import BARCODE_TYPE_TO_CMD, BARCODE_1D_PARAM_ORDER
        cmd = BARCODE_TYPE_TO_CMD.get(bc_type, "BC")

        # Module width: prefer measured scanline value, validate, then analytic fallback.
        measured_mw = region.extra.get("module_width", 0) or 0

        if is_ean13:
            if measured_mw >= 1:
                module_w = measured_mw
            else:
                module_w = max(1, min(10, round(module_span / 95)))
            is_code_c = False
        elif "CODE39" in bc_upper or "39" in bc_upper:
            total_modules = (data_len + 2) * 13
            if measured_mw >= 1:
                module_w = measured_mw
            else:
                module_w = max(1, min(10, round(module_span / max(total_modules, 1))))
            is_code_c = False
        elif cmd == "BC":
            # Code 128: determine module_width and Code B/C encoding
            can_code_c = data.isdigit() and len(data) % 2 == 0
            mods_b = len(data) * 11 + 35
            mods_c = (len(data) // 2) * 11 + 35 if can_code_c else 0

            if measured_mw >= 1:
                module_w = measured_mw
                # Validate: if measured mw gives barcode > 2× region width, it's wrong
                best_err_b = abs(module_span - mods_b * module_w)
                best_err_c = abs(module_span - mods_c * module_w) if can_code_c else float('inf')
                min_err = min(best_err_b, best_err_c)
                if min_err > module_span * 0.4:
                    # Measured mw is clearly wrong; try analytic
                    n_mods_check = mods_b  # default Code B for check
                    analytic_mw = max(1, round(module_span / max(n_mods_check, 1)))
                    if abs(module_span - n_mods_check * analytic_mw) < min_err:
                        module_w = analytic_mw
            else:
                # No measured value: compute analytically
                n_modules = mods_b
                module_w = max(1, min(10, round(module_span / max(n_modules, 1))))

            # Code B vs Code C discrimination
            if can_code_c:
                err_c = abs(module_span - mods_c * module_w)
                err_b = abs(module_span - mods_b * module_w)
                is_code_c = err_c < err_b
            else:
                is_code_c = False
        else:
            # Other barcode types
            n_modules = len(data) * 11 + 35
            if measured_mw >= 1:
                module_w = measured_mw
            else:
                module_w = max(1, min(10, round(module_span / max(n_modules, 1))))
            is_code_c = False

        module_w = max(1, module_w)

        hri = "Y" if region.extra.get("has_hr_text", False) else "N"
        bar_h = max(30, bar_span)

        # Use explicit subset prefix: >7 for Code C, >: for Code B
        # This prevents the encoder's auto-detection from overriding our decision
        if is_code_c:
            fd_data = ">7" + data
        elif cmd == "BC" and data.isdigit() and len(data) % 2 == 0:
            # Data would trigger auto-detect Code C, but we decided Code B — force it
            fd_data = ">:" + data
        else:
            fd_data = data

        # pyzbar bbox offset: pyzbar's bbox starts ~2 modules after the start pattern,
        # so shift left to include the full barcode. Only for pyzbar-detected barcodes.
        # Heuristic-detected barcodes already include the full barcode extent.
        bc_x = x
        bc_y = y
        is_pyzbar = region.extra.get("pyzbar_detected", False)
        if cmd == "BC" and is_pyzbar:
            if orientation in ("N", "I"):
                bc_x = max(0, x - 2 * module_w)
            elif orientation in ("R", "B"):
                bc_y = max(0, y - 2 * module_w)

        lines.append(f"^BY{module_w},2,{bar_h}")
        lines.append(f"^FO{bc_x},{bc_y}")
        if is_ean13:
            lines.append(f"^BE{orientation},{bar_h},{hri},N")
            lines.append(f"^FD{data}^FS")
        elif cmd in BARCODE_1D_PARAM_ORDER:
            lines.append(f"^{cmd}{orientation},{bar_h},{hri},N")
            lines.append(f"^FD{fd_data}^FS")
        else:
            lines.append(f"^BC{orientation},{bar_h},{hri},N")
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
        # Our local renderer uses border=0 so QR data starts at the ^FO position directly.
        return [
            f"^FO{x},{y}",
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
