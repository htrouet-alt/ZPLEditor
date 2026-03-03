"""
Pixel-Perfect ZPL Test Loop
Iteratively tests and reports label similarity.
"""
import cv2
import numpy as np
import os
import sys
import time
import requests

sys.path.insert(0, os.path.dirname(__file__))

from zpl_editor.image_processing.image_analyzer import ImageAnalyzer
from zpl_editor.image_processing.zpl_from_image import ZPLFromImage


def render_via_labelary(zpl_code: str, width_inches, height_inches, dpi=203,
                        max_retries=3) -> bytes:
    dpmm = round(dpi / 25.4)
    url = f"http://api.labelary.com/v1/printers/{dpmm}dpmm/labels/{width_inches}x{height_inches}/0/"
    headers = {"Accept": "image/png"}
    for attempt in range(max_retries):
        try:
            resp = requests.post(url, data=zpl_code.encode("utf-8"),
                                 headers=headers, timeout=30)
            if resp.status_code == 200:
                return resp.content
            print(f"  Labelary {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            print(f"  Labelary attempt {attempt+1} failed: {e}")
        if attempt < max_retries - 1:
            time.sleep(2)
    return None


def compare_images(input_path: str, output_path: str):
    """Compare input vs output images, return similarity metrics."""
    img_in = cv2.imread(input_path, cv2.IMREAD_GRAYSCALE)
    img_out = cv2.imread(output_path, cv2.IMREAD_GRAYSCALE)
    if img_in is None or img_out is None:
        return None

    # Resize output to match input if needed
    if img_in.shape != img_out.shape:
        img_out = cv2.resize(img_out, (img_in.shape[1], img_in.shape[0]),
                             interpolation=cv2.INTER_AREA)

    # Binary threshold
    _, bin_in = cv2.threshold(img_in, 128, 255, cv2.THRESH_BINARY_INV)
    _, bin_out = cv2.threshold(img_out, 128, 255, cv2.THRESH_BINARY_INV)

    fg_in = np.sum(bin_in > 0)
    fg_out = np.sum(bin_out > 0)
    total_pixels = img_in.shape[0] * img_in.shape[1]

    # Match: pixels that are foreground in both OR background in both
    match = np.sum(bin_in == bin_out)
    similarity = match / total_pixels * 100

    # Missed: foreground in input but not in output
    missed = np.sum((bin_in > 0) & (bin_out == 0))
    missed_pct = missed / max(fg_in, 1) * 100

    # False positive: foreground in output but not in input
    false_pos = np.sum((bin_out > 0) & (bin_in == 0))
    false_pos_pct = false_pos / max(fg_out, 1) * 100

    # Analyze worst regions (50px Y-bands)
    worst_bands = []
    band_size = 50
    for band_y in range(0, img_in.shape[0], band_size):
        band_in = bin_in[band_y:band_y + band_size, :]
        band_out = bin_out[band_y:band_y + band_size, :]
        band_fg_in = np.sum(band_in > 0)
        if band_fg_in > 100:  # Only significant bands
            band_missed = np.sum((band_in > 0) & (band_out == 0))
            band_missed_pct = band_missed / band_fg_in * 100
            if band_missed_pct > 50:
                worst_bands.append((band_y, band_missed_pct, band_fg_in))

    return {
        "similarity": similarity,
        "missed_pct": missed_pct,
        "false_pos_pct": false_pos_pct,
        "fg_in": fg_in,
        "fg_out": fg_out,
        "worst_bands": sorted(worst_bands, key=lambda x: -x[1])[:5]
    }


def process_and_compare(iteration: int):
    """Process all labels and return comparison results."""
    base_dir = os.path.dirname(__file__)
    input_dir = os.path.join(base_dir, "Examples", "input")
    zpl_dir = os.path.join(base_dir, "Examples", "output", "ZPLCode")
    img_dir = os.path.join(base_dir, "Examples", "output", "ZplImage")

    os.makedirs(zpl_dir, exist_ok=True)
    os.makedirs(img_dir, exist_ok=True)

    results = {}
    analyzer = ImageAnalyzer()
    generator = ZPLFromImage()

    for filename in sorted(os.listdir(input_dir)):
        if not filename.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
            continue

        name = os.path.splitext(filename)[0]
        input_path = os.path.join(input_dir, filename)
        zpl_path = os.path.join(zpl_dir, f"{name}.zpl")
        img_path = os.path.join(img_dir, f"{name}.png")

        print(f"\n--- {name} ---")

        # Load and analyze
        image = cv2.imread(input_path)
        if image is None:
            print(f"  ERROR: Could not load {input_path}")
            continue

        img_h, img_w = image.shape[:2]
        dpi = 203
        aspect = img_w / max(img_h, 1)

        # Determine label dimensions
        if 0.85 < aspect < 1.15:
            label_w, label_h = img_w, img_h
        elif img_w > img_h * 1.2:
            label_w, label_h = img_w, img_h
        else:
            label_w, label_h = 812, 1218

        print(f"  Image: {img_w}x{img_h}, Label: {label_w}x{label_h}")

        regions = analyzer.analyze(image)
        type_counts = {}
        for r in regions:
            type_counts[r.region_type] = type_counts.get(r.region_type, 0) + 1
        print(f"  Detected: {len(regions)} regions {type_counts}")

        zpl_code = generator.generate(image, regions, label_w, label_h, dpi)

        with open(zpl_path, "w", encoding="utf-8") as f:
            f.write(zpl_code)
        print(f"  ZPL: {len(zpl_code)} bytes")

        # Render via Labelary
        w_inches = round(label_w / dpi, 2)
        h_inches = round(label_h / dpi, 2)
        png_data = render_via_labelary(zpl_code, w_inches, h_inches, dpi)
        if png_data:
            with open(img_path, "wb") as f:
                f.write(png_data)

            # Compare
            metrics = compare_images(input_path, img_path)
            if metrics:
                results[name] = metrics
                print(f"  Similarity: {metrics['similarity']:.1f}%")
                print(f"  Missed: {metrics['missed_pct']:.1f}%, False+: {metrics['false_pos_pct']:.1f}%")
                if metrics['worst_bands']:
                    print(f"  Worst bands: {[(y, f'{p:.0f}%') for y, p, _ in metrics['worst_bands'][:3]]}")
        else:
            print(f"  ERROR: Labelary render failed")

        time.sleep(1)  # Rate limit

    return results


if __name__ == "__main__":
    results = process_and_compare(1)

    print("\n" + "="*60)
    print("ITERATION 1 RESULTS")
    print("="*60)
    print(f"{'Label':<15} {'Similarity':>10} {'Missed':>10} {'False+':>10}")
    print("-" * 50)

    all_pass = True
    for name in sorted(results.keys()):
        m = results[name]
        status = "OK" if m['similarity'] >= 95 else "FAIL"
        print(f"{name:<15} {m['similarity']:>9.1f}% {m['missed_pct']:>9.1f}% {m['false_pos_pct']:>9.1f}%  [{status}]")
        if m['similarity'] < 95:
            all_pass = False

    if all_pass:
        print("\nALL LABELS PASS (>= 95% similarity)")
    else:
        print(f"\nSome labels below 95% - need further fixes")
