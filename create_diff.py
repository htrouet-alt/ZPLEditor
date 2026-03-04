"""Create robust diff images between input and rendered ZPL output.

Improvements:
- Otsu threshold instead of fixed threshold
- Small shift alignment search (±2 px)
- Strict + tolerant similarity metrics
- Worst-band and largest-component diagnostics
"""
import os
import cv2
import numpy as np


INPUT_DIR = 'Examples/input'
OUTPUT_DIR = 'Examples/output/ZplImage'
DIFF_DIR = 'Examples/diff'


def _load_pair(label: str):
    inp = cv2.imread(f'{INPUT_DIR}/{label}.png', cv2.IMREAD_GRAYSCALE)
    out = cv2.imread(f'{OUTPUT_DIR}/{label}.png', cv2.IMREAD_GRAYSCALE)
    if inp is None or out is None:
        return None, None
    if inp.shape != out.shape:
        out = cv2.resize(out, (inp.shape[1], inp.shape[0]), interpolation=cv2.INTER_NEAREST)
    return inp, out


def _to_binary(img_gray: np.ndarray) -> np.ndarray:
    _, binary = cv2.threshold(img_gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return binary


def _shift_binary(binary: np.ndarray, dx: int, dy: int) -> np.ndarray:
    h, w = binary.shape[:2]
    m = np.float32([[1, 0, dx], [0, 1, dy]])
    return cv2.warpAffine(binary, m, (w, h), flags=cv2.INTER_NEAREST,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=0)


def _best_small_shift(bin_in: np.ndarray, bin_out: np.ndarray, max_shift: int = 2):
    best = {"dx": 0, "dy": 0, "score": -1.0, "shifted": bin_out}
    total = bin_in.size
    for dy in range(-max_shift, max_shift + 1):
        for dx in range(-max_shift, max_shift + 1):
            shifted = _shift_binary(bin_out, dx, dy)
            score = float(np.sum(bin_in == shifted)) / max(total, 1)
            if score > best["score"]:
                best = {"dx": dx, "dy": dy, "score": score, "shifted": shifted}
    return best


def _build_diff(bin_in: np.ndarray, bin_out: np.ndarray):
    h, w = bin_in.shape[:2]
    diff = np.ones((h, w, 3), dtype=np.uint8) * 255

    match_black = (bin_in > 0) & (bin_out > 0)
    missed = (bin_in > 0) & (bin_out == 0)
    false_pos = (bin_in == 0) & (bin_out > 0)

    diff[match_black] = [80, 80, 80]
    diff[missed] = [0, 0, 255]
    diff[false_pos] = [255, 128, 0]

    return diff, match_black, missed, false_pos


def _tolerant_similarity(bin_in: np.ndarray, bin_out: np.ndarray, tol_px: int = 1) -> float:
    kernel = np.ones((2 * tol_px + 1, 2 * tol_px + 1), np.uint8)
    bin_in_d = cv2.dilate(bin_in, kernel, iterations=1)
    bin_out_d = cv2.dilate(bin_out, kernel, iterations=1)
    match_relaxed = ((bin_in_d > 0) | (bin_out == 0)) & ((bin_out_d > 0) | (bin_in == 0))
    return float(np.sum(match_relaxed)) / max(bin_in.size, 1) * 100


def _largest_components(mask: np.ndarray, top_k: int = 5):
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
    comps = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if area < 20:
            continue
        comps.append((int(area), int(x), int(y), int(w), int(h)))
    comps.sort(reverse=True)
    return comps[:top_k]


def _process_label(label: str):
    inp, out = _load_pair(label)
    if inp is None or out is None:
        print(f'{label}: SKIP (input/output bulunamadi)')
        return

    bin_in = _to_binary(inp)
    bin_out_raw = _to_binary(out)

    align = _best_small_shift(bin_in, bin_out_raw, max_shift=2)
    bin_out = align["shifted"]

    diff, match_black, missed, false_pos = _build_diff(bin_in, bin_out)

    h, _ = inp.shape[:2]
    inp_color = cv2.cvtColor(inp, cv2.COLOR_GRAY2BGR)
    out_color = cv2.cvtColor(out, cv2.COLOR_GRAY2BGR)
    sep = np.ones((h, 3, 3), dtype=np.uint8) * 128
    combined = np.hstack([inp_color, sep, out_color, sep, diff])

    cv2.imwrite(f'{DIFF_DIR}/{label}_diff.png', diff)
    cv2.imwrite(f'{DIFF_DIR}/{label}_sidebyside.png', combined)

    fg_in = int(np.sum(bin_in > 0))
    n_missed = int(np.sum(missed))
    n_fp = int(np.sum(false_pos))
    n_match_black = int(np.sum(match_black))
    strict_similarity = float(np.sum(bin_in == bin_out)) / max(bin_in.size, 1) * 100
    relaxed_similarity = _tolerant_similarity(bin_in, bin_out, tol_px=1)

    print(f'=== {label} ===')
    print(f'  Align shift: dx={align["dx"]}, dy={align["dy"]}, strict={align["score"] * 100:.2f}%')
    print(f'  Input siyah piksel: {fg_in}')
    print(f'  Dogru (gri):        {n_match_black} ({n_match_black / max(fg_in, 1) * 100:.1f}%)')
    print(f'  EKSIK (kirmizi):    {n_missed} ({n_missed / max(fg_in, 1) * 100:.1f}%)')
    print(f'  FAZLA (turuncu):    {n_fp}')
    print(f'  Similarity: strict={strict_similarity:.2f}%, relaxed(1px)={relaxed_similarity:.2f}%')

    print(f'\n  --- En kotu Y-bandlari (30px) ---')
    band_size = 30
    band_rows = []
    for y in range(0, h, band_size):
        band_in = bin_in[y:y + band_size, :]
        band_out = bin_out[y:y + band_size, :]
        fg_band = np.sum(band_in > 0)
        if fg_band < 50:
            continue
        n_miss = np.sum((band_in > 0) & (band_out == 0))
        miss_pct = n_miss / max(fg_band, 1) * 100
        band_rows.append((miss_pct, y, y + band_size, int(n_miss), int(fg_band)))

    band_rows.sort(reverse=True)
    for miss_pct, y1, y2, n_miss, fg_band in band_rows[:8]:
        if miss_pct < 10:
            continue
        print(f'    y={y1:4d}-{y2:4d}: eksik={n_miss}/{fg_band} ({miss_pct:.0f}%)')

    print(f'\n  --- En buyuk eksik bloklar ---')
    for area, x, y, w, h in _largest_components(missed, top_k=5):
        print(f'    area={area:5d} bbox=({x},{y},{w},{h})')
    print()


def main():
    os.makedirs(DIFF_DIR, exist_ok=True)
    labels = []
    for fn in sorted(os.listdir(INPUT_DIR)):
        if fn.lower().endswith('.png'):
            labels.append(os.path.splitext(fn)[0])

    if not labels:
        print('Input label bulunamadi: Examples/input')
        return

    for label in labels:
        _process_label(label)

    print('Renk kodlari:')
    print('  Gri     = dogru eslesen (input=siyah, output=siyah)')
    print('  KIRMIZI = eksik (input=siyah, output=beyaz) -> kayip icerik')
    print('  TURUNCU = fazla (input=beyaz, output=siyah) -> gereksiz icerik')
    print('  Beyaz   = her ikisi de beyaz (dogru)')


if __name__ == '__main__':
    main()
