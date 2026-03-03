"""Detailed comparison between input and output labels."""
import cv2
import numpy as np

for label in ['label_1', 'label_2', 'label_3', 'label_4']:
    inp = cv2.imread(f'Examples/input/{label}.png', cv2.IMREAD_GRAYSCALE)
    out = cv2.imread(f'Examples/output/ZplImage/{label}.png', cv2.IMREAD_GRAYSCALE)
    if inp is None or out is None:
        continue
    if inp.shape != out.shape:
        out = cv2.resize(out, (inp.shape[1], inp.shape[0]))
    _, bin_in = cv2.threshold(inp, 128, 255, cv2.THRESH_BINARY_INV)
    _, bin_out = cv2.threshold(out, 128, 255, cv2.THRESH_BINARY_INV)
    sim_strict = np.sum(bin_in == bin_out) / bin_in.size * 100

    # Relaxed: allow 1px shift (dilate both, then compare)
    kernel = np.ones((3, 3), np.uint8)
    bin_in_d = cv2.dilate(bin_in, kernel, iterations=1)
    bin_out_d = cv2.dilate(bin_out, kernel, iterations=1)
    # A pixel is "matched" if it's covered by the dilated version of the other
    match_relaxed = ((bin_in_d > 0) | (bin_out == 0)) & ((bin_out_d > 0) | (bin_in == 0))
    sim_relaxed = np.sum(match_relaxed) / bin_in.size * 100

    print(f'{label}: strict={sim_strict:.1f}%, relaxed(1px)={sim_relaxed:.1f}%')

    # Detailed: show worst 50px bands with content type
    h, w = inp.shape[:2]
    print(f'  Worst Y-bands (strict):')
    band_diffs = []
    for y in range(0, h, 50):
        band_in = bin_in[y:y+50, :]
        band_out = bin_out[y:y+50, :]
        fg_in = np.sum(band_in > 0)
        if fg_in < 50:
            continue
        diff = np.sum(band_in != band_out)
        diff_pct = diff / band_in.size * 100
        missed = np.sum((band_in > 0) & (band_out == 0))
        missed_pct = missed / fg_in * 100
        false_pos = np.sum((band_out > 0) & (band_in == 0))
        band_diffs.append((y, diff_pct, missed_pct, false_pos))

    band_diffs.sort(key=lambda x: -x[1])
    for y, diff, missed, fp in band_diffs[:8]:
        print(f'    y={y:4d}: diff={diff:.1f}%, missed={missed:.0f}%, false+={fp}px')
    print()
