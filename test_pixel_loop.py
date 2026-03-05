"""
Test: Image → ZPL → Local Render → Pixel Similarity comparison.

Pipeline per label:
  1. Load input PNG from TestData/input/
  2. ImageAnalyzer → detect regions
  3. ZPLFromImage → generate ZPL code
  4. ZPLRenderer  → render ZPL to PNG locally (no Labelary API)
  5. Compare original vs rendered pixel-by-pixel

Outputs:
  TestData/output/ZPLCode/   → generated .zpl files
  TestData/output/ZplImage/  → rendered .png files
  TestData/output/Diff/      → side-by-side comparison images

Pass threshold: >= 95% pixel similarity (relaxed 1px tolerance)
"""

import os
import sys
import time
import glob
import cv2
import numpy as np

# -- paths --------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR = os.path.join(BASE_DIR, "TestData", "input")
OUT_ZPL = os.path.join(BASE_DIR, "TestData", "output", "ZPLCode")
OUT_IMG = os.path.join(BASE_DIR, "TestData", "output", "ZplImage")
OUT_DIFF = os.path.join(BASE_DIR, "TestData", "output", "Diff")

os.makedirs(OUT_ZPL, exist_ok=True)
os.makedirs(OUT_IMG, exist_ok=True)
os.makedirs(OUT_DIFF, exist_ok=True)

# Ensure project root is on path
sys.path.insert(0, BASE_DIR)

# -- env flags ----------------------------------------------------------
# Disable full-bitmap fallback so we test structured ZPL accuracy
os.environ["ZPL_FORCE_FULL_BITMAP_ON_LOW_SIMILARITY"] = "0"
os.environ["ZPL_ALLOW_FULL_BITMAP_FALLBACK"] = "0"

PASS_THRESHOLD = 95.0  # minimum % pixel similarity to pass


def pixel_similarity(img_a: np.ndarray, img_b: np.ndarray, tolerance_px: int = 1) -> float:
    """Compute relaxed pixel similarity between two grayscale images.
    Uses 1px dilation tolerance to handle sub-pixel rendering differences."""

    # Resize to same dimensions if needed
    h = max(img_a.shape[0], img_b.shape[0])
    w = max(img_a.shape[1], img_b.shape[1])
    if img_a.shape[:2] != (h, w):
        img_a = cv2.resize(img_a, (w, h), interpolation=cv2.INTER_NEAREST)
    if img_b.shape[:2] != (h, w):
        img_b = cv2.resize(img_b, (w, h), interpolation=cv2.INTER_NEAREST)

    # Binarize
    _, bin_a = cv2.threshold(img_a, 128, 255, cv2.THRESH_BINARY)
    _, bin_b = cv2.threshold(img_b, 128, 255, cv2.THRESH_BINARY)

    # Strict match
    strict_match = np.sum(bin_a == bin_b)
    total = bin_a.size
    strict_pct = 100.0 * strict_match / total

    # Relaxed: dilate both and check again
    if tolerance_px > 0:
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT,
                                           (2 * tolerance_px + 1, 2 * tolerance_px + 1))
        dil_a = cv2.dilate(255 - bin_a, kernel)
        dil_b = cv2.dilate(255 - bin_b, kernel)

        # For each black pixel in A, is there a nearby black pixel in B?
        ink_a = (bin_a == 0)
        ink_b = (bin_b == 0)
        a_covered = ink_a & (dil_b > 0)
        b_covered = ink_b & (dil_a > 0)
        white_match = (~ink_a & ~ink_b)

        matched = np.sum(a_covered) + np.sum(b_covered) + np.sum(white_match)
        # Avoid double-counting: total compared = ink_a + ink_b + white_match
        compared = np.sum(ink_a) + np.sum(ink_b) + np.sum(white_match)
        relaxed_pct = 100.0 * matched / max(compared, 1)
    else:
        relaxed_pct = strict_pct

    return relaxed_pct


def create_diff_image(original: np.ndarray, rendered: np.ndarray) -> np.ndarray:
    """Create a side-by-side comparison with diff overlay."""
    h = max(original.shape[0], rendered.shape[0])
    w = max(original.shape[1], rendered.shape[1])

    # Resize to same dims
    orig_resized = cv2.resize(original, (w, h), interpolation=cv2.INTER_NEAREST)
    rend_resized = cv2.resize(rendered, (w, h), interpolation=cv2.INTER_NEAREST)

    # Binarize
    _, bin_orig = cv2.threshold(orig_resized, 128, 255, cv2.THRESH_BINARY)
    _, bin_rend = cv2.threshold(rend_resized, 128, 255, cv2.THRESH_BINARY)

    # Diff: green = match, red = original only, blue = rendered only
    diff = np.zeros((h, w, 3), dtype=np.uint8)
    diff[:] = (255, 255, 255)  # white background

    both_black = (bin_orig == 0) & (bin_rend == 0)
    orig_only = (bin_orig == 0) & (bin_rend != 0)
    rend_only = (bin_orig != 0) & (bin_rend == 0)

    diff[both_black] = (0, 0, 0)       # black = matched ink
    diff[orig_only] = (0, 0, 255)      # red = missed (in original, not in rendered)
    diff[rend_only] = (255, 0, 0)      # blue = false positive (in rendered, not in original)

    # Convert originals to color for side-by-side
    orig_color = cv2.cvtColor(orig_resized, cv2.COLOR_GRAY2BGR)
    rend_color = cv2.cvtColor(rend_resized, cv2.COLOR_GRAY2BGR)

    # Add labels
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(orig_color, "Original", (10, 30), font, 1.0, (0, 0, 255), 2)
    cv2.putText(rend_color, "Rendered", (10, 30), font, 1.0, (255, 0, 0), 2)
    cv2.putText(diff, "Diff", (10, 30), font, 1.0, (0, 128, 0), 2)

    # Side by side: Original | Rendered | Diff
    separator = np.ones((h, 3, 3), dtype=np.uint8) * 128
    combined = np.hstack([orig_color, separator, rend_color, separator, diff])
    return combined


def safe_filename(name: str) -> str:
    """Sanitize filename for output."""
    return name.replace(" ", "_").replace("(", "").replace(")", "")


def run_test():
    from zpl_editor.image_processing.image_analyzer import ImageAnalyzer
    from zpl_editor.image_processing.zpl_from_image import ZPLFromImage
    from zpl_editor.core.zpl_renderer import render_zpl_to_png_bytes

    # Find all input images
    patterns = [os.path.join(INPUT_DIR, "*.png"),
                os.path.join(INPUT_DIR, "*.jpg"),
                os.path.join(INPUT_DIR, "*.bmp")]
    input_files = []
    for pat in patterns:
        input_files.extend(glob.glob(pat))
    input_files.sort()

    if not input_files:
        print(f"ERROR: No images found in {INPUT_DIR}")
        sys.exit(1)

    print(f"Found {len(input_files)} test images in {INPUT_DIR}")
    print("=" * 70)

    analyzer = ImageAnalyzer()
    generator = ZPLFromImage()
    results = []

    for img_path in input_files:
        label_name = os.path.splitext(os.path.basename(img_path))[0]
        safe_name = safe_filename(label_name)
        print(f"\n{'-' * 70}")
        print(f"Testing: {label_name}")
        print(f"{'-' * 70}")

        # 1. Load image
        image = cv2.imread(img_path)
        if image is None:
            print(f"  SKIP: Cannot read {img_path}")
            results.append((label_name, 0.0, "SKIP"))
            continue

        img_h, img_w = image.shape[:2]
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        print(f"  Image size: {img_w}x{img_h}")

        # 2. Analyze image
        t0 = time.time()
        regions = analyzer.analyze(image)
        t_analyze = time.time() - t0
        print(f"  Detected {len(regions)} regions in {t_analyze:.1f}s")

        # 3. Generate ZPL
        t0 = time.time()
        zpl_code = generator.generate(image, regions,
                                       label_width=img_w, label_height=img_h)
        t_gen = time.time() - t0
        print(f"  Generated ZPL ({len(zpl_code)} chars) in {t_gen:.1f}s")

        # Save ZPL
        zpl_path = os.path.join(OUT_ZPL, f"{safe_name}.zpl")
        with open(zpl_path, "w", encoding="utf-8") as f:
            f.write(zpl_code)

        # 4. Render ZPL locally
        t0 = time.time()
        png_bytes = render_zpl_to_png_bytes(zpl_code, dpi=203)
        t_render = time.time() - t0

        if png_bytes is None:
            print(f"  FAIL: Local render returned None")
            results.append((label_name, 0.0, "RENDER_FAIL"))
            continue

        # Decode rendered PNG
        arr = np.frombuffer(png_bytes, dtype=np.uint8)
        rendered = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if rendered is None:
            print(f"  FAIL: Cannot decode rendered PNG")
            results.append((label_name, 0.0, "DECODE_FAIL"))
            continue

        rendered_gray = cv2.cvtColor(rendered, cv2.COLOR_BGR2GRAY)
        rh, rw = rendered_gray.shape[:2]
        print(f"  Rendered size: {rw}x{rh} in {t_render:.1f}s")

        # Save rendered image
        render_path = os.path.join(OUT_IMG, f"{safe_name}.png")
        cv2.imwrite(render_path, rendered)

        # 5. Pixel similarity
        similarity = pixel_similarity(gray, rendered_gray, tolerance_px=1)
        passed = similarity >= PASS_THRESHOLD
        status = "PASS" if passed else "FAIL"
        results.append((label_name, similarity, status))

        print(f"  Similarity: {similarity:.1f}%  [{status}]")

        # 6. Create diff image
        diff_img = create_diff_image(gray, rendered_gray)
        diff_path = os.path.join(OUT_DIFF, f"{safe_name}_diff.png")
        cv2.imwrite(diff_path, diff_img)

    # -- Summary --------------------------------------------------------
    print(f"\n{'=' * 70}")
    print("SUMMARY")
    print(f"{'=' * 70}")

    all_pass = True
    for label_name, similarity, status in results:
        icon = "OK" if status == "PASS" else "XX"
        print(f"  [{icon}] {label_name:30s}  {similarity:5.1f}%  {status}")
        if status != "PASS":
            all_pass = False

    passed_count = sum(1 for _, _, s in results if s == "PASS")
    total_count = len(results)
    print(f"\n  {passed_count}/{total_count} passed (threshold: >= {PASS_THRESHOLD}%)")

    if all_pass:
        print("\n  ALL TESTS PASSED!")
    else:
        print("\n  SOME TESTS FAILED.")
        sys.exit(1)


if __name__ == "__main__":
    run_test()
