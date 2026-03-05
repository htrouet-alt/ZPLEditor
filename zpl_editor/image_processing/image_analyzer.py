"""
Image analyzer for detecting barcodes, QR codes, text, lines, boxes, and image regions.
Uses OpenCV for image processing, pyzbar for barcode detection,
and RapidOCR (ONNX Runtime) for text recognition.
"""
import cv2
import numpy as np
import traceback
import importlib.util
from collections import defaultdict
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class DetectedRegion:
    region_type: str  # "barcode", "qrcode", "text", "image", "hline", "vline", "box"
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    data: str = ""
    barcode_type: str = ""
    confidence: float = 0.0
    extra: dict = field(default_factory=dict)


class ImageAnalyzer:
    _ocr_reader = None  # Singleton: RapidOCR shared across instances
    _easyocr_reader = None  # Singleton: EasyOCR shared across instances

    def __init__(self, enabled_engines=None, tesseract_path=None):
        """Initialize image analyzer.

        Args:
            enabled_engines: Optional set of engine names to enable.
                Valid values: {"rapidocr", "easyocr", "tesseract"}.
                If None, auto-detect all available engines (default).
                If provided, only listed engines that are actually installed
                will be enabled.
            tesseract_path: Path to tesseract executable. If None, uses default.
        """
        from ..utils.settings import DEFAULT_TESSERACT_PATH
        self._tesseract_path = tesseract_path or DEFAULT_TESSERACT_PATH
        self._has_pyzbar = importlib.util.find_spec("pyzbar") is not None

        # Auto-detect availability (lightweight check via find_spec).
        # Actual engine init is lazy -- if DLLs fail at runtime,
        # the singleton pattern handles it gracefully and falls through.
        rapidocr_available = importlib.util.find_spec("rapidocr_onnxruntime") is not None
        easyocr_available = importlib.util.find_spec("easyocr") is not None
        tesseract_available = False
        try:
            import pytesseract
            pytesseract.pytesseract.tesseract_cmd = self._tesseract_path
            pytesseract.get_tesseract_version()
            tesseract_available = True
        except Exception:
            pass

        # Apply engine filter if provided
        if enabled_engines is None:
            self._has_ocr = rapidocr_available
            self._has_easyocr = easyocr_available
            self._has_tesseract = tesseract_available
        else:
            self._has_ocr = rapidocr_available and "rapidocr" in enabled_engines
            self._has_easyocr = easyocr_available and "easyocr" in enabled_engines
            self._has_tesseract = tesseract_available and "tesseract" in enabled_engines

    @classmethod
    def _get_ocr_reader(cls):
        """Get or create the shared RapidOCR engine. Returns None on failure."""
        if cls._ocr_reader is False:
            return None
        if cls._ocr_reader is None:
            try:
                from rapidocr_onnxruntime import RapidOCR
                cls._ocr_reader = RapidOCR()
            except Exception as e:
                print(f"[ImageAnalyzer] Failed to init RapidOCR: {e}")
                cls._ocr_reader = False
                return None
        return cls._ocr_reader

    @classmethod
    def _get_easyocr_reader(cls):
        """Get or create the shared EasyOCR engine (downloads models on first use).
        Returns None on failure."""
        if cls._easyocr_reader is False:
            return None
        if cls._easyocr_reader is None:
            try:
                import easyocr
                cls._easyocr_reader = easyocr.Reader(['en'], gpu=False, verbose=False)
                print("[ImageAnalyzer] EasyOCR initialized")
            except Exception as e:
                print(f"[ImageAnalyzer] Failed to init EasyOCR: {e}")
                cls._easyocr_reader = False
                return None
        return cls._easyocr_reader

    @staticmethod
    def get_available_engines(tesseract_path=None):
        """Return a dict of engine name -> is_available (bool).
        Uses lightweight find_spec check. Actual init is lazy at runtime."""
        from ..utils.settings import DEFAULT_TESSERACT_PATH
        tess_path = tesseract_path or DEFAULT_TESSERACT_PATH
        available = {
            "rapidocr": importlib.util.find_spec("rapidocr_onnxruntime") is not None,
            "easyocr": importlib.util.find_spec("easyocr") is not None,
            "tesseract": False,
        }
        try:
            import pytesseract
            pytesseract.pytesseract.tesseract_cmd = tess_path
            pytesseract.get_tesseract_version()
            available["tesseract"] = True
        except Exception:
            pass
        return available

    def _ocr_crop_text(self, crop: np.ndarray) -> str:
        """Run OCR on a preprocessed grayscale crop.
        Tries RapidOCR → EasyOCR → Tesseract (in that order)."""
        best_text = ""

        # 1. RapidOCR (fastest, pure pip)
        if self._has_ocr:
            engine = self._get_ocr_reader()
            if engine is not None:
                try:
                    result, _ = engine(crop)
                    if result:
                        texts = [t.strip() for _, t, c in result if c > 0.3 and t.strip()]
                        if texts:
                            best_text = " ".join(texts)
                except Exception:
                    pass

        # 2. EasyOCR (pure pip, needs PyTorch)
        if not best_text and self._has_easyocr:
            reader = self._get_easyocr_reader()
            if reader is not None:
                try:
                    results = reader.readtext(crop)
                    if results:
                        texts = [t.strip() for _, t, c in results if c > 0.3 and t.strip()]
                        if texts:
                            best_text = " ".join(texts)
                except Exception:
                    pass

        # 3. Tesseract (requires system install, fallback)
        if not best_text and self._has_tesseract:
            try:
                import pytesseract
                pytesseract.pytesseract.tesseract_cmd = self._tesseract_path
                _, binary = cv2.threshold(crop, 0, 255,
                                          cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                for psm in ['7', '6']:
                    try:
                        text = pytesseract.image_to_string(
                            binary, config=f'--oem 3 --psm {psm}'
                        ).strip()
                        if text and len(text) > len(best_text):
                            best_text = text
                    except Exception:
                        pass
            except Exception:
                pass

        return best_text.replace('\n', ' ').strip()

    def _ocr_results_to_word_blocks(self, ocr_results, scale: float, img_h: int) -> list:
        """Convert RapidOCR/EasyOCR line-level results to word-level blocks.
        OCR engines return line-level bboxes; this splits multi-word results
        into individual word blocks with proportionally allocated widths.

        ocr_results: list of (bbox, text, confidence) tuples
          - RapidOCR bbox: [[x1,y1],[x2,y1],[x2,y2],[x1,y2]]
          - EasyOCR bbox: same format
        """
        blocks = []
        for item in ocr_results:
            bbox, text, conf = item
            text = text.strip()
            if not text or conf < 0.3:
                continue

            # Extract bounding box (handle both list-of-lists and numpy arrays)
            try:
                pts = np.array(bbox)
                x_min = int(pts[:, 0].min() / scale)
                x_max = int(pts[:, 0].max() / scale)
                y_min = int(pts[:, 1].min() / scale)
                y_max = int(pts[:, 1].max() / scale)
            except Exception:
                continue

            w_total = x_max - x_min
            h = y_max - y_min
            if w_total < 3 or h < 3:
                continue

            # Split multi-word results into individual word blocks
            words = text.split()
            if len(words) <= 1:
                if self._is_noise_text(text, w_total, h, img_h):
                    continue
                blocks.append({
                    'text': text, 'x': x_min, 'y': y_min,
                    'w': w_total, 'h': h, 'conf': int(conf * 100)
                })
            else:
                total_chars = sum(len(w) for w in words)
                if total_chars == 0:
                    continue
                x_cursor = x_min
                for word in words:
                    word_w = max(1, int(w_total * len(word) / total_chars))
                    if self._is_noise_text(word, word_w, h, img_h):
                        x_cursor += word_w
                        continue
                    blocks.append({
                        'text': word, 'x': x_cursor, 'y': y_min,
                        'w': word_w, 'h': h, 'conf': int(conf * 100)
                    })
                    x_cursor += word_w

        return blocks

    def analyze(self, image: np.ndarray) -> List[DetectedRegion]:
        """Analyze image and return detected regions.
        Order: barcodes → text → lines/boxes → images
        Text is NOT excluded by lines/boxes (text can be inside boxes)."""
        if image is None:
            return []

        results = []
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image.copy()
        img_h, img_w = gray.shape[:2]
        print(f"[ImageAnalyzer] Input: {img_w}x{img_h}, channels={len(image.shape)}, "
              f"gray range=[{int(gray.min())},{int(gray.max())}]")

        # Precompute clean binary image (used by line/box/image detection)
        self._binary_cache = self._get_binary(gray)
        fg_pixels = int(np.sum(self._binary_cache > 0))
        fg_pct = fg_pixels / max(img_w * img_h, 1) * 100
        print(f"[ImageAnalyzer] Binary: Otsu, foreground={fg_pct:.1f}%")

        # 1. Detect barcodes and QR codes FIRST
        bc_regions = self._detect_barcodes(image, gray)
        bc_regions = self._deduplicate_barcodes(bc_regions)
        # Try to decode any barcode regions that have no data
        for bc in bc_regions:
            if not bc.data and bc.region_type == "barcode":
                self._try_decode_barcode_region(image, gray, bc)
        # Measure module width for 1D barcodes from the actual bar pattern
        for bc in bc_regions:
            if bc.region_type == "barcode" and bc.data:
                orientation = self._infer_barcode_orientation(gray, bc)
                bc.extra["zpl_orientation"] = orientation
                mw = self._measure_module_width(gray, bc, orientation)
                if mw > 0:
                    bc.extra["module_width"] = mw
        results.extend(bc_regions)
        print(f"[ImageAnalyzer] Barcodes detected: {len(bc_regions)}")

        # 2. Detect text (exclude only barcode areas, NOT lines/boxes)
        text_regions = self._detect_text(image, gray, bc_regions)
        results.extend(text_regions)
        ocr_count = sum(1 for r in text_regions if r.data)
        print(f"[ImageAnalyzer] Text regions: {len(text_regions)} ({ocr_count} with OCR data)")

        # 3. Detect lines and boxes (exclude barcode areas)
        line_regions = self._detect_lines(gray, bc_regions)
        line_regions = self._merge_collinear_lines(line_regions, img_w, img_h)
        box_regions = self._detect_boxes(gray, bc_regions)
        # Remove false-positive boxes that are actually text block contours
        box_regions = self._remove_text_formed_boxes(box_regions, text_regions)
        # Resolve conflicts: remove false boxes formed by line intersections,
        # then remove lines that are edges of real boxes
        box_regions = self._remove_line_formed_boxes(box_regions, line_regions)
        line_regions = self._remove_box_edge_lines(line_regions, box_regions)
        line_regions = self._merge_collinear_lines(line_regions, img_w, img_h)
        # Convert boxes with internal graphics (logos, icons) to image regions
        box_regions, graphic_boxes = self._separate_graphic_boxes(gray, box_regions)
        # Post-process: convert clusters of vlines into barcode regions
        line_regions, extra_barcodes = self._vlines_to_barcodes(line_regions)
        # Filter vline-barcodes: must not overlap existing barcodes,
        # and must not be in dense (>70%) regions (likely logos/banners)
        filtered_extra_bc = []
        for b in extra_barcodes:
            if self._overlaps_any(b, bc_regions):
                continue
            roi = self._binary_cache[b.y:b.y+b.height, b.x:b.x+b.width]
            density = np.sum(roi > 0) / max(roi.size, 1)
            if density > 0.70:
                continue  # Too dense for a barcode
            filtered_extra_bc.append(b)
        extra_barcodes = self._deduplicate_barcodes(filtered_extra_bc)
        # Try to decode the vline-cluster barcodes
        for bc in extra_barcodes:
            self._try_decode_barcode_region(image, gray, bc)
        results.extend(extra_barcodes)
        bc_regions = self._deduplicate_barcodes(bc_regions + extra_barcodes)
        results.extend(line_regions)
        results.extend(box_regions)
        results.extend(graphic_boxes)
        print(f"[ImageAnalyzer] Lines: {len(line_regions)}, Boxes: {len(box_regions)}"
              f"{f', graphic-boxes->images: {len(graphic_boxes)}' if graphic_boxes else ''}"
              f"{f', vline-barcodes: {len(extra_barcodes)}' if extra_barcodes else ''}")

        # 3.1. Detect filled dark headers inside boxes (e.g., WARNING box)
        box_headers = self._detect_box_headers(gray, box_regions)
        if box_headers:
            # Remove text regions significantly inside the box header
            # (these would be garbage OCR from white-on-dark text)
            to_remove = set()
            for bh_region in box_headers:
                for i, r in enumerate(results):
                    if r.region_type == "text":
                        overlap = self._overlap_area(bh_region, r)
                        r_area = max(r.width * r.height, 1)
                        if overlap / r_area > 0.5:
                            to_remove.add(i)
            if to_remove:
                results = [r for i, r in enumerate(results) if i not in to_remove]
                text_regions = [r for r in text_regions
                                if not any(self._overlap_area(bh, r) / max(r.width * r.height, 1) > 0.5
                                           for bh in box_headers)]
                print(f"[ImageAnalyzer] Removed {len(to_remove)} text regions inside box headers")
            results.extend(box_headers)
            print(f"[ImageAnalyzer] Box headers: {len(box_headers)}")

        # 3.5. Detect text inside grid cells (headers, checkboxes, etc.)
        grid_text = self._detect_grid_cell_text(gray, line_regions, text_regions)
        if grid_text:
            results.extend(grid_text)
            text_regions.extend(grid_text)
            print(f"[ImageAnalyzer] Grid cell text: {len(grid_text)}")

        # 4. Detect image/graphic regions (exclude everything found so far)
        img_regions = self._detect_images(gray, results)
        # 4a. Detect colored regions (logos, icons) that binary detection misses
        if len(image.shape) == 3:
            color_regions = self._detect_colored_regions(image, results + img_regions)
            if color_regions:
                img_regions.extend(color_regions)
                print(f"[ImageAnalyzer] Colored regions: {len(color_regions)}")
        # Try OCR on image regions - large bold text (e.g. "CA") may be classified as images
        text_from_images, img_regions = self._ocr_image_regions(gray, img_regions)
        results.extend(text_from_images)
        results.extend(img_regions)
        print(f"[ImageAnalyzer] Image regions: {len(img_regions)}"
              f"{f', converted to text: {len(text_from_images)}' if text_from_images else ''}")

        # 5. Detect reverse-video banners (white text on dark background)
        reverse_regions = self._detect_reverse_banners(gray, results)
        if reverse_regions:
            # Remove text/image regions that overlap with detected reverse banners
            # (they contain OCR garbage from reading dark-on-dark)
            to_remove = set()
            for rev in reverse_regions:
                for i, r in enumerate(results):
                    if r.region_type in ("text", "image"):
                        overlap = self._overlap_area(rev, r)
                        r_area = max(r.width * r.height, 1)
                        if overlap / r_area > 0.3:
                            to_remove.add(i)
            if to_remove:
                results = [r for i, r in enumerate(results) if i not in to_remove]
                print(f"[ImageAnalyzer] Removed {len(to_remove)} regions inside reverse banners")
            results.extend(reverse_regions)
            print(f"[ImageAnalyzer] Reverse-video banners: {len(reverse_regions)}")

        # 6. Per-region text color detection: check if each text region
        #    has light text on a dark background (not just full-width banners).
        self._detect_text_colors(gray, results)

        return results

    # ── Preprocessing ─────────────────────────────────────────────────

    def _get_binary(self, gray: np.ndarray) -> np.ndarray:
        """Create clean binary image using Otsu's threshold.
        Handles real-world images with varying contrast, JPEG artifacts, etc.
        No blur or morphological cleanup - they degrade thin lines (3px)."""
        # Otsu's method finds optimal threshold automatically
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        return binary

    # ── Line detection ───────────────────────────────────────────────

    def _detect_lines(self, gray: np.ndarray, exclude: List[DetectedRegion] = None) -> List[DetectedRegion]:
        """Detect horizontal and vertical lines, excluding regions in `exclude`."""
        results = []
        exclude = exclude or []
        try:
            img_h, img_w = gray.shape[:2]
            binary = self._binary_cache.copy()

            # Mask out excluded regions (e.g., barcodes)
            if exclude:
                mask = np.ones_like(binary) * 255
                for r in exclude:
                    pad = 4
                    cv2.rectangle(mask, (r.x - pad, r.y - pad),
                                  (r.x + r.width + pad, r.y + r.height + pad), 0, -1)
                binary = cv2.bitwise_and(binary, mask)

            # Minimum line length: 15% of image width/height
            min_hlen = int(img_w * 0.15)
            min_vlen = int(img_h * 0.08)
            max_thickness = max(8, int(min(img_w, img_h) * 0.01))
            # Edge margin: skip lines at image borders (artifacts from pasted images)
            edge_margin = max(5, int(min(img_w, img_h) * 0.01))

            # Detect horizontal lines
            h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (min_hlen, 1))
            h_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, h_kernel)
            h_contours, _ = cv2.findContours(h_lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in h_contours:
                x, y, w, h = cv2.boundingRect(cnt)
                if w >= min_hlen and h <= max_thickness:
                    # Skip border artifact lines at image edges
                    if y < edge_margin or y + h > img_h - edge_margin:
                        continue
                    results.append(DetectedRegion(
                        region_type="hline", x=x, y=y, width=w, height=h,
                        confidence=0.9, extra={"thickness": max(1, h)}
                    ))

            # Detect vertical lines
            v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, min_vlen))
            v_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, v_kernel)
            v_contours, _ = cv2.findContours(v_lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in v_contours:
                x, y, w, h = cv2.boundingRect(cnt)
                if h >= min_vlen and w <= max_thickness:
                    # Skip border artifact lines at image edges
                    if x < edge_margin or x + w > img_w - edge_margin:
                        continue
                    results.append(DetectedRegion(
                        region_type="vline", x=x, y=y, width=w, height=h,
                        confidence=0.9, extra={"thickness": max(1, w)}
                    ))
        except Exception as e:
            print(f"[ImageAnalyzer] Line detection error: {e}")
        return results

    def _merge_collinear_lines(self, lines: List[DetectedRegion], img_w: int, img_h: int) -> List[DetectedRegion]:
        """Merge nearby collinear line segments to recover fragmented frame/grid edges."""
        if not lines:
            return lines

        hlines = [l for l in lines if l.region_type == "hline"]
        vlines = [l for l in lines if l.region_type == "vline"]
        others = [l for l in lines if l.region_type not in ("hline", "vline")]

        axis_tol = max(2, int(min(img_w, img_h) * 0.003))
        gap_h = max(8, int(img_w * 0.02))
        gap_v = max(8, int(img_h * 0.02))

        def merge_horizontal(candidates: List[DetectedRegion]) -> List[DetectedRegion]:
            if not candidates:
                return []
            buckets = []
            for ln in sorted(candidates, key=lambda r: (r.y, r.x)):
                placed = False
                for bucket in buckets:
                    if abs(ln.y - bucket["axis"]) <= axis_tol:
                        bucket["items"].append(ln)
                        bucket["axis_vals"].append(ln.y)
                        bucket["axis"] = int(np.median(bucket["axis_vals"]))
                        placed = True
                        break
                if not placed:
                    buckets.append({"axis": ln.y, "axis_vals": [ln.y], "items": [ln]})

            merged = []
            for bucket in buckets:
                parts = sorted(bucket["items"], key=lambda r: r.x)
                cur = parts[0]
                cur_start = cur.x
                cur_end = cur.x + cur.width
                cur_h = cur.height
                cur_conf = cur.confidence
                for part in parts[1:]:
                    part_start = part.x
                    part_end = part.x + part.width
                    long_span = ((cur_end - cur_start) > img_w * 0.2) or (part.width > img_w * 0.2)
                    allowed_gap = max(gap_h, int(img_w * 0.18)) if long_span else gap_h
                    if part_start <= cur_end + allowed_gap:
                        cur_end = max(cur_end, part_end)
                        cur_h = max(cur_h, part.height)
                        cur_conf = max(cur_conf, part.confidence)
                    else:
                        merged.append(DetectedRegion(
                            region_type="hline",
                            x=int(cur_start), y=int(bucket["axis"]),
                            width=int(cur_end - cur_start), height=int(max(1, cur_h)),
                            confidence=cur_conf,
                            extra={"thickness": int(max(1, cur_h))}
                        ))
                        cur_start = part_start
                        cur_end = part_end
                        cur_h = part.height
                        cur_conf = part.confidence
                merged.append(DetectedRegion(
                    region_type="hline",
                    x=int(cur_start), y=int(bucket["axis"]),
                    width=int(cur_end - cur_start), height=int(max(1, cur_h)),
                    confidence=cur_conf,
                    extra={"thickness": int(max(1, cur_h))}
                ))
            return merged

        def merge_vertical(candidates: List[DetectedRegion]) -> List[DetectedRegion]:
            if not candidates:
                return []
            buckets = []
            for ln in sorted(candidates, key=lambda r: (r.x, r.y)):
                placed = False
                for bucket in buckets:
                    if abs(ln.x - bucket["axis"]) <= axis_tol:
                        bucket["items"].append(ln)
                        bucket["axis_vals"].append(ln.x)
                        bucket["axis"] = int(np.median(bucket["axis_vals"]))
                        placed = True
                        break
                if not placed:
                    buckets.append({"axis": ln.x, "axis_vals": [ln.x], "items": [ln]})

            merged = []
            for bucket in buckets:
                parts = sorted(bucket["items"], key=lambda r: r.y)
                cur = parts[0]
                cur_start = cur.y
                cur_end = cur.y + cur.height
                cur_w = cur.width
                cur_conf = cur.confidence
                for part in parts[1:]:
                    part_start = part.y
                    part_end = part.y + part.height
                    long_span = ((cur_end - cur_start) > img_h * 0.2) or (part.height > img_h * 0.2)
                    allowed_gap = max(gap_v, int(img_h * 0.22)) if long_span else gap_v
                    if part_start <= cur_end + allowed_gap:
                        cur_end = max(cur_end, part_end)
                        cur_w = max(cur_w, part.width)
                        cur_conf = max(cur_conf, part.confidence)
                    else:
                        merged.append(DetectedRegion(
                            region_type="vline",
                            x=int(bucket["axis"]), y=int(cur_start),
                            width=int(max(1, cur_w)), height=int(cur_end - cur_start),
                            confidence=cur_conf,
                            extra={"thickness": int(max(1, cur_w))}
                        ))
                        cur_start = part_start
                        cur_end = part_end
                        cur_w = part.width
                        cur_conf = part.confidence
                merged.append(DetectedRegion(
                    region_type="vline",
                    x=int(bucket["axis"]), y=int(cur_start),
                    width=int(max(1, cur_w)), height=int(cur_end - cur_start),
                    confidence=cur_conf,
                    extra={"thickness": int(max(1, cur_w))}
                ))
            return merged

        merged_h = merge_horizontal(hlines)
        merged_v = merge_vertical(vlines)
        return merged_h + merged_v + others

    # ── Box detection ────────────────────────────────────────────────

    def _detect_boxes(self, gray: np.ndarray, exclude: List[DetectedRegion] = None) -> List[DetectedRegion]:
        """Detect rectangular box outlines, excluding regions in `exclude`."""
        results = []
        exclude = exclude or []
        try:
            img_h, img_w = gray.shape[:2]
            binary = self._binary_cache.copy()

            # Mask out excluded regions
            if exclude:
                mask = np.ones_like(binary) * 255
                for r in exclude:
                    pad = 10
                    cv2.rectangle(mask, (r.x - pad, r.y - pad),
                                  (r.x + r.width + pad, r.y + r.height + pad), 0, -1)
                binary = cv2.bitwise_and(binary, mask)

            contours, hierarchy = cv2.findContours(binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            if hierarchy is None:
                return results

            min_area = int(img_w * img_h * 0.003)
            max_area = int(img_w * img_h * 0.7)

            for i, cnt in enumerate(contours):
                x, y, w, h = cv2.boundingRect(cnt)
                area = w * h
                if area < min_area or area > max_area:
                    continue
                if w < 20 or h < 20:
                    continue
                # Skip boxes that span nearly the entire image (border artifacts)
                if w > img_w * 0.9 and h > img_h * 0.9:
                    continue

                epsilon = 0.02 * cv2.arcLength(cnt, True)
                approx = cv2.approxPolyDP(cnt, epsilon, True)
                if len(approx) < 4 or len(approx) > 6:
                    continue

                cnt_area = cv2.contourArea(cnt)
                if area == 0:
                    continue
                rectangularity = cnt_area / area
                if rectangularity < 0.85:
                    continue

                roi = binary[y:y + h, x:x + w]
                density = np.sum(roi > 0) / max(area, 1)

                if density < 0.4:
                    # Hollow box - measure actual border thickness by scanning
                    thickness = self._measure_border_thickness(roi)
                    if thickness is not None and thickness < min(w, h) // 3:
                        results.append(DetectedRegion(
                            region_type="box",
                            x=x, y=y, width=w, height=h,
                            confidence=0.85,
                            extra={"thickness": thickness, "filled": False}
                        ))

            # Deduplicate: if two boxes overlap >80%, keep the one with larger area
            results = self._deduplicate_boxes(results)

        except Exception as e:
            print(f"[ImageAnalyzer] Box detection error: {e}")
        return results

    def _measure_border_thickness(self, roi: np.ndarray) -> int | None:
        """Measure actual border thickness by scanning inward from edges.
        Uses multiple scan points per edge for robustness against noise."""
        h, w = roi.shape[:2]
        if h < 6 or w < 6:
            return None

        thicknesses = []
        # Scan at 3 points per edge (25%, 50%, 75%) for robustness
        scan_fracs = [0.25, 0.5, 0.75]

        for frac in scan_fracs:
            px = int(w * frac)
            py = int(h * frac)

            # Scan from top edge inward
            for y in range(min(h // 2, 50)):
                if roi[y, px] == 0:
                    if y > 0:
                        thicknesses.append(y)
                    break

            # Scan from bottom edge inward
            for y in range(h - 1, max(h // 2, 0), -1):
                if roi[y, px] == 0:
                    if (h - 1 - y) > 0:
                        thicknesses.append(h - 1 - y)
                    break

            # Scan from left edge inward
            for x in range(min(w // 2, 50)):
                if roi[py, x] == 0:
                    if x > 0:
                        thicknesses.append(x)
                    break

            # Scan from right edge inward
            for x in range(w - 1, max(w // 2, 0), -1):
                if roi[py, x] == 0:
                    if (w - 1 - x) > 0:
                        thicknesses.append(w - 1 - x)
                    break

        if not thicknesses:
            return None

        # Use median to be robust against noise
        thicknesses.sort()
        return max(1, thicknesses[len(thicknesses) // 2])

    def _deduplicate_boxes(self, boxes: List[DetectedRegion]) -> List[DetectedRegion]:
        """Remove near-duplicate boxes. Two boxes are duplicates if they have
        very similar position and size (within tolerance), NOT just because
        one contains the other (nested boxes are valid)."""
        if len(boxes) <= 1:
            return boxes
        keep = []
        used = set()
        for i, box in enumerate(boxes):
            if i in used:
                continue
            keep.append(box)
            for j in range(i + 1, len(boxes)):
                if j in used:
                    continue
                other = boxes[j]
                # Check if positions and sizes are nearly identical
                if (abs(box.x - other.x) < 10 and abs(box.y - other.y) < 10 and
                        abs(box.width - other.width) < 15 and abs(box.height - other.height) < 15):
                    used.add(j)
        return keep

    # ── Barcode detection ────────────────────────────────────────────

    def _detect_barcodes(self, image: np.ndarray, gray: np.ndarray) -> List[DetectedRegion]:
        """Detect barcodes and QR codes."""
        results = []

        if self._has_pyzbar:
            pyzbar_results = self._detect_with_pyzbar(image, gray)
            results.extend(pyzbar_results)

        qr_results = self._detect_qr_opencv(gray)
        for qr in qr_results:
            if not self._overlaps_any(qr, results):
                results.append(qr)

        heuristic_results = self._detect_barcode_heuristic(gray)
        for h in heuristic_results:
            if not self._overlaps_any(h, results):
                results.append(h)

        return self._deduplicate_barcodes(results)

    def _deduplicate_barcodes(self, regions: List[DetectedRegion]) -> List[DetectedRegion]:
        """Remove duplicate barcode/QR detections coming from multiple detectors."""
        if len(regions) <= 1:
            return regions

        def score(r: DetectedRegion) -> tuple:
            area = max(r.width * r.height, 1)
            has_data = 1 if (r.data and r.data.strip()) else 0
            known_type = 1 if (r.barcode_type and r.barcode_type != "unknown") else 0
            return (has_data, known_type, r.confidence, area)

        ordered = sorted(regions, key=score, reverse=True)
        keep: List[DetectedRegion] = []

        for cand in ordered:
            duplicate = False
            cand_area = max(cand.width * cand.height, 1)
            for ex in keep:
                overlap = self._overlap_area(cand, ex)
                if overlap <= 0:
                    continue
                ex_area = max(ex.width * ex.height, 1)
                union = cand_area + ex_area - overlap
                iou = overlap / max(union, 1)
                overlap_small = overlap / min(cand_area, ex_area)

                same_family = (
                    cand.region_type == ex.region_type or
                    {cand.region_type, ex.region_type} <= {"barcode", "qrcode"}
                )
                same_payload = bool(cand.data and ex.data and cand.data == ex.data)

                if same_family and (iou > 0.55 or overlap_small > 0.75):
                    duplicate = True
                    break
                if same_payload and overlap_small > 0.35:
                    duplicate = True
                    break
                if (cand.region_type == ex.region_type == "barcode" and
                        overlap_small > 0.5 and
                        ((not cand.data) or (not ex.data))):
                    duplicate = True
                    break

            if not duplicate:
                keep.append(cand)

        return keep

    def _detect_with_pyzbar(self, image: np.ndarray, gray: np.ndarray) -> List[DetectedRegion]:
        """Detect barcodes using pyzbar library - tries multiple preprocessing approaches."""
        results = []
        try:
            from pyzbar import pyzbar

            decoded = pyzbar.decode(image)
            if not decoded:
                decoded = pyzbar.decode(gray)
            if not decoded:
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                decoded = pyzbar.decode(clahe.apply(gray))
            if not decoded:
                thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                                cv2.THRESH_BINARY, 51, 10)
                decoded = pyzbar.decode(thresh)
            if not decoded and max(gray.shape) > 1500:
                scale = 1000.0 / max(gray.shape)
                small = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
                decoded = pyzbar.decode(small)
                for obj in decoded:
                    x, y, w, h = self._pyzbar_rect(obj)
                    if w <= 0 or h <= 0:
                        continue
                    results.append(self._pyzbar_to_region(obj, int(x / scale), int(y / scale),
                                                          int(w / scale), int(h / scale)))
                return results
            # Scale UP small images (pasted previews may have small barcodes/QR)
            if not decoded and max(gray.shape) < 800:
                scale = 1200.0 / max(gray.shape)
                big = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
                decoded = pyzbar.decode(big)
                for obj in decoded:
                    x, y, w, h = self._pyzbar_rect(obj)
                    if w <= 0 or h <= 0:
                        continue
                    results.append(self._pyzbar_to_region(obj, int(x / scale), int(y / scale),
                                                          int(w / scale), int(h / scale)))
                if results:
                    print(f"[ImageAnalyzer] pyzbar found {len(results)} barcodes/QR (upscaled)")
                    return results
            # Try Otsu binary (helps with anti-aliased pasted images)
            if not decoded:
                _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                decoded = pyzbar.decode(otsu)

            for obj in decoded:
                x, y, w, h = self._pyzbar_rect(obj)
                if w <= 0 or h <= 0:
                    continue
                results.append(self._pyzbar_to_region(obj, x, y, w, h))
            print(f"[ImageAnalyzer] pyzbar found {len(results)} barcodes/QR")
        except Exception as e:
            print(f"[ImageAnalyzer] pyzbar error: {e}")
        return results

    def _pyzbar_rect(self, obj) -> tuple:
        """Get bounding rect from pyzbar result, using polygon as fallback for 0x0 rects."""
        x, y, w, h = obj.rect
        if w > 0 and h > 0:
            return (x, y, w, h)
        # Fallback: compute from polygon points
        if obj.polygon:
            pts = [(p.x, p.y) for p in obj.polygon]
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            x = min(xs)
            y = min(ys)
            w = max(xs) - x
            h = max(ys) - y
        return (x, y, w, h)

    def _pyzbar_to_region(self, obj, x, y, w, h) -> DetectedRegion:
        data = obj.data.decode('utf-8', errors='replace')
        bc_type = obj.type
        if bc_type == 'QRCODE':
            return DetectedRegion("qrcode", x=x, y=y, width=w, height=h,
                                  data=data, barcode_type="qrcode", confidence=1.0)
        region = DetectedRegion("barcode", x=x, y=y, width=w, height=h,
                              data=data, barcode_type=self._pyzbar_type_to_zpl(bc_type),
                              confidence=1.0)
        region.extra["pyzbar_detected"] = True
        return region

    def _detect_qr_opencv(self, gray: np.ndarray) -> List[DetectedRegion]:
        """Detect QR codes using OpenCV's built-in detector with multiple preprocessing."""
        results = []
        try:
            detector = cv2.QRCodeDetector()
            # Try multiple preprocessing approaches
            images_to_try = [gray]
            # Otsu threshold
            _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            images_to_try.append(otsu)
            # CLAHE enhanced
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            images_to_try.append(clahe.apply(gray))
            # Resized (if large)
            if max(gray.shape) > 1000:
                scale = 800.0 / max(gray.shape)
                small = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
                images_to_try.append(small)
            # Scale UP (if small - pasted previews)
            if max(gray.shape) < 800:
                scale = 1200.0 / max(gray.shape)
                big = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
                images_to_try.append(big)

            for img in images_to_try:
                data, points, _ = detector.detectAndDecode(img)
                if data and points is not None:
                    pts = points[0].astype(int)
                    x, y = int(pts[:, 0].min()), int(pts[:, 1].min())
                    w = int(pts[:, 0].max()) - x
                    h = int(pts[:, 1].max()) - y
                    # If detected on resized image, scale back
                    if img is not gray and img.shape != gray.shape:
                        sy = gray.shape[0] / img.shape[0]
                        sx = gray.shape[1] / img.shape[1]
                        x, y = int(x * sx), int(y * sy)
                        w, h = int(w * sx), int(h * sy)
                    if w > 5 and h > 5:
                        results.append(DetectedRegion("qrcode", x=x, y=y, width=w, height=h,
                                                      data=data, barcode_type="qrcode", confidence=1.0))
                        break
        except Exception:
            pass
        return results

    def _detect_barcode_heuristic(self, gray: np.ndarray) -> List[DetectedRegion]:
        """Detect barcode-like patterns using morphological operations."""
        results = []
        try:
            img_h, img_w = gray.shape[:2]
            base = max(img_w, img_h) / 500.0
            k_w = max(21, int(21 * base)) | 1
            k_h = max(7, int(7 * base)) | 1
            blur_k = max(9, int(9 * base)) | 1

            grad_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=-1)
            grad_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=-1)
            gradient = cv2.subtract(cv2.convertScaleAbs(grad_x), cv2.convertScaleAbs(grad_y))

            blurred = cv2.GaussianBlur(gradient, (blur_k, blur_k), 0)
            _, thresh = cv2.threshold(blurred, 40, 255, cv2.THRESH_BINARY)

            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k_w, k_h))
            closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
            erode_iter = max(2, int(4 * base))
            closed = cv2.erode(closed, None, iterations=erode_iter)
            closed = cv2.dilate(closed, None, iterations=erode_iter)

            contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            min_area = max(3000, int(img_w * img_h * 0.005))
            min_h = max(60, int(img_h * 0.06))

            binary = self._binary_cache
            for cnt in contours:
                x, y, w, h = cv2.boundingRect(cnt)
                # Strict: aspect ratio > 2.5, minimum height/width, significant area
                if w * h > min_area and w / max(h, 1) > 2.5 and h > min_h and w > 80:
                    if self._verify_barcode_pattern(gray, x, y, w, h):
                        # Reject if region is a dense dark band (banner/header)
                        # Barcodes have ~50% black, banners are much denser
                        roi = binary[y:y+h, x:x+w]
                        density = np.sum(roi > 0) / max(roi.size, 1)
                        if density > 0.75:
                            continue  # Too dense - likely a banner, not a barcode
                        results.append(DetectedRegion("barcode", x=x, y=y, width=w, height=h,
                                                      barcode_type="unknown", confidence=0.6))
            print(f"[ImageAnalyzer] Heuristic found {len(results)} barcode candidates")
        except Exception as e:
            print(f"[ImageAnalyzer] Heuristic barcode error: {e}")
        return results

    def _verify_barcode_pattern(self, gray: np.ndarray, x: int, y: int, w: int, h: int) -> bool:
        """Verify region has barcode-like vertical stripe pattern.
        Checks multiple rows and requires consistent high transition counts."""
        try:
            min_transitions = max(20, w // 12)
            passing_rows = 0
            # Check 5 rows across the region height
            for frac in [0.25, 0.35, 0.5, 0.65, 0.75]:
                ry = min(y + int(h * frac), gray.shape[0] - 1)
                row = gray[ry, x:x + w]
                _, binary_row = cv2.threshold(row.reshape(1, -1), 0, 255,
                                              cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                transitions = np.sum(np.abs(np.diff(binary_row.flatten().astype(int))) > 128)
                if transitions >= min_transitions:
                    passing_rows += 1
            # At least 4 of 5 rows must have barcode-like pattern
            return passing_rows >= 4
        except Exception:
            return False

    # ── Text detection ───────────────────────────────────────────────

    def _detect_text(self, image: np.ndarray, gray: np.ndarray,
                     existing: List[DetectedRegion]) -> List[DetectedRegion]:
        """Detect text using OCR engines.
        Tesseract: uses word-level grouped detection (best accuracy).
        RapidOCR/EasyOCR: uses their native detection + morphology fallback.
        Falls back to multi-engine OCR + morphology if primary gives < 2 results."""
        img_h, img_w = gray.shape[:2]

        text_regions = []

        # Tesseract has word-level image_to_data() which gives best results
        # with the grouped detection algorithm. RapidOCR/EasyOCR return line-level
        # results, so they work better through _detect_text_fallback path which
        # uses their native detection parsers (_detect_text_rapidocr/_detect_text_easyocr).
        if self._has_tesseract:
            text_regions = self._detect_text_grouped(gray, existing)

        # Fallback: multi-engine OCR + morphology if grouped detection gave < 2 results
        if len(text_regions) < 2:
            fallback = self._detect_text_fallback(image, gray, existing)
            for r in fallback:
                if not self._overlaps_any(r, text_regions):
                    text_regions.append(r)

        # Remove text near barcodes (human-readable barcode text)
        barcode_regions = [r for r in existing if r.region_type in ("barcode", "qrcode")]
        if barcode_regions:
            text_regions = self._remove_barcode_text(text_regions, barcode_regions)

        # Light cleanup and dedup
        text_regions = self._clean_and_dedup_text(text_regions, img_h, img_w)
        return text_regions

    def _detect_text_grouped(self, gray: np.ndarray,
                              existing: List[DetectedRegion]) -> List[DetectedRegion]:
        """Detect text using Tesseract PSM 6 word-level with row/column grouping.
        Based on qwen.py approach: get individual word positions, then group into lines."""
        img_h, img_w = gray.shape[:2]

        # Step 1: Get word-level blocks from Tesseract
        word_blocks = self._get_word_blocks(gray)
        print(f"[ImageAnalyzer] OCR word blocks: {len(word_blocks)}")

        if not word_blocks:
            return []

        # Step 2: Filter out words overlapping with existing (barcode) regions
        filtered = []
        for b in word_blocks:
            r = DetectedRegion("text", x=b['x'], y=b['y'], width=b['w'], height=b['h'])
            if not self._overlaps_any(r, existing):
                filtered.append(b)

        if not filtered:
            return []

        # Step 3: Cluster into rows by Y position
        row_threshold = max(10, int(img_h * 0.015))  # ~1.5% of image height
        y_coords = [b['y'] for b in filtered]
        row_positions = self._cluster_values(y_coords, threshold=row_threshold)

        # Step 4: Assign blocks to closest row
        rows = defaultdict(list)
        for block in filtered:
            closest_row = min(row_positions, key=lambda ry: abs(ry - block['y']))
            rows[closest_row].append(block)

        # Step 5: Within each row, split into columns by large X gap
        # Use adaptive gap: larger of character-height-based or absolute minimum
        text_regions = []

        for row_y in sorted(rows.keys()):
            row_blocks = sorted(rows[row_y], key=lambda b: b['x'])

            # Adaptive column gap: use average character height * 2 for this row
            # Balance: detect multi-column layouts without over-splitting single columns
            avg_h = max(10, int(np.mean([b['h'] for b in row_blocks])))
            col_gap = max(int(avg_h * 2), 35)  # Min 35px gap to split columns

            # Split into columns by X gap
            columns = [[row_blocks[0]]]
            for i in range(1, len(row_blocks)):
                prev = columns[-1][-1]
                curr = row_blocks[i]
                gap = curr['x'] - (prev['x'] + prev['w'])
                if gap > col_gap:
                    columns.append([curr])
                else:
                    columns[-1].append(curr)

            # Each column becomes a text region
            for col in columns:
                text = " ".join(b['text'] for b in col)
                text = text.replace('^', '').replace('~', '')
                # Replace non-ASCII chars (em-dash, etc.) with ASCII equivalents
                text = text.replace('\u2014', '-').replace('\u2013', '-')
                text = text.replace('\u2018', "'").replace('\u2019', "'")
                text = text.replace('\u201c', '"').replace('\u201d', '"')
                # Remove any remaining non-printable/non-ASCII
                text = ''.join(c if 32 <= ord(c) < 127 else '-' if ord(c) > 127 else '' for c in text)
                text = text.strip()
                if not text:
                    continue

                x = col[0]['x']
                y = min(b['y'] for b in col)
                right = max(b['x'] + b['w'] for b in col)
                bottom = max(b['y'] + b['h'] for b in col)
                w = right - x
                h = bottom - y
                
                # CRITICAL FIX: Tesseract reports INK height (~75% of ZPL font cell height).
                # Labelary renders ink at ~75% of specified font_h.
                # Using ink_h directly as font_h → renders only 75%×75% = 56% of original.
                # Multiply by 4/3 to recover the original font cell height.
                h = round(h * 4 / 3)

                # Post-merge noise check: reject garbled multi-icon text
                if self._is_noise_text(text, w, h, img_h):
                    continue

                text_regions.append(DetectedRegion(
                    "text", x=x, y=y, width=w, height=h,
                    data=text, confidence=0.8
                ))

        print(f"[ImageAnalyzer] Text lines after grouping: {len(text_regions)}")
        return text_regions

    def _measure_ink_bounds(self, binary: np.ndarray, x: int, y: int, w: int, h: int) -> dict:
        """Measure actual ink pixel bounds in binary image.
        
        Tesseract's bounding box often misses parts of text (especially descenders).
        This function finds the true ink extent within the detected region plus
        a small padding to catch descenders.
        
        Returns:
            dict with 'y_top', 'y_bottom', 'ink_height' or None if no ink found.
        """
        try:
            # Small padding only for descenders (below the text)
            pad_y_down = max(15, int(h * 0.4))  # 40% or at least 15px below
            pad_y_up = max(5, int(h * 0.1))     # Small padding above
            pad_x = max(5, int(w * 0.02))       # Minimal x padding
            
            x1 = max(0, x - pad_x)
            y1 = max(0, y - pad_y_up)
            x2 = min(binary.shape[1], x + w + pad_x)
            y2 = min(binary.shape[0], y + h + pad_y_down)
            
            if x2 <= x1 or y2 <= y1:
                return None
            
            # Extract ROI
            roi = binary[y1:y2, x1:x2]
            
            # Find ink pixels
            if np.max(roi) <= 1:
                ink_y, ink_x = np.where(roi > 0)
            else:
                ink_y, ink_x = np.where(roi > 128)
            
            if len(ink_y) == 0:
                return None
            
            # Get vertical bounds
            y_top_rel = int(np.min(ink_y))
            y_bottom_rel = int(np.max(ink_y))
            y_top = y1 + y_top_rel
            y_bottom = y1 + y_bottom_rel
            ink_height = y_bottom - y_top + 1
            
            # Validate: measured height should be reasonable
            if ink_height < h * 0.8:  # Not useful if similar or smaller
                return None
            if ink_height > h * 2.5:  # Way too large (multiple lines?)
                return None
            
            # Additional check: ink should be mostly within the original region
            # to avoid capturing adjacent lines
            original_bottom = y + h
            ink_below_original = max(0, y_bottom - original_bottom)
            
            # If ink extends too far below, it's probably capturing next line
            if ink_below_original > h * 0.8:
                return None
                
            return {
                'y_top': y_top,
                'y_bottom': y_bottom,
                'ink_height': ink_height
            }
            
        except Exception:
            return None

    def _get_word_blocks(self, gray: np.ndarray) -> list:
        """Get word-level text blocks using available OCR engines.
        Priority: RapidOCR → EasyOCR → Tesseract.
        Scales image 2x for better OCR accuracy on small text."""
        scale = 2.0
        big = cv2.resize(gray, None, fx=scale, fy=scale,
                         interpolation=cv2.INTER_CUBIC)
        img_h = gray.shape[0]
        blocks = []

        # 1. Try RapidOCR first (fastest, pure pip)
        if self._has_ocr:
            engine = self._get_ocr_reader()
            if engine is not None:
                try:
                    result, _ = engine(big)
                    if result:
                        blocks = self._ocr_results_to_word_blocks(result, scale, img_h)
                        if blocks:
                            return blocks
                except Exception as e:
                    print(f"[ImageAnalyzer] RapidOCR word blocks error: {e}")

        # 2. Try EasyOCR (pure pip)
        if self._has_easyocr:
            reader = self._get_easyocr_reader()
            if reader is not None:
                try:
                    results = reader.readtext(big)
                    if results:
                        blocks = self._ocr_results_to_word_blocks(results, scale, img_h)
                        if blocks:
                            return blocks
                except Exception as e:
                    print(f"[ImageAnalyzer] EasyOCR word blocks error: {e}")

        # 3. Tesseract fallback (requires system install)
        if self._has_tesseract:
            try:
                import pytesseract
                pytesseract.pytesseract.tesseract_cmd = self._tesseract_path

                custom_config = r'--oem 3 --psm 6'
                data = pytesseract.image_to_data(
                    big, output_type=pytesseract.Output.DICT, config=custom_config
                )

                for i in range(len(data['text'])):
                    text = data['text'][i].strip()
                    conf = int(data['conf'][i])
                    if text and conf > 30:
                        x = int(data['left'][i] / scale)
                        y = int(data['top'][i] / scale)
                        w = int(data['width'][i] / scale)
                        h = int(data['height'][i] / scale)
                        if w < 3 or h < 3:
                            continue
                        if self._is_noise_text(text, w, h, img_h):
                            continue
                        blocks.append({
                            'text': text, 'x': x, 'y': y, 'w': w, 'h': h, 'conf': conf
                        })
                return blocks
            except Exception as e:
                print(f"[ImageAnalyzer] Tesseract word blocks error: {e}")

        return blocks

    @staticmethod
    def _cluster_values(values, threshold=20):
        """Cluster nearby values together (for row grouping by Y position)."""
        if not values:
            return []
        values = sorted(values)
        clusters = [[values[0]]]
        for val in values[1:]:
            if val - clusters[-1][-1] < threshold:
                clusters[-1].append(val)
            else:
                clusters.append([val])
        return [int(np.mean(cluster)) for cluster in clusters]

    def _detect_text_fallback(self, image: np.ndarray, gray: np.ndarray,
                               existing: List[DetectedRegion]) -> List[DetectedRegion]:
        """Fallback text detection using multi-engine OCR + morphology."""
        has_any_ocr = self._has_ocr or self._has_easyocr or self._has_tesseract
        img_h, img_w = gray.shape[:2]

        ocr_regions = []
        if has_any_ocr:
            ocr_regions = self._detect_text_ocr(image, gray, existing)

        morph_regions = self._detect_text_morphological(gray, existing)

        # Split large morph regions into lines
        split_morph = []
        for mr in morph_regions:
            if mr.height > img_h * 0.06 and mr.height > 40:
                sub_regions = self._split_text_region_into_lines(gray, mr)
                if len(sub_regions) > 1:
                    split_morph.extend(sub_regions)
                    continue
            split_morph.append(mr)
        morph_regions = split_morph

        merged = list(ocr_regions)
        for mr in morph_regions:
            if not self._overlaps_any(mr, merged):
                if has_any_ocr and not mr.data:
                    text = self._ocr_single_region(gray, mr)
                    if text:
                        if self._is_noise_text(text, mr.width, mr.height, img_h):
                            continue
                        mr.data = text
                        mr.confidence = 0.8
                if not mr.data and (mr.height < 10 or mr.width * mr.height < 500):
                    continue
                merged.append(mr)
        return merged

    def _detect_text_ocr(self, image: np.ndarray, gray: np.ndarray,
                         existing: List[DetectedRegion]) -> List[DetectedRegion]:
        """Detect text using all available OCR engines and combine results.
        Priority: RapidOCR → EasyOCR → Tesseract."""
        img_h, img_w = gray.shape[:2]

        # Step 1: Run RapidOCR (fastest, pure pip)
        rapid_results = self._detect_text_rapidocr(image, gray, existing)
        combined = list(rapid_results)

        # Step 2: EasyOCR (catches anti-aliased text RapidOCR misses)
        if self._has_easyocr and len(combined) < 3:
            easy_results = self._detect_text_easyocr(image, gray, existing)
            for er in easy_results:
                if not self._overlaps_any(er, combined):
                    combined.append(er)
            print(f"[ImageAnalyzer] EasyOCR found {len(easy_results)} text regions "
                  f"(combined total: {len(combined)})")

        # Step 3: Tesseract fallback (if available and still sparse)
        if self._has_tesseract and len(combined) < 3:
            tess_results = self._detect_text_tesseract(gray, existing)
            new_from_tess = 0
            for tr in tess_results:
                if self._overlaps_any(tr, combined):
                    continue
                if tr.data and any(
                    c.data and tr.data in c.data
                    for c in combined
                ):
                    continue
                combined.append(tr)
                new_from_tess += 1
            print(f"[ImageAnalyzer] Tesseract found {len(tess_results)} text regions "
                  f"({new_from_tess} new after merge)")

        return combined

    def _clean_for_ocr(self, gray: np.ndarray) -> list:
        """Generate cleaned preprocessing variants for OCR.
        Upscales small images first, then uses erode→dilate to remove noise.
        Returns list of (name, image) tuples."""
        # Step 1: Upscale small images so erode→dilate doesn't destroy thin text
        h, w = gray.shape[:2]
        upscaled = gray
        if max(h, w) < 300:
            scale = 300.0 / max(h, w)
            upscaled = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

        images = [("original", upscaled)]

        # Step 2: Binary (Otsu)
        _, binary = cv2.threshold(upscaled, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        images.append(("binary", binary))

        # Step 3: Erode→dilate on inverted binary (thin kills noise, dilate restores chars)
        inv = cv2.bitwise_not(binary)
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        eroded = cv2.erode(inv, k, iterations=1)
        dilated = cv2.dilate(eroded, k, iterations=1)
        images.append(("erode-dilate", cv2.bitwise_not(dilated)))

        # Step 4: Sharpen (helps with anti-aliased text from screen captures/pastes)
        sharp_k = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]], dtype=np.float32)
        sharpened = cv2.filter2D(upscaled, -1, sharp_k)
        images.append(("sharpened", sharpened))

        return images

    def _detect_text_tesseract(self, gray: np.ndarray,
                               existing: List[DetectedRegion]) -> List[DetectedRegion]:
        """Detect text using Tesseract OCR with denoising + adaptive threshold (minimax approach)."""
        try:
            import pytesseract
            pytesseract.pytesseract.tesseract_cmd = self._tesseract_path
        except Exception:
            return []

        results = []
        try:
            img_h, img_w = gray.shape[:2]

            # Preprocessing from minimax.py: denoise + adaptive threshold
            denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
            processed = cv2.adaptiveThreshold(
                denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY, 11, 2
            )

            # PSM 11 = sparse text (find as much text as possible)
            custom_config = r'--oem 3 --psm 11'
            data = pytesseract.image_to_data(
                processed, config=custom_config,
                output_type=pytesseract.Output.DICT
            )

            n_boxes = len(data['text'])
            for i in range(n_boxes):
                text = data['text'][i].strip()
                conf = float(data['conf'][i])
                if conf < 40 or not text:
                    continue

                x = data['left'][i]
                y = data['top'][i]
                w = data['width'][i]
                h = data['height'][i]
                if w < 3 or h < 3:
                    continue
                # Skip oversized regions
                if h > img_h * 0.15 or w > img_w * 0.8:
                    continue
                # Skip noise text (tick marks, brackets, etc.)
                if self._is_noise_text(text, w, h, img_h):
                    continue

                region = DetectedRegion("text", x=x, y=y, width=w, height=h,
                                        data=text, confidence=conf / 100.0)
                if not self._overlaps_any(region, existing):
                    results.append(region)

            # Merge adjacent word-level results into lines
            results = self._merge_tesseract_words(results, img_w)
        except Exception as e:
            print(f"[ImageAnalyzer] Tesseract error: {e}")
            traceback.print_exc()
        return results

    def _merge_tesseract_words(self, words: List[DetectedRegion], img_w: int) -> List[DetectedRegion]:
        """Merge Tesseract word-level results into text lines (same y-level, close x)."""
        if not words:
            return words
        # Sort by y then x
        words.sort(key=lambda r: (r.y, r.x))
        merged = []
        current = words[0]

        for w in words[1:]:
            # Same line if y-centers are close and x-gap is small
            cy1 = current.y + current.height / 2
            cy2 = w.y + w.height / 2
            gap_x = w.x - (current.x + current.width)
            line_h = max(current.height, w.height)

            if abs(cy1 - cy2) < line_h * 0.6 and gap_x < line_h * 1.2:
                # Merge: extend current to include w
                new_x = min(current.x, w.x)
                new_y = min(current.y, w.y)
                new_right = max(current.x + current.width, w.x + w.width)
                new_bottom = max(current.y + current.height, w.y + w.height)
                current = DetectedRegion(
                    "text", x=new_x, y=new_y,
                    width=new_right - new_x, height=new_bottom - new_y,
                    data=current.data + " " + w.data,
                    confidence=min(current.confidence, w.confidence)
                )
            else:
                merged.append(current)
                current = w
        merged.append(current)
        return merged

    def _detect_text_rapidocr(self, image: np.ndarray, gray: np.ndarray,
                              existing: List[DetectedRegion]) -> List[DetectedRegion]:
        """Detect and recognize text using RapidOCR with multiple preprocessing attempts."""
        engine = self._get_ocr_reader()
        if engine is None:
            return []

        try:
            img_h, img_w = gray.shape[:2]
            scale = 1.0

            # Prepare base image - scale to good OCR size range
            base_img = image if len(image.shape) == 3 else gray
            max_dim = max(img_h, img_w)
            if max_dim > 1500:
                scale = 1500.0 / max_dim
                new_w, new_h = int(img_w * scale), int(img_h * scale)
                base_img = cv2.resize(base_img, (new_w, new_h), interpolation=cv2.INTER_AREA)
                print(f"[ImageAnalyzer] Downscaled for OCR: {img_w}x{img_h} -> {new_w}x{new_h}")
            elif max_dim < 600:
                scale = 800.0 / max_dim
                new_w, new_h = int(img_w * scale), int(img_h * scale)
                base_img = cv2.resize(base_img, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
                print(f"[ImageAnalyzer] Upscaled for OCR: {img_w}x{img_h} -> {new_w}x{new_h}")

            gray_scaled = cv2.cvtColor(base_img, cv2.COLOR_BGR2GRAY) if len(base_img.shape) == 3 else base_img
            images_to_try = self._clean_for_ocr(gray_scaled)

            best_results = []
            for name, ocr_img in images_to_try:
                ocr_results, _ = engine(ocr_img)
                if ocr_results is None:
                    continue

                current = self._parse_ocr_results(ocr_results, scale, img_h, img_w, existing)
                print(f"[ImageAnalyzer] RapidOCR ({name}) found {len(ocr_results)} items -> {len(current)} valid")

                if len(current) > len(best_results):
                    best_results = current

                if name == "original" and len(current) >= 3:
                    break

            return best_results
        except Exception as e:
            print(f"[ImageAnalyzer] RapidOCR error: {e}")
            traceback.print_exc()
        return []

    def _detect_text_easyocr(self, image: np.ndarray, gray: np.ndarray,
                             existing: List[DetectedRegion]) -> List[DetectedRegion]:
        """Detect text using EasyOCR with dilate→erode cleaned preprocessing."""
        reader = self._get_easyocr_reader()
        if reader is None:
            return []

        try:
            img_h, img_w = gray.shape[:2]
            scale = 1.0

            # Prepare base image
            base_img = gray.copy()
            max_dim = max(img_h, img_w)
            if max_dim > 1500:
                scale = 1500.0 / max_dim
                new_w, new_h = int(img_w * scale), int(img_h * scale)
                base_img = cv2.resize(base_img, (new_w, new_h), interpolation=cv2.INTER_AREA)
            elif max_dim < 600:
                scale = 800.0 / max_dim
                new_w, new_h = int(img_w * scale), int(img_h * scale)
                base_img = cv2.resize(base_img, (new_w, new_h), interpolation=cv2.INTER_CUBIC)

            images_to_try = self._clean_for_ocr(base_img)

            best_results = []
            for name, ocr_img in images_to_try:
                easyocr_results = reader.readtext(ocr_img)
                if not easyocr_results:
                    continue

                current = self._parse_easyocr_results(easyocr_results, scale, img_h, img_w, existing)
                print(f"[ImageAnalyzer] EasyOCR ({name}) found {len(easyocr_results)} items -> {len(current)} valid")

                if len(current) > len(best_results):
                    best_results = current

                if name == "original" and len(current) >= 3:
                    break

            return best_results
        except Exception as e:
            print(f"[ImageAnalyzer] EasyOCR error: {e}")
            traceback.print_exc()
        return []

    def _parse_easyocr_results(self, easyocr_results, scale: float, img_h: int, img_w: int,
                               existing: List[DetectedRegion]) -> List[DetectedRegion]:
        """Parse EasyOCR results into DetectedRegion list. EasyOCR format: [(bbox, text, conf), ...]"""
        results = []
        for bbox, text, confidence in easyocr_results:
            if confidence < 0.2:
                continue
            text = text.strip()
            if not text:
                continue

            pts = np.array(bbox, dtype=np.float64)
            x = int(pts[:, 0].min() / scale)
            y = int(pts[:, 1].min() / scale)
            w = int(pts[:, 0].max() / scale) - x
            h = int(pts[:, 1].max() / scale) - y
            if w < 3 or h < 3:
                continue
            # Skip oversized regions
            if h > img_h * 0.15 or w > img_w * 0.8:
                continue
            # Skip noise text (tick marks, brackets, etc.)
            if self._is_noise_text(text, w, h, img_h):
                continue

            region = DetectedRegion("text", x=x, y=y, width=w, height=h,
                                    data=text, confidence=confidence)
            if not self._overlaps_any(region, existing):
                results.append(region)
        return results

    def _parse_ocr_results(self, ocr_results, scale: float, img_h: int, img_w: int,
                           existing: List[DetectedRegion]) -> List[DetectedRegion]:
        """Parse raw OCR results into DetectedRegion list with filtering."""
        results = []
        for box, text, confidence in ocr_results:
            if confidence < 0.2:
                continue
            text = text.strip()
            if not text:
                continue

            pts = np.array(box, dtype=np.float64)
            x = int(pts[:, 0].min() / scale)
            y = int(pts[:, 1].min() / scale)
            w = int(pts[:, 0].max() / scale) - x
            h = int(pts[:, 1].max() / scale) - y
            if w < 3 or h < 3:
                continue
            # Skip oversized "text" regions (likely misdetected barcodes/images)
            if h > img_h * 0.15 or w > img_w * 0.8:
                continue
            # Skip noise text (tick marks, brackets, etc.)
            if self._is_noise_text(text, w, h, img_h):
                continue

            region = DetectedRegion("text", x=x, y=y, width=w, height=h,
                                    data=text, confidence=confidence)
            if not self._overlaps_any(region, existing):
                results.append(region)
        return results

    def _detect_text_morphological(self, gray: np.ndarray, existing: List[DetectedRegion]) -> List[DetectedRegion]:
        """Detect text regions using morphological analysis (fallback)."""
        results = []
        try:
            img_h, img_w = gray.shape[:2]
            binary = self._binary_cache.copy()

            mask = np.ones_like(binary) * 255
            for r in existing:
                pad = 5
                cv2.rectangle(mask, (r.x - pad, r.y - pad),
                              (r.x + r.width + pad, r.y + r.height + pad), 0, -1)
            binary = cv2.bitwise_and(binary, mask)

            # Remove long horizontal/vertical lines so they don't merge with text
            line_min_h = int(img_w * 0.15)
            line_min_v = int(img_h * 0.08)
            h_line_k = cv2.getStructuringElement(cv2.MORPH_RECT, (line_min_h, 1))
            h_lines_found = cv2.morphologyEx(binary, cv2.MORPH_OPEN, h_line_k)
            binary = cv2.subtract(binary, h_lines_found)
            v_line_k = cv2.getStructuringElement(cv2.MORPH_RECT, (1, line_min_v))
            v_lines_found = cv2.morphologyEx(binary, cv2.MORPH_OPEN, v_line_k)
            binary = cv2.subtract(binary, v_lines_found)

            base = max(img_w, img_h) / 500.0
            # Purely horizontal dilation to connect characters into words/lines
            kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (max(15, int(15 * base)), 1))
            dilated = cv2.dilate(binary, kernel_h, iterations=2)
            # Light vertical dilation to bridge ascenders/descenders within a line
            kernel_v = cv2.getStructuringElement(cv2.MORPH_RECT, (max(3, int(3 * base)), max(2, int(2 * base))))
            dilated = cv2.dilate(dilated, kernel_v, iterations=1)

            contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            min_area = max(200, int(img_w * img_h * 0.0002))

            for cnt in contours:
                x, y, w, h = cv2.boundingRect(cnt)
                area = w * h
                if area < min_area or (h > img_h * 0.8 and w > img_w * 0.8):
                    continue
                # Skip oversized regions (allow multi-line text blocks up to 40% height)
                if h > img_h * 0.4:
                    continue
                if w / max(h, 1) > 0.5 or (w < img_w * 0.2 and h < img_h * 0.2):
                    if not self._overlaps_any(DetectedRegion("text", x, y, w, h), existing):
                        results.append(DetectedRegion("text", x=x, y=y, width=w, height=h,
                                                      confidence=0.7))
        except Exception as e:
            print(f"[ImageAnalyzer] Morphological text error: {e}")
        return results

    def _clean_and_dedup_text(self, regions: List[DetectedRegion],
                              img_h: int, img_w: int) -> List[DetectedRegion]:
        """Clean text data and remove duplicate/fragment text regions.

        Fixes:
        1. Remove leading/trailing pipe | chars (vline artifacts in OCR)
        2. Remove multi-line garbage from single-region OCR
        3. Remove text fragments that are substrings of nearby longer text
        4. Remove regions whose text is contained in another overlapping region
        """
        import re

        # Phase 1: Clean individual text data
        for r in regions:
            if not r.data:
                continue
            text = r.data

            # Remove leading pipe/bracket chars (vline artifacts)
            text = re.sub(r'^[\|\[\]\{\}]+\s*', '', text)
            text = re.sub(r'\s*[\|\[\]\{\}]+$', '', text)

            # If text has multiple lines, keep only lines with ≥3 alphanumeric chars
            if '\n' in text:
                good_lines = []
                for line in text.split('\n'):
                    line = line.strip()
                    alnum = re.sub(r'[^a-zA-Z0-9]', '', line)
                    if len(alnum) >= 3:
                        good_lines.append(line)
                text = ' '.join(good_lines) if good_lines else text.split('\n')[0].strip()

            # Remove garbage words (OCR artifacts from anti-aliased rendering)
            # A word is garbage if it has: too many special chars, no vowels,
            # or looks like random character sequences
            cleaned_words = []
            for word in text.split():
                w_clean = word.strip('.,;:!?()[]{}|/\\')
                if not w_clean:
                    continue
                alnum = re.sub(r'[^a-zA-Z0-9]', '', w_clean)
                if len(alnum) == 0:
                    continue
                # Skip words with too many special chars (like "=%naeew")
                if len(alnum) < len(w_clean) * 0.6 and len(w_clean) > 2:
                    continue
                # Skip long words (>4 chars) with no vowels (like "olsccru", "hUORe")
                letters = re.sub(r'[^a-zA-Z]', '', w_clean)
                if len(letters) > 4:
                    vowels = len(re.findall(r'[aeiouAEIOU]', letters))
                    if vowels == 0:
                        continue
                    # Skip words with very low vowel ratio (like "Mewes" is ok, "bccdf" is not)
                    if vowels / len(letters) < 0.15 and len(letters) > 5:
                        continue
                cleaned_words.append(word)
            text = ' '.join(cleaned_words)

            # Validate text length against region width
            # If OCR returned way more text than fits, truncate to reasonable length
            max_chars = max(5, r.width // 4)  # ~4px per character minimum
            if len(text) > max_chars * 1.5:
                # Try to keep meaningful prefix
                text = text[:max_chars].rsplit(' ', 1)[0] if ' ' in text[:max_chars] else text[:max_chars]

            # Secondary noise validation after cleanup/truncation
            if self._is_noise_text(text, r.width, r.height, img_h):
                r.data = ""
                continue

            # Reject overly long multi-token strings in very wide, short regions
            # (common artifact when OCR merges logos/icons with text)
            words = text.split()
            if r.height > 0 and (r.width / r.height) > 10 and len(words) > 12:
                alpha_words = [w for w in words if len(re.sub(r'[^a-zA-Z0-9]', '', w)) >= 2]
                if len(alpha_words) < len(words) * 0.6:
                    r.data = ""
                    continue

            r.data = text.strip()

        # Phase 2: Remove fragments - if text A is a substring of nearby text B
        # and their bounding boxes are close, remove A (keep B, the longer one)
        to_remove = set()
        for i, ri in enumerate(regions):
            if not ri.data or ri.region_type != "text":
                continue
            for j, rj in enumerate(regions):
                if i == j or not rj.data or rj.region_type != "text":
                    continue
                # Check if ri's text is a substring of rj's text
                if ri.data in rj.data and len(ri.data) < len(rj.data):
                    # Check proximity (within reasonable distance)
                    dist_y = abs((ri.y + ri.height / 2) - (rj.y + rj.height / 2))
                    if dist_y < max(ri.height, rj.height) * 1.5:
                        to_remove.add(i)
                        break

        # Phase 3: Remove spatially overlapping text with similar content (keep longer)
        for i, ri in enumerate(regions):
            if i in to_remove or not ri.data or ri.region_type != "text":
                continue
            for j, rj in enumerate(regions):
                if i == j or j in to_remove or not rj.data or rj.region_type != "text":
                    continue
                overlap = self._overlap_area(ri, rj)
                min_area = min(ri.width * ri.height, rj.width * rj.height)
                if min_area > 0 and overlap / min_area > 0.3:
                    # Check content similarity - don't remove if texts are different
                    words_i = set(ri.data.lower().split())
                    words_j = set(rj.data.lower().split())
                    common = words_i & words_j
                    min_words = min(len(words_i), len(words_j))
                    if min_words > 0 and len(common) / min_words < 0.3:
                        continue  # Different content, keep both
                    # Overlapping with similar content - keep the one with longer text
                    if len(ri.data) < len(rj.data):
                        to_remove.add(i)
                        break
                    elif len(ri.data) > len(rj.data):
                        to_remove.add(j)

        # Phase 4: Remove regions with empty text after cleaning
        result = []
        for i, r in enumerate(regions):
            if i in to_remove:
                continue
            if r.region_type == "text" and r.data is not None and not r.data.strip():
                continue
            result.append(r)

        removed = len(regions) - len(result)
        if removed > 0:
            print(f"[ImageAnalyzer] Text dedup: removed {removed} fragment/duplicate regions")
        return result

    def _remove_barcode_text(self, text_regions: List[DetectedRegion],
                             barcode_regions: List[DetectedRegion]) -> List[DetectedRegion]:
        """Remove text regions that are the human-readable text below barcodes.
        Also marks the corresponding barcode with has_hr_text=True so ZPL generation
        can enable the HR interpretation line only when it was present originally."""
        result = []
        removed = 0
        for tr in text_regions:
            is_barcode_text = False
            tr_cx = tr.x + tr.width / 2
            tr_cy = tr.y + tr.height / 2
            for bc in barcode_regions:
                bc_bottom = bc.y + bc.height
                bc_left = bc.x
                bc_right = bc.x + bc.width
                # Text must be below barcode (within 50px) and horizontally within barcode range
                if (bc_bottom - 5 <= tr.y <= bc_bottom + 50 and
                        bc_left - 20 <= tr_cx <= bc_right + 20):
                    is_barcode_text = True
                    bc.extra['has_hr_text'] = True
                    break
                # Also check if text center is within barcode's expanded vertical zone
                if (bc_bottom - 5 <= tr_cy <= bc_bottom + 40 and
                        bc_left - 10 <= tr_cx <= bc_right + 10):
                    is_barcode_text = True
                    bc.extra['has_hr_text'] = True
                    break
            if is_barcode_text:
                removed += 1
            else:
                result.append(tr)
        if removed:
            print(f"[ImageAnalyzer] Removed {removed} barcode human-readable text region(s)")
        return result

    def _split_text_region_into_lines(self, gray: np.ndarray,
                                       region: DetectedRegion) -> List[DetectedRegion]:
        """Split a tall text region into separate lines using horizontal projection.
        Returns sub-regions if multiple lines found, otherwise returns [region]."""
        img_h, img_w = gray.shape[:2]
        x1 = max(0, region.x)
        y1 = max(0, region.y)
        x2 = min(img_w, region.x + region.width)
        y2 = min(img_h, region.y + region.height)
        if x2 <= x1 or y2 <= y1:
            return [region]

        crop = gray[y1:y2, x1:x2]
        # Binarize
        _, binary = cv2.threshold(crop, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        # Horizontal projection: sum of foreground pixels per row
        h_proj = np.sum(binary > 0, axis=1)

        # Find rows with minimal content (gaps between lines)
        threshold = max(1, crop.shape[1] * 0.02)  # 2% of width
        is_gap = h_proj < threshold

        # Find contiguous text bands (non-gap rows)
        bands = []
        in_band = False
        band_start = 0
        for row_idx in range(len(is_gap)):
            if not is_gap[row_idx] and not in_band:
                band_start = row_idx
                in_band = True
            elif is_gap[row_idx] and in_band:
                band_end = row_idx
                if band_end - band_start >= 5:  # Minimum 5px height for a text line
                    bands.append((band_start, band_end))
                in_band = False
        # Close last band
        if in_band and len(is_gap) - band_start >= 5:
            bands.append((band_start, len(is_gap)))

        if len(bands) <= 1:
            return [region]

        # Create sub-regions for each band
        sub_regions = []
        for band_top, band_bottom in bands:
            sub_h = band_bottom - band_top
            sub_y = region.y + band_top
            sub_regions.append(DetectedRegion(
                "text", x=region.x, y=sub_y,
                width=region.width, height=sub_h,
                confidence=region.confidence
            ))
        return sub_regions

    def _ocr_single_region(self, image: np.ndarray, region: DetectedRegion) -> str:
        """Run OCR on a single cropped region. Uses multiple preprocessing variants."""
        img_h, img_w = image.shape[:2]
        pad = 20
        x1 = max(0, region.x - pad)
        y1 = max(0, region.y - pad)
        x2 = min(img_w, region.x + region.width + pad)
        y2 = min(img_h, region.y + region.height + pad)
        crop = image[y1:y2, x1:x2]
        if crop.size == 0:
            return ""

        gray_crop = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if len(crop.shape) == 3 else crop

        # Scale up small crops for better OCR on anti-aliased text
        ch, cw = gray_crop.shape[:2]
        if max(ch, cw) < 250:
            scale = 400.0 / max(ch, cw)
            gray_crop = cv2.resize(gray_crop, None, fx=scale, fy=scale,
                                   interpolation=cv2.INTER_CUBIC)

        # Generate cleaned variants
        crops_to_try = self._clean_for_ocr(gray_crop)

        # Collect all OCR results and pick the best (longest text with high confidence)
        best_text = ""

        # Try RapidOCR first
        engine = self._get_ocr_reader()
        if engine is not None:
            for name, c in crops_to_try:
                try:
                    result, _ = engine(c)
                    if result:
                        texts = [t.strip() for _, t, c2 in result if c2 > 0.3 and t.strip()]
                        if texts:
                            candidate = " ".join(texts)
                            if len(candidate) > len(best_text):
                                best_text = candidate
                except Exception:
                    pass

        # Try EasyOCR (pure pip, catches anti-aliased text)
        if not best_text and self._has_easyocr:
            reader = self._get_easyocr_reader()
            if reader is not None:
                for name, c in crops_to_try:
                    try:
                        results = reader.readtext(c)
                        if results:
                            texts = [t.strip() for _, t, c2 in results if c2 > 0.3 and t.strip()]
                            if texts:
                                candidate = " ".join(texts)
                                if len(candidate) > len(best_text):
                                    best_text = candidate
                    except Exception:
                        pass

        # Tesseract fallback (requires system install)
        if not best_text and self._has_tesseract:
            try:
                import pytesseract
                preprocessed = []
                denoised = cv2.fastNlMeansDenoising(gray_crop, None, 10, 7, 21)
                processed = cv2.adaptiveThreshold(
                    denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                    cv2.THRESH_BINARY, 11, 2
                )
                preprocessed.append(processed)
                _, otsu = cv2.threshold(gray_crop, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                preprocessed.append(otsu)

                for pp in preprocessed:
                    for psm in ['7', '6']:
                        try:
                            text = pytesseract.image_to_string(
                                pp, config=f'--oem 3 --psm {psm}'
                            ).strip()
                            if text and len(text) > len(best_text):
                                best_text = text
                        except Exception:
                            pass
            except Exception:
                pass

        return best_text

    # ── Grid cell text detection ─────────────────────────────────────

    def _detect_grid_cell_text(self, gray: np.ndarray,
                                line_regions: List[DetectedRegion],
                                text_regions: List[DetectedRegion]) -> List[DetectedRegion]:
        """Detect text inside grid/table cells that the main OCR missed.

        Identifies compact grid rows (height 15-120px) formed by hlines with
        matching vline columns, then runs OCR on uncovered cells.
        """
        results = []
        try:
            if not self._has_ocr and not self._has_easyocr and not self._has_tesseract:
                return results

            img_h, img_w = gray.shape[:2]

            hlines = sorted([r for r in line_regions if r.region_type == "hline"],
                            key=lambda r: r.y)
            vlines = sorted([r for r in line_regions if r.region_type == "vline"],
                            key=lambda r: r.x)

            if len(hlines) < 2 or len(vlines) < 3:
                return results

            # Find compact grid rows: pairs of adjacent hlines with height 15-120px
            # that share similar x-extent (both span > 60% of image width)
            grid_rows = []
            for i in range(len(hlines) - 1):
                h1 = hlines[i]
                h2 = hlines[i + 1]
                row_h = h2.y - h1.y
                if row_h < 15 or row_h > 120:
                    continue
                # Both hlines must be wide (>60% of image width)
                if h1.width < img_w * 0.6 or h2.width < img_w * 0.6:
                    continue
                grid_rows.append((h1.y, h2.y))

            if not grid_rows:
                return results

            # Find column boundaries from vlines that span the grid rows
            grid_y_min = min(r[0] for r in grid_rows)
            grid_y_max = max(r[1] for r in grid_rows)
            grid_vlines = [v for v in vlines
                           if v.y <= grid_y_min + 5 and v.y + v.height >= grid_y_max - 5]

            if len(grid_vlines) < 3:
                return results

            col_positions = sorted(set(v.x for v in grid_vlines))
            binary = self._binary_cache

            for ry1, ry2 in grid_rows:
                y1 = ry1 + 4
                y2 = ry2 - 2

                for ci in range(len(col_positions) - 1):
                    x1 = col_positions[ci] + 4
                    x2 = col_positions[ci + 1] - 2
                    if x2 - x1 < 20:
                        continue

                    # Check if any existing region already covers this cell
                    cell_region = DetectedRegion("text", x1, y1, x2 - x1, y2 - y1)
                    covered = False
                    for tr in text_regions:
                        overlap = self._overlap_area(cell_region, tr)
                        tr_area = max(tr.width * tr.height, 1)
                        cell_area = max((x2 - x1) * (y2 - y1), 1)
                        # Covered if text overlaps >10% of cell or cell overlaps >30% of text
                        if overlap / cell_area > 0.1 or overlap / tr_area > 0.3:
                            covered = True
                            break
                    if covered:
                        continue

                    # Check foreground density
                    cell_bin = binary[y1:y2, x1:x2]
                    if cell_bin.size == 0:
                        continue
                    fg = np.sum(cell_bin > 0)
                    density = fg / cell_bin.size
                    if density < 0.005:
                        continue

                    # Run OCR on cell crop
                    cell_gray = gray[y1:y2, x1:x2]
                    scale = max(2.0, 200.0 / max(y2 - y1, x2 - x1, 1))
                    big = cv2.resize(cell_gray, None, fx=scale, fy=scale,
                                     interpolation=cv2.INTER_CUBIC)
                    text = self._ocr_crop_text(big)

                    if not text:
                        continue

                    import re
                    text = re.sub(r'[{}\|\\~`\^]', '', text).strip()
                    text = text.replace('^', '').replace('~', '')
                    if not text:
                        continue

                    # Find tight ink bounds
                    ink_rows = np.where(np.sum(cell_bin > 0, axis=1) > 0)[0]
                    ink_cols = np.where(np.sum(cell_bin > 0, axis=0) > 0)[0]
                    if len(ink_rows) == 0 or len(ink_cols) == 0:
                        continue

                    ty = y1 + int(ink_rows[0])
                    th = int(ink_rows[-1] - ink_rows[0]) + 1
                    tx = x1 + int(ink_cols[0])
                    tw = int(ink_cols[-1] - ink_cols[0]) + 1

                    # Checkbox/bracket content (like "[ ]"): render as image
                    # for pixel-accurate rendering (ZPL font brackets look wrong)
                    import re
                    is_bracket = bool(re.match(r'^[\[\]\(\)\s]+$', text))
                    if is_bracket:
                        results.append(DetectedRegion(
                            "image", x=tx, y=ty, width=tw, height=th,
                            confidence=0.7
                        ))
                    else:
                        # Apply 4/3 height correction for text
                        th = round(th * 4 / 3)
                        results.append(DetectedRegion(
                            "text", x=tx, y=ty, width=tw, height=th,
                            data=text, confidence=0.7
                        ))

        except Exception as e:
            print(f"[ImageAnalyzer] Grid cell text error: {e}")

        return results

    # ── Image/graphic detection ──────────────────────────────────────

    def _detect_colored_regions(self, image: np.ndarray,
                                existing: List[DetectedRegion]) -> List[DetectedRegion]:
        """Detect colored regions (logos, icons with color) that binary detection misses.
        Most label content is black/white; colored areas are logos or icons."""
        results = []
        try:
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            # High saturation = color (not gray/black/white)
            sat = hsv[:, :, 2]  # value channel
            sat_mask = hsv[:, :, 1] > 50  # saturation > 50
            val_mask = hsv[:, :, 2] > 40   # not too dark
            color_mask = (sat_mask & val_mask).astype(np.uint8) * 255

            if np.sum(color_mask > 0) < 100:
                return results

            # Mask out existing text/barcode regions to avoid detecting
            # sub-pixel rendering artifacts at text edges as colored regions.
            for r in existing:
                if r.region_type in ("text", "barcode"):
                    pad = 8
                    cv2.rectangle(color_mask,
                                  (r.x - pad, r.y - pad),
                                  (r.x + r.width + pad, r.y + r.height + pad),
                                  0, -1)

            if np.sum(color_mask > 0) < 100:
                return results

            # Dilate to group nearby colored pixels
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
            dilated = cv2.dilate(color_mask, kernel, iterations=3)

            contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL,
                                           cv2.CHAIN_APPROX_SIMPLE)
            img_h, img_w = image.shape[:2]
            min_area = 400
            max_area = int(img_w * img_h * 0.1)

            for cnt in contours:
                x, y, w, h = cv2.boundingRect(cnt)
                area = w * h
                if area < min_area or area > max_area:
                    continue
                # Check actual colored pixel density in region
                roi = color_mask[y:y + h, x:x + w]
                density = np.sum(roi > 0) / max(area, 1)
                if density < 0.05:
                    continue
                if not self._overlaps_any(DetectedRegion("image", x, y, w, h), existing):
                    results.append(DetectedRegion(
                        "image", x=x, y=y, width=w, height=h,
                        confidence=0.6, extra={"source": "color", "density": round(density, 3)}))
        except Exception as e:
            print(f"[ImageAnalyzer] Color detection error: {e}")
        return results

    def _detect_images(self, gray: np.ndarray, existing: List[DetectedRegion]) -> List[DetectedRegion]:
        """Detect image/graphic regions (logos, icons, filled shapes).
        Only compact, high-density regions qualify (not scattered leftover pixels)."""
        results = []
        try:
            img_h, img_w = gray.shape[:2]
            img_area = img_h * img_w
            binary = self._binary_cache.copy()

            # Mask out all already-detected regions with moderate padding
            mask = np.ones_like(binary) * 255
            for r in existing:
                if r.region_type == "text":
                    pad = 5
                elif r.region_type in ("hline", "vline"):
                    pad = 3
                else:
                    pad = 15
                cv2.rectangle(mask, (r.x - pad, r.y - pad),
                              (r.x + r.width + pad, r.y + r.height + pad), 0, -1)
            masked = cv2.bitwise_and(binary, mask)

            # Light dilation to group nearby pixels (not aggressive)
            base = max(img_w, img_h) / 500.0
            k_size = max(5, int(5 * base))
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k_size, k_size))
            dilated = cv2.dilate(masked, kernel, iterations=2)

            contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            min_area = max(500, int(img_area * 0.0009))
            max_area = int(img_area * 0.25)  # No region larger than 25% of image

            for cnt in contours:
                bx, by, bw, bh = cv2.boundingRect(cnt)

                # Tighten bounding box using actual ink pixels (not dilated extent)
                roi_loose = masked[by:by + bh, bx:bx + bw]
                tight_rows = np.any(roi_loose > 0, axis=1)
                tight_cols = np.any(roi_loose > 0, axis=0)
                if not np.any(tight_rows) or not np.any(tight_cols):
                    continue
                y_min = int(np.where(tight_rows)[0][0])
                y_max = int(np.where(tight_rows)[0][-1])
                x_min = int(np.where(tight_cols)[0][0])
                x_max = int(np.where(tight_cols)[0][-1])
                x = bx + x_min
                y = by + y_min
                w = x_max - x_min + 1
                h = y_max - y_min + 1

                area = w * h
                if area < min_area or area > max_area:
                    continue

                # Skip very elongated strips (likely leftover line edges or thin borders).
                aspect = max(w, h) / max(min(w, h), 1)

                # Text-line strips: wide & shallow regions that may be partially obscured
                # by adjacent text masking (e.g. right-side text columns in a label row).
                # These have high aspect ratios but are valid content.
                is_text_line_strip = (h < 60 and w > 100 and 15.0 < aspect <= 35.0)
                if aspect > 15.0 and not is_text_line_strip:
                    continue

                # Measure actual pixel density in the tight bounding box
                roi = masked[y:y + h, x:x + w]
                density = np.sum(roi > 0) / max(area, 1)
                # Text-line strips have lower ink density because they are partially masked
                min_density = 0.05 if is_text_line_strip else 0.15
                if density < min_density:
                    continue  # Too sparse - just scattered edge pixels

                if not self._overlaps_any(DetectedRegion("image", x, y, w, h), existing):
                    results.append(DetectedRegion("image", x=x, y=y, width=w, height=h,
                                                  confidence=0.5, extra={"density": round(density, 3)}))
        except Exception as e:
            print(f"[ImageAnalyzer] Image detection error: {e}")
        return results

    def _ocr_image_regions(self, gray: np.ndarray,
                            img_regions: List[DetectedRegion]):
        """Try OCR on image regions to detect large bold text (e.g. 'CA').
        Returns (text_regions, remaining_image_regions)."""
        has_any_ocr = self._has_ocr or self._has_easyocr or self._has_tesseract
        if not has_any_ocr or not img_regions:
            return [], img_regions

        text_regions = []
        remaining = []

        for region in img_regions:
            # Skip roughly-square, dense regions — likely QR codes, icons, or logos.
            # OCR on these produces garbage text; keep as image for GFA rendering.
            aspect = region.width / max(region.height, 1)
            if 0.5 <= aspect <= 2.0 and region.width > 30 and region.height > 30:
                roi = gray[region.y:region.y + region.height,
                           region.x:region.x + region.width]
                if roi.size > 0:
                    dark_ratio = float(np.mean(roi < 128))
                    if dark_ratio > 0.25:
                        remaining.append(region)
                        continue

            pad = 10
            x1 = max(0, region.x - pad)
            y1 = max(0, region.y - pad)
            x2 = min(gray.shape[1], region.x + region.width + pad)
            y2 = min(gray.shape[0], region.y + region.height + pad)
            crop = gray[y1:y2, x1:x2]
            if crop.size == 0:
                remaining.append(region)
                continue

            # Scale up small crops
            scale_used = 1.0
            ch, cw = crop.shape[:2]
            if max(ch, cw) < 200:
                scale_used = 300.0 / max(ch, cw)
                crop = cv2.resize(crop, None, fx=scale_used, fy=scale_used,
                                  interpolation=cv2.INTER_CUBIC)

            # Try Otsu binary
            _, binary = cv2.threshold(crop, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

            # Run OCR using available engines
            best_text = self._ocr_crop_text(crop)
            # Accept text from image regions only if it looks like real text:
            # - At least 2 alphanumeric chars (single chars are garbage)
            # - No special characters that suggest OCR noise
            # - For 2-3 char text, require it to be uppercase (like routing codes: CA, NY)
            #   or all digits, since short lowercase is usually OCR garbage (aoe, ot, Be)
            import re
            alnum = re.sub(r'[^a-zA-Z0-9]', '', best_text)
            has_special = any(c in best_text for c in '{}|\\~`^#&=')
            is_valid = False
            if alnum and len(alnum) >= 2 and len(alnum) <= 10 and not has_special:
                if len(alnum) <= 3:
                    # Short text: only accept if ALL UPPERCASE or all digits
                    is_valid = alnum.isupper() or alnum.isdigit()
                else:
                    is_valid = True

            # Reject garbage OCR: many single-char words indicate noise from
            # reading complex graphics (QR codes, logos, dense patterns).
            if is_valid:
                words = best_text.split()
                single_char_words = sum(1 for w in words if len(w) == 1)
                if len(words) >= 3 and single_char_words / len(words) > 0.4:
                    is_valid = False

            # Guard: large graphic regions can be misread as short text (e.g. logo -> "CA").
            # In these cases keep the region as bitmap image for pixel-accurate rendering.
            if is_valid and len(alnum) <= 3:
                region_area = region.width * region.height
                region_aspect = region.width / max(region.height, 1)
                dark_ratio = float(np.mean(binary == 0)) if binary.size else 0.0

                # Large/tall regions with very short OCR text are likely logos, not text.
                # Also reject dense short-text crops; real text occupies less ink ratio.
                if ((region_area > 7000 and region.height > 80 and region_aspect < 1.2)
                        or (region_area > 10000 and len(alnum) <= 3)
                        or dark_ratio > 0.40):
                    is_valid = False

            if is_valid:
                # For short text (routing codes like "CA"), measure actual ink extent
                # to correct the font height. The box boundary is the detected region,
                # but the original font cell may be taller than the measured ink height.
                # ZPL ^A0 font renders ink at ~75% of cell height (cap height ratio).
                final_height = region.height
                if len(alnum) <= 3:
                    try:
                        # Use interior columns to avoid border pixels on left/right edges
                        bh, bw = binary.shape[:2]
                        margin = max(5, min(15, bw // 8))
                        interior = binary[:, margin:bw - margin]
                        if interior.size > 0:
                            dark_rows = np.where(np.any(interior == 0, axis=1))[0]
                            if len(dark_rows) > 0:
                                ink_bottom_crop = int(dark_rows.max())
                                # Map back: crop row → image y
                                ink_bottom_img = y1 + round(ink_bottom_crop / scale_used)
                                ink_height = max(1, ink_bottom_img - region.y + 1)
                                # Font cell height = ink_height / cap_height_ratio (0.75)
                                corrected_h = round(ink_height / 0.75)
                                if corrected_h > region.height:
                                    final_height = corrected_h
                                    print(f"[ImageAnalyzer] '{best_text}' height corrected: "
                                          f"{region.height} -> {final_height}")
                    except Exception:
                        pass
                text_regions.append(DetectedRegion(
                    "text", x=region.x, y=region.y,
                    width=region.width, height=final_height,
                    data=best_text, confidence=0.7,
                    extra={"from_image_ocr": True}
                ))
            else:
                remaining.append(region)

        if text_regions:
            print(f"[ImageAnalyzer] OCR on images: converted {len(text_regions)} to text: "
                  + ", ".join(f'"{r.data}"' for r in text_regions))
        return text_regions, remaining

    def _detect_box_headers(self, gray: np.ndarray,
                             box_regions: List[DetectedRegion]) -> List[DetectedRegion]:
        """Detect filled dark headers inside boxes (e.g., WARNING box header).
        These are dark bands at the top of a box with white text inside.
        Returns image regions for GFA bitmap rendering."""
        results = []
        img_h, img_w = gray.shape[:2]
        dark_threshold = 100

        for box in box_regions:
            bx, by, bw, bh = box.x, box.y, box.width, box.height
            if bw < 50 or bh < 40:
                continue

            thickness = box.extra.get("thickness", 3)
            # Scan rows from top of box downward (up to 50% of box height)
            max_scan = min(by + bh // 2, img_h)
            header_end = by
            gap = 0
            max_gap = 3  # Allow small gaps for white text rows

            for y in range(by, max_scan):
                row = gray[y, bx:bx + bw]
                dark_pct = np.sum(row < dark_threshold) / max(len(row), 1)
                if dark_pct > 0.50:
                    header_end = y + 1
                    gap = 0
                else:
                    gap += 1
                    if gap > max_gap:
                        break

            header_h = header_end - by
            # Need at least thickness + 5px (more than just the box border)
            if header_h > thickness + 5:
                results.append(DetectedRegion(
                    "image",
                    x=bx, y=by,
                    width=bw, height=header_h,
                    confidence=0.8,
                    extra={"box_header": True}
                ))
                print(f"[ImageAnalyzer] Box header at ({bx},{by}): {bw}x{header_h}")

        return results

    def _detect_reverse_banners(self, gray: np.ndarray,
                                 existing: List[DetectedRegion]) -> List[DetectedRegion]:
        """Detect reverse-video banners (white text on dark background).
        These are wide dark horizontal bands with white text inside."""
        results = []
        try:
            img_h, img_w = gray.shape[:2]
            # Don't use inverse binary cache - CAUTION band may have gray background
            # that OTSU thresholds as white. Instead count dark pixels in gray image.
            # Dark = pixel value < 100 (adjustable threshold for "black" background)
            dark_threshold = 100
            row_dark_count = np.sum(gray < dark_threshold, axis=1)
            row_density = row_dark_count / img_w

            # Find contiguous bands where density > 20% (lower threshold for text inside)
            in_band = False
            band_start = 0
            raw_bands = []
            for y in range(img_h):
                if row_density[y] > 0.20:
                    if not in_band:
                        band_start = y
                        in_band = True
                else:
                    if in_band:
                        raw_bands.append((band_start, y - band_start))
                        in_band = False
            if in_band:
                raw_bands.append((band_start, img_h - band_start))

            # Merge nearby bands (gap <= 5 rows) to handle text inside banners
            # Keep gap small to avoid merging unrelated regions (e.g. grid lines + banner)
            bands = []
            for start, height in raw_bands:
                if bands and start - (bands[-1][0] + bands[-1][1]) <= 5:
                    # Merge with previous band
                    prev_start, prev_h = bands[-1]
                    bands[-1] = (prev_start, start + height - prev_start)
                else:
                    bands.append((start, height))

            # Filter by size
            bands = [(s, h) for s, h in bands
                     if h > 15 and h < img_h * 0.15]

            # Filter: band must have average density > 40% across the whole band
            # This ensures it's actually a filled background, not just dense text
            filtered_bands = []
            for band_y, band_h in bands:
                avg_density = np.mean(row_density[band_y:band_y + band_h])
                if avg_density > 0.40:
                    filtered_bands.append((band_y, band_h))
            bands = filtered_bands

            for band_y, band_h in bands:
                # Find x-extent of the dark band using gray image
                band_gray = gray[band_y:band_y + band_h, :]
                col_density = np.sum(band_gray < dark_threshold, axis=0) / band_h
                # Band must span at least 50% of image width
                band_cols = np.where(col_density > 0.5)[0]
                if len(band_cols) < img_w * 0.5:
                    continue
                band_x = int(band_cols[0])
                band_w = int(band_cols[-1] - band_cols[0] + 1)

                # Check overlap only with non-text regions (barcodes, QR, boxes)
                # Text regions inside banners should be replaced by reverse text
                test_region = DetectedRegion("text", band_x, band_y, band_w, band_h)
                non_text = [r for r in existing if r.region_type not in ("text", "image")]
                if self._overlaps_any(test_region, non_text):
                    continue

                # Extract region and invert for OCR (white text becomes black)
                pad = 5
                y1 = max(0, band_y - pad)
                y2 = min(img_h, band_y + band_h + pad)
                x1 = max(0, band_x - pad)
                x2 = min(img_w, band_x + band_w + pad)
                crop = gray[y1:y2, x1:x2]
                inverted = cv2.bitwise_not(crop)

                # Scale up for better OCR
                ch, cw = inverted.shape[:2]
                if max(ch, cw) < 200:
                    scale = 300.0 / max(ch, cw)
                    inverted = cv2.resize(inverted, None, fx=scale, fy=scale,
                                          interpolation=cv2.INTER_CUBIC)

                # Try OCR on inverted region
                text = self._ocr_reverse_region(inverted)
                if text and len(text) >= 3:
                    results.append(DetectedRegion(
                        "text", x=band_x, y=band_y,
                        width=band_w, height=band_h,
                        data=text, confidence=0.8,
                        extra={"reverse": True}
                    ))
                    print(f"[ImageAnalyzer] Reverse banner at y={band_y}: \"{text}\"")
        except Exception as e:
            print(f"[ImageAnalyzer] Reverse banner detection error: {e}")
        return results

    def _detect_text_colors(self, gray: np.ndarray, regions: List[DetectedRegion]):
        """Detect background color for each text region.

        For each text region not already marked as reverse, check if it sits on a
        dark background (white/light text on dark). If so, set extra["reverse"]=True.
        """
        img_h, img_w = gray.shape[:2]
        reverse_count = 0
        for r in regions:
            if r.region_type != "text":
                continue
            if r.extra.get("reverse"):
                continue  # already marked by banner detection

            # Extract ROI with small padding
            pad = 2
            y1 = max(0, r.y - pad)
            y2 = min(img_h, r.y + r.height + pad)
            x1 = max(0, r.x - pad)
            x2 = min(img_w, r.x + r.width + pad)
            if y2 <= y1 or x2 <= x1:
                continue

            roi = gray[y1:y2, x1:x2]

            # Sample background: use border pixels (edges of the ROI)
            # These are most likely background, not text ink
            border_pixels = np.concatenate([
                roi[0, :],           # top row
                roi[-1, :],          # bottom row
                roi[:, 0],           # left column
                roi[:, -1],          # right column
            ])
            bg_mean = float(np.mean(border_pixels))

            # If background is dark (mean < 100), text is light/white
            if bg_mean < 100:
                r.extra["reverse"] = True
                reverse_count += 1

        if reverse_count > 0:
            print(f"[ImageAnalyzer] Text color detection: {reverse_count} reverse text regions")

    def _ocr_reverse_region(self, inverted_gray: np.ndarray) -> str:
        """Run OCR on an inverted (white-on-dark -> dark-on-white) region.
        Priority: RapidOCR → EasyOCR → Tesseract."""
        best_text = self._ocr_crop_text(inverted_gray)

        # Clean up
        import re
        best_text = re.sub(r'[{}\|\\~`\^]', '', best_text).strip()
        return best_text

    def _separate_graphic_boxes(self, gray: np.ndarray,
                                 boxes: List[DetectedRegion]):
        """Separate boxes with internal graphics (logos, icons) from plain boxes.
        Returns (plain_boxes, graphic_image_regions)."""
        if not boxes:
            return boxes, []

        binary = self._binary_cache
        plain = []
        graphics = []

        for box in boxes:
            # Only check roughly square, small-ish boxes (likely logos/icons)
            aspect = max(box.width, box.height) / max(min(box.width, box.height), 1)
            if aspect > 2.5 or box.width * box.height > gray.shape[0] * gray.shape[1] * 0.05:
                plain.append(box)
                continue

            # Check interior pixel density (exclude border ~20%)
            margin_x = max(3, int(box.width * 0.2))
            margin_y = max(3, int(box.height * 0.2))
            x1 = box.x + margin_x
            y1 = box.y + margin_y
            x2 = box.x + box.width - margin_x
            y2 = box.y + box.height - margin_y
            if x2 <= x1 or y2 <= y1:
                plain.append(box)
                continue

            interior = binary[y1:y2, x1:x2]
            if interior.size == 0:
                plain.append(box)
                continue

            density = np.sum(interior > 0) / interior.size
            if density > 0.10:
                # Significant internal content → convert to image region
                graphics.append(DetectedRegion(
                    "image", x=box.x, y=box.y,
                    width=box.width, height=box.height,
                    confidence=0.6, extra={"source": "graphic_box", "density": round(density, 3)}
                ))
            else:
                plain.append(box)

        if graphics:
            print(f"[ImageAnalyzer] Graphic boxes -> images: {len(graphics)}")
        return plain, graphics

    # ── Post-processing ────────────────────────────────────────────────

    def _remove_line_formed_boxes(self, boxes: List[DetectedRegion],
                                   lines: List[DetectedRegion]) -> List[DetectedRegion]:
        """Remove boxes formed by grid lines. Detects two cases:
        1. Grid CELLS: box edges formed by lines that extend >30% beyond the box
        2. Grid OUTLINES: all 4 edges match lines AND interior lines cross through"""
        if not boxes or not lines:
            return boxes

        tol = 8
        extend_thresh = 0.3
        hlines = [l for l in lines if l.region_type == "hline"]
        vlines = [l for l in lines if l.region_type == "vline"]

        keep = []
        for box in boxes:
            bx, by, bw, bh = box.x, box.y, box.width, box.height
            grid_edges = 0

            # Check top/bottom hlines: do they extend significantly beyond box width?
            for hl in hlines:
                if abs(hl.y - by) < tol or abs(hl.y - (by + bh)) < tol:
                    if hl.x <= bx + tol and (hl.x + hl.width) >= (bx + bw - tol):
                        extra = hl.width - bw
                        if extra > bw * extend_thresh:
                            grid_edges += 1

            # Check left/right vlines: do they extend beyond box height?
            for vl in vlines:
                if abs(vl.x - bx) < tol or abs(vl.x - (bx + bw)) < tol:
                    if vl.y <= by + tol and (vl.y + vl.height) >= (by + bh - tol):
                        extra = vl.height - bh
                        if extra > bh * extend_thresh:
                            grid_edges += 1

            if grid_edges >= 2:
                continue

            # Case 2: Outer grid boundary - all 4 edges match lines AND has interior lines
            matching_top = any(abs(hl.y - by) < tol and hl.x <= bx + tol
                               and (hl.x + hl.width) >= (bx + bw - tol) for hl in hlines)
            matching_bottom = any(abs(hl.y - (by + bh)) < tol and hl.x <= bx + tol
                                  and (hl.x + hl.width) >= (bx + bw - tol) for hl in hlines)
            matching_left = any(abs(vl.x - bx) < tol and vl.y <= by + tol
                                and (vl.y + vl.height) >= (by + bh - tol) for vl in vlines)
            matching_right = any(abs(vl.x - (bx + bw)) < tol and vl.y <= by + tol
                                 and (vl.y + vl.height) >= (by + bh - tol) for vl in vlines)

            if matching_top and matching_bottom and matching_left and matching_right:
                # All edges match lines - check if there are interior lines too
                interior = 0
                for hl in hlines:
                    if hl.y > by + tol and hl.y < (by + bh) - tol:
                        if hl.x <= bx + tol and (hl.x + hl.width) >= (bx + bw - tol):
                            interior += 1
                for vl in vlines:
                    if vl.x > bx + tol and vl.x < (bx + bw) - tol:
                        if vl.y <= by + tol and (vl.y + vl.height) >= (by + bh - tol):
                            interior += 1
                if interior >= 1:
                    # Grid outline: all edges match lines + interior lines = grid
                    continue

            keep.append(box)
        return keep

    def _remove_text_formed_boxes(self, boxes: List[DetectedRegion],
                                    texts: List[DetectedRegion]) -> List[DetectedRegion]:
        """Remove boxes whose interior is mostly text (false positives from text blocks).
        A real box has thin borders with empty/text interior. A false box from text
        contours has most of its area covered by text with no visible border."""
        if not boxes or not texts:
            return boxes
        keep = []
        for box in boxes:
            bx, by, bw, bh = box.x, box.y, box.width, box.height
            box_area = max(bw * bh, 1)
            text_area = 0
            for t in texts:
                overlap = self._overlap_area(box, t)
                text_area += overlap
            text_ratio = text_area / box_area
            # If >60% of box area is text and no measurable border, it's a false box
            thickness = box.extra.get("thickness", 0)
            if text_ratio > 0.6 and thickness <= 1:
                continue
            keep.append(box)
        return keep

    def _remove_box_edge_lines(self, lines: List[DetectedRegion],
                                boxes: List[DetectedRegion]) -> List[DetectedRegion]:
        """Remove lines that coincide with edges of detected boxes."""
        if not boxes or not lines:
            return lines

        tol = 8  # pixel tolerance
        keep = []
        for line in lines:
            is_box_edge = False
            for box in boxes:
                bx, by, bw, bh = box.x, box.y, box.width, box.height

                if line.region_type == "hline":
                    lx, ly = line.x, line.y
                    lw = line.width
                    # Top edge of box
                    if abs(ly - by) < tol and abs(lx - bx) < tol and abs(lw - bw) < tol * 3:
                        is_box_edge = True
                        break
                    # Bottom edge of box
                    if abs(ly - (by + bh)) < tol and abs(lx - bx) < tol and abs(lw - bw) < tol * 3:
                        is_box_edge = True
                        break

                elif line.region_type == "vline":
                    lx, ly = line.x, line.y
                    lh = line.height
                    # Left edge of box
                    if abs(lx - bx) < tol and abs(ly - by) < tol and abs(lh - bh) < tol * 3:
                        is_box_edge = True
                        break
                    # Right edge of box
                    if abs(lx - (bx + bw)) < tol and abs(ly - by) < tol and abs(lh - bh) < tol * 3:
                        is_box_edge = True
                        break

            if not is_box_edge:
                keep.append(line)
        return keep

    def _try_decode_barcode_region(self, image: np.ndarray, gray: np.ndarray,
                                    bc: DetectedRegion):
        """Try to decode a barcode region using pyzbar with aggressive preprocessing."""
        if not self._has_pyzbar or bc.data:
            return
        try:
            from pyzbar import pyzbar
            pad = 10
            img_h, img_w = gray.shape[:2]
            x1 = max(0, bc.x - pad)
            y1 = max(0, bc.y - pad)
            x2 = min(img_w, bc.x + bc.width + pad)
            y2 = min(img_h, bc.y + bc.height + pad)
            crop = gray[y1:y2, x1:x2]
            if crop.size == 0:
                return

            # Try multiple preprocessing approaches on the cropped region
            attempts = [crop]
            # Otsu
            _, otsu = cv2.threshold(crop, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            attempts.append(otsu)
            # Adaptive threshold
            adapt = cv2.adaptiveThreshold(crop, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                          cv2.THRESH_BINARY, 51, 10)
            attempts.append(adapt)
            # Scale up 2x (helps pyzbar with small/anti-aliased barcodes)
            big = cv2.resize(crop, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
            attempts.append(big)
            _, big_otsu = cv2.threshold(big, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            attempts.append(big_otsu)
            # Sharpen + Otsu at 2x
            sharp_k = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]], dtype=np.float32)
            sharpened = cv2.filter2D(big, -1, sharp_k)
            _, sharp_otsu = cv2.threshold(sharpened, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            attempts.append(sharp_otsu)

            for attempt in attempts:
                decoded = pyzbar.decode(attempt)
                if decoded:
                    obj = decoded[0]
                    bc.data = obj.data.decode('utf-8', errors='replace')
                    bc.barcode_type = self._pyzbar_type_to_zpl(obj.type)
                    bc.confidence = 0.9
                    print(f"[ImageAnalyzer] Decoded barcode region: {bc.barcode_type} = {repr(bc.data)}")
                    return
        except Exception as e:
            print(f"[ImageAnalyzer] Barcode region decode error: {e}")

    def _infer_barcode_orientation(self, gray: np.ndarray, bc: DetectedRegion) -> str:
        """Infer ZPL barcode orientation.

        Returns:
            "N" -> bars are vertical in image (standard horizontal barcode)
            "R" -> bars are horizontal in image (visually vertical barcode)
        """
        try:
            img_h, img_w = gray.shape[:2]
            pad = 2
            x1 = max(0, bc.x + pad)
            y1 = max(0, bc.y + pad)
            x2 = min(img_w, bc.x + bc.width - pad)
            y2 = min(img_h, bc.y + bc.height - pad)
            if x2 - x1 < 10 or y2 - y1 < 10:
                return "R" if bc.height > bc.width * 1.35 else "N"

            crop = gray[y1:y2, x1:x2]
            _, binary = cv2.threshold(crop, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            ch, cw = binary.shape[:2]

            row_scores = []
            for frac in [0.25, 0.4, 0.5, 0.6, 0.75]:
                sy = int(ch * frac)
                if 0 <= sy < ch:
                    row = binary[sy, :]
                    transitions = np.sum(np.abs(np.diff(row.astype(np.int16))) > 0)
                    row_scores.append(int(transitions))

            col_scores = []
            for frac in [0.25, 0.4, 0.5, 0.6, 0.75]:
                sx = int(cw * frac)
                if 0 <= sx < cw:
                    col = binary[:, sx]
                    transitions = np.sum(np.abs(np.diff(col.astype(np.int16))) > 0)
                    col_scores.append(int(transitions))

            avg_row = float(np.mean(row_scores)) if row_scores else 0.0
            avg_col = float(np.mean(col_scores)) if col_scores else 0.0

            if avg_col > avg_row * 1.25:
                return "R"
            if avg_row > avg_col * 1.25:
                return "N"

            return "R" if bc.height > bc.width * 1.35 else "N"
        except Exception:
            return "R" if bc.height > bc.width * 1.35 else "N"

    def _measure_module_width(self, gray: np.ndarray, bc: DetectedRegion,
                              orientation: str = "N") -> int:
        """Measure the narrowest bar (module) width directly from the image pixels.
        Returns module width in pixels (1-10), or 0 if measurement fails."""
        try:
            img_h, img_w = gray.shape[:2]
            # Extract barcode region with small padding
            pad = 2
            x1 = max(0, bc.x + pad)
            y1 = max(0, bc.y + pad)
            x2 = min(img_w, bc.x + bc.width - pad)
            y2 = min(img_h, bc.y + bc.height - pad)
            if x2 - x1 < 10 or y2 - y1 < 5:
                return 0

            crop = gray[y1:y2, x1:x2]
            # Binarize with Otsu
            _, binary = cv2.threshold(crop, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

            # Sample scanlines through the barcode in the axis orthogonal to bars.
            # N: bars vertical  -> sample horizontal lines
            # R: bars horizontal -> sample vertical lines
            ch, cw = binary.shape[:2]
            scanlines = []
            if orientation == "R":
                for frac in [0.35, 0.45, 0.5, 0.55, 0.65]:
                    sx = int(cw * frac)
                    if 0 <= sx < cw:
                        scanlines.append(binary[:, sx])
            else:
                for frac in [0.35, 0.45, 0.5, 0.55, 0.65]:
                    sy = int(ch * frac)
                    if 0 <= sy < ch:
                        scanlines.append(binary[sy, :])

            if not scanlines:
                return 0

            all_widths = []
            for scanline in scanlines:
                # Find run-lengths of consecutive same-value pixels
                runs = []
                current_val = scanline[0]
                run_len = 1
                for i in range(1, len(scanline)):
                    if scanline[i] == current_val:
                        run_len += 1
                    else:
                        runs.append(run_len)
                        current_val = scanline[i]
                        run_len = 1
                runs.append(run_len)

                # Skip leading/trailing quiet zones (first and last runs which are
                # typically wide white space)
                if len(runs) < 5:
                    continue
                # Trim quiet zones: skip first and last run if they're white (255)
                # and much wider than average
                inner_runs = runs[1:-1] if len(runs) > 4 else runs

                if not inner_runs:
                    continue

                # Collect all run widths (each run is a bar or space)
                all_widths.extend(inner_runs)

            if not all_widths:
                return 0

            # The module width is the most common narrow bar width.
            # Use the smallest frequently-occurring run width.
            # Filter out very rare outliers (quiet zones that leaked in).
            from collections import Counter
            counts = Counter(all_widths)
            # Only consider widths that appear at least 3 times
            frequent = {w: c for w, c in counts.items() if c >= 3}
            if not frequent:
                # Fallback: use all
                frequent = counts

            # Find the smallest width that appears frequently
            min_width = min(frequent.keys())

            # Validate: module width should be reasonable (1-10 pixels)
            if 1 <= min_width <= 10:
                return int(min_width)
            elif min_width > 10:
                # Might be scaled up; see if there's a common divisor
                return max(1, min(10, int(round(min_width))))
            return 0
        except Exception as e:
            print(f"[ImageAnalyzer] Module width measurement error: {e}")
            return 0

    def _vlines_to_barcodes(self, line_regions: List[DetectedRegion]):
        """Convert clusters of vertical lines into barcode regions.
        When pyzbar fails on anti-aliased barcodes, individual bars are detected as vlines.
        Groups of 8+ vlines with similar y-position and height indicate a barcode."""
        vlines = [l for l in line_regions if l.region_type == "vline"]
        other_lines = [l for l in line_regions if l.region_type != "vline"]
        if len(vlines) < 8:
            return line_regions, []

        img_h, img_w = self._binary_cache.shape[:2]

        # Group vlines by y position (within 20px tolerance)
        vlines_sorted = sorted(vlines, key=lambda v: v.y)
        groups = []
        current_group = [vlines_sorted[0]]
        for v in vlines_sorted[1:]:
            if abs(v.y - current_group[0].y) < 20:
                current_group.append(v)
            else:
                groups.append(current_group)
                current_group = [v]
        groups.append(current_group)

        barcodes = []
        consumed_vlines = set()
        for group in groups:
            if len(group) < 8:
                continue
            # Check heights are similar (within 30% of median)
            heights = [v.height for v in group]
            median_h = sorted(heights)[len(heights) // 2]
            # Very tall lines are usually table/grid borders, not barcodes
            if median_h > img_h * 0.45:
                continue
            consistent = [v for v in group if abs(v.height - median_h) < median_h * 0.3]
            if len(consistent) < 8:
                continue

            # Split by x-gaps so separate structures in same row don't merge
            consistent = sorted(consistent, key=lambda v: v.x)
            max_gap = max(10, int(np.median([max(1, v.width) for v in consistent]) * 6))
            x_clusters = [[consistent[0]]]
            for v in consistent[1:]:
                prev = x_clusters[-1][-1]
                gap = v.x - (prev.x + prev.width)
                if gap <= max_gap:
                    x_clusters[-1].append(v)
                else:
                    x_clusters.append([v])

            for cluster in x_clusters:
                if len(cluster) < 8:
                    continue

                min_x = min(v.x for v in cluster)
                max_x = max(v.x + v.width for v in cluster)
                min_y = min(v.y for v in cluster)
                max_y = max(v.y + v.height for v in cluster)
                bw = max_x - min_x
                bh = max_y - min_y
                if bw <= 0 or bh <= 0:
                    continue
                # 1D barcode should be wider than tall
                if bw / max(bh, 1) < 1.6:
                    continue
                # Table-like patterns have too few transitions
                if not self._verify_barcode_pattern(self._binary_cache, min_x, min_y, bw, bh):
                    continue

                barcodes.append(DetectedRegion(
                    "barcode", x=min_x, y=min_y,
                    width=bw, height=bh,
                    barcode_type="unknown", confidence=0.5
                ))
                for v in cluster:
                    consumed_vlines.add(id(v))

        remaining_vlines = [v for v in vlines if id(v) not in consumed_vlines]
        return other_lines + remaining_vlines, barcodes

    # ── Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _is_noise_text(text: str, w: int, h: int, img_h: int) -> bool:
        """Filter out garbage OCR results from tick marks, decorations, etc.
        Returns True if the text is likely noise and should be discarded."""
        import re
        # Strip whitespace for analysis
        t = text.strip()
        if not t:
            return True
        # Count actual alphanumeric characters
        alnum = re.sub(r'[^a-zA-Z0-9]', '', t)
        alpha = re.sub(r'[^a-zA-Z]', '', t)

        # Pure non-alphanumeric text (e.g. "]", "=]", "[]", "|")
        if len(alnum) == 0:
            return True

        # Excessively tall text regions are almost always OCR bleed from logos/banners
        if h > img_h * 0.12 and len(alnum) > 4:
            return True

        # Low alphanumeric density with enough symbols usually indicates OCR garbage
        if len(t) >= 8 and len(alnum) / max(len(t), 1) < 0.45:
            return True

        # Long alpha strings with very low vowel ratio are typically gibberish
        if len(alpha) >= 10:
            vowels = len(re.findall(r'[aeiouAEIOU]', alpha))
            if vowels / len(alpha) < 0.15:
                return True

        # Very short text (1-2 alphanum chars) with brackets/symbols → noise from tick marks
        if len(alnum) <= 2 and len(t) > len(alnum):
            return True

        # Single character that isn't a plausible standalone label value
        # (digits and common single-letter labels like "X" are OK)
        if len(alnum) == 1:
            if alnum not in '0123456789XxOo':
                return True  # Non-standard single chars are always noise
            # Even valid single chars - reject if very tall (likely misread graphic)
            if h > img_h * 0.06:
                return True

        # Very small height regions (likely scan artifacts) with short text
        if h < 10 and len(alnum) <= 3:
            return True

        # Short text (2-3 chars) with special characters like }, |, \ → OCR garbage
        if len(alnum) <= 3 and len(t) > len(alnum) + 1:
            import re
            if re.search(r'[{}\|\\~`\^]', t):
                return True

        # Very wide text region with small font → likely merged icon/logo text garbage
        # Real text lines have width/height < ~30, icon text spans are much wider
        if h > 0 and w / h > 8 and len(alnum) > 15:
            # Count short words (<=3 chars) - garbage text from icons has many fragments
            words = t.split()
            if len(words) > 5:
                short_words = sum(1 for word in words if len(word) <= 3)
                # Also check for disconnected/incoherent content
                # (repeated words, mixed fragments)
                unique_words = len(set(w.lower() for w in words))
                if short_words / len(words) > 0.35 or unique_words < len(words) * 0.7:
                    return True

        # Ultra-wide regions with many tokens are often merged OCR of graphics
        if h > 0 and w / h > 12:
            words = t.split()
            if len(words) > 10 and len(alnum) > 20:
                return True

        return False

    def _overlaps_any(self, region: DetectedRegion, others: List[DetectedRegion]) -> bool:
        for other in others:
            overlap = self._overlap_area(region, other)
            area = region.width * region.height
            if area > 0 and overlap / area > 0.4:
                return True
        return False

    def _overlap_area(self, a: DetectedRegion, b: DetectedRegion) -> int:
        x1, y1 = max(a.x, b.x), max(a.y, b.y)
        x2 = min(a.x + a.width, b.x + b.width)
        y2 = min(a.y + a.height, b.y + b.height)
        return (x2 - x1) * (y2 - y1) if x1 < x2 and y1 < y2 else 0

    def _pyzbar_type_to_zpl(self, pyzbar_type: str) -> str:
        mapping = {
            "CODE128": "code128", "CODE39": "code39", "CODE93": "code93",
            "EAN13": "ean13", "EAN8": "ean8", "UPCA": "upca", "UPCE": "upce",
            "I25": "i2of5", "CODABAR": "codabar", "QRCODE": "qrcode",
            "PDF417": "pdf417", "DATAMATRIX": "datamatrix",
        }
        return mapping.get(pyzbar_type, "code128")
