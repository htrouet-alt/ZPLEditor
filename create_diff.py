"""Create pixel-by-pixel diff images between input and rendered ZPL output."""
import cv2
import numpy as np
import os

os.makedirs('Examples/diff', exist_ok=True)

for label in ['label_2', 'label_3']:
    inp = cv2.imread(f'Examples/input/{label}.png', cv2.IMREAD_GRAYSCALE)
    out = cv2.imread(f'Examples/output/ZplImage/{label}.png', cv2.IMREAD_GRAYSCALE)
    if inp is None or out is None:
        print(f'{label}: SKIP')
        continue
    if inp.shape[0] != out.shape[0] or inp.shape[1] != out.shape[1]:
        out = cv2.resize(out, (inp.shape[1], inp.shape[0]))

    _, bin_in = cv2.threshold(inp, 128, 255, cv2.THRESH_BINARY_INV)
    _, bin_out = cv2.threshold(out, 128, 255, cv2.THRESH_BINARY_INV)

    h, w = inp.shape

    # ---- DIFF IMAGE ----
    # Beyaz zemin
    diff = np.ones((h, w, 3), dtype=np.uint8) * 255
    # Dogru eslesen siyah pikseller -> koyu gri
    match_black = (bin_in > 0) & (bin_out > 0)
    diff[match_black] = [80, 80, 80]
    # Eksik (inputta var, outputta yok) -> KIRMIZI
    missed = (bin_in > 0) & (bin_out == 0)
    diff[missed] = [0, 0, 255]
    # Fazla (inputta yok, outputta var) -> MAVI/TURUNCU
    false_pos = (bin_in == 0) & (bin_out > 0)
    diff[false_pos] = [255, 128, 0]

    cv2.imwrite(f'Examples/diff/{label}_diff.png', diff)

    # ---- SIDE BY SIDE (input | output | diff) ----
    inp_color = cv2.cvtColor(inp, cv2.COLOR_GRAY2BGR)
    out_color = cv2.cvtColor(out, cv2.COLOR_GRAY2BGR)

    sep = np.ones((h, 3, 3), dtype=np.uint8) * 128
    combined = np.hstack([inp_color, sep, out_color, sep, diff])
    cv2.imwrite(f'Examples/diff/{label}_sidebyside.png', combined)

    # Stats
    total_fg = int(np.sum(bin_in > 0))
    n_missed = int(np.sum(missed))
    n_fp = int(np.sum(false_pos))
    n_match = int(np.sum(match_black))

    print(f'=== {label} ===')
    print(f'  Input siyah piksel: {total_fg}')
    print(f'  Dogru (gri):        {n_match} ({n_match / max(total_fg, 1) * 100:.1f}%)')
    print(f'  EKSIK (kirmizi):    {n_missed} ({n_missed / max(total_fg, 1) * 100:.1f}%)')
    print(f'  FAZLA (turuncu):    {n_fp}')

    # Region-by-region analysis: which content is fully missing?
    print(f'\n  --- Tamamen eksik bolgeler (kirmizi yogunluk) ---')
    band_size = 30
    for y in range(0, h, band_size):
        band_missed = np.sum(missed[y:y + band_size, :])
        band_fg = np.sum(bin_in[y:y + band_size, :] > 0)
        if band_fg > 50 and band_missed > band_fg * 0.5:
            # Find x extent of the missed content
            missed_cols = np.where(np.sum(missed[y:y + band_size, :], axis=0) > 0)[0]
            if len(missed_cols) > 0:
                x_start = int(missed_cols[0])
                x_end = int(missed_cols[-1])
                miss_pct = band_missed / band_fg * 100
                print(f'    y={y:4d}-{y + band_size:4d}: x=[{x_start},{x_end}] '
                      f'eksik={band_missed}/{band_fg} ({miss_pct:.0f}%)')
    print()

print('Renk kodlari:')
print('  Gri     = dogru eslesen (input=siyah, output=siyah)')
print('  KIRMIZI = eksik (input=siyah, output=beyaz) -> kayip icerik!')
print('  TURUNCU = fazla (input=beyaz, output=siyah) -> gereksiz icerik')
print('  Beyaz   = her ikisi de beyaz (dogru)')
