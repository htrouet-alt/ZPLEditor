"""
Generate diverse ZPL cargo labels and render them as PNG test inputs.
Based on ZplPrompt.txt specifications.
"""
import os
import sys
import numpy as np
import cv2

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

OUT_ZPL = os.path.join(BASE_DIR, "TestData", "generated_zpl")
OUT_PNG = os.path.join(BASE_DIR, "TestData", "input")
os.makedirs(OUT_ZPL, exist_ok=True)
os.makedirs(OUT_PNG, exist_ok=True)


# ── Label 1: Layout A ─ Info top, barcode middle, QR bottom-right ─────
LABEL_1 = """^XA
^PW812^LL1218
^CI28
^FO0,0^GB812,1218,2^FS

^FX -- Kargo Firma Adi --
^FO30,30^A0N,36,36^FDYurtici Kargo^FS

^FX -- Ayirici --
^FO30,80^GB750,2,2^FS

^FX -- Alici Bilgileri --
^FO30,100^A0N,24,24^FDAlici:^FS
^FO30,135^A0N,28,28^FDAhmet Yilmaz^FS
^FO30,175^A0N,20,20^FDAtaturk Cad. No:45/3^FS
^FO30,205^A0N,20,20^FDKadikoy / Istanbul^FS
^FO30,235^A0N,20,20^FDTel: 0532 123 4567^FS

^FX -- Ayirici --
^FO30,275^GB750,2,2^FS

^FX -- Satis Kanali --
^FO30,300^A0N,44,44^FDTrendyol^FS

^FX -- Ayirici --
^FO30,360^GB750,2,2^FS

^FX -- Siparis ve Gonderi No --
^FO30,385^A0N,20,20^FDSiparis No: TRN-2024-987654^FS
^FO30,415^A0N,20,20^FDGonderi No: 7290012345678^FS

^FX -- Ayirici --
^FO30,455^GB750,2,2^FS

^FX -- Barkod (Code 128, ortada) --
^FO120,490^BY3
^BCN,120,Y,N,N
^FD7290012345678^FS

^FX -- Ayirici --
^FO30,660^GB750,2,2^FS

^FX -- Ek Bilgiler --
^FO30,685^A0N,20,20^FDTarih: 05.03.2026^FS
^FO30,715^A0N,20,20^FDAgirlk: 1.2 kg^FS
^FO30,745^A0N,20,20^FDKoli: 1/1^FS

^FX -- QR Kod (sag alt) --
^FO580,900^BQN,2,5
^FDQA,https://kargo.track/7290012345678^FS

^XZ"""


# ── Label 2: Layout C ─ QR top-right, barcode middle, info left ───────
LABEL_2 = """^XA
^PW812^LL1218
^CI28
^FO0,0^GB812,1218,2^FS

^FX -- Kargo Firma Adi --
^FO30,30^A0N,32,32^FDAras Kargo^FS

^FX -- QR Kod (sag ust) --
^FO600,30^BQN,2,4
^FDQA,https://aras.track/8801234567890^FS

^FX -- Ayirici --
^FO30,90^GB750,2,2^FS

^FX -- Alici Bilgileri --
^FO30,110^A0N,22,22^FDAlici:^FS
^FO30,142^A0N,26,26^FDFatma Demir^FS
^FO30,180^A0N,20,20^FDCumhuriyet Mah. Lale Sok. No:12^FS
^FO30,210^A0N,20,20^FDNilfer / Bursa^FS
^FO30,240^A0N,20,20^FDPosta Kodu: 16110^FS
^FO30,270^A0N,20,20^FDTel: 0544 987 6543^FS

^FX -- Ayirici --
^FO30,310^GB750,2,2^FS

^FX -- Satis Kanali --
^FO30,340^A0N,40,40^FDN11^FS

^FX -- Ayirici --
^FO30,395^GB750,2,2^FS

^FX -- Siparis ve Gonderi --
^FO30,420^A0N,20,20^FDSiparis No: N11-88776655^FS
^FO30,450^A0N,20,20^FDGonderi No: 8801234567890^FS
^FO30,480^A0N,20,20^FDTarih: 05.03.2026^FS
^FO30,510^A0N,20,20^FDAgirlk: 0.8 kg  Koli: 1/1^FS

^FX -- Ayirici --
^FO30,550^GB750,2,2^FS

^FX -- Barkod (Code 39, ortada) --
^FO80,590^BY2
^B3N,N,130,Y,N
^FD8801234567890^FS

^XZ"""


# ── Label 3: Layout D ─ Info top, QR+barcode yan yana altta ───────────
LABEL_3 = """^XA
^PW812^LL1218
^CI28
^FO0,0^GB812,1218,2^FS

^FX -- Kargo Firma Adi --
^FO30,25^A0N,34,34^FDMNG Kargo^FS

^FX -- Ayirici --
^FO30,72^GB750,2,2^FS

^FX -- Alici --
^FO30,95^A0N,22,22^FDAlici:^FS
^FO30,127^A0N,26,26^FDMehmet Kaya^FS
^FO30,163^A0N,18,18^FDIstiklal Mah. Gul Cad. No:78 D:5^FS
^FO30,191^A0N,18,18^FDBornova / Izmir 35040^FS
^FO30,219^A0N,18,18^FDTel: 0555 222 3344^FS

^FX -- Ayirici --
^FO30,255^GB750,2,2^FS

^FX -- Satis Kanali --
^FO30,280^A0N,42,42^FDHepsiburada^FS

^FX -- Ayirici --
^FO30,340^GB750,2,2^FS

^FX -- Siparis No --
^FO30,365^A0N,20,20^FDSiparis: HB-2026-112233^FS
^FO30,395^A0N,20,20^FDGonderi: 5567890123456^FS

^FX -- Ayirici --
^FO30,435^GB750,2,2^FS

^FX -- Ek bilgiler --
^FO30,460^A0N,18,18^FDTarih: 04.03.2026^FS
^FO30,488^A0N,18,18^FDAgirlk: 2.5 kg^FS
^FO30,516^A0N,18,18^FDKoli: 1/2^FS
^FO400,460^A0N,18,18^FDUrun: Elektronik^FS
^FO400,488^A0N,18,18^FDOdeme: Kredi Karti^FS

^FX -- Ayirici --
^FO30,550^GB750,2,2^FS

^FX -- QR Kod (sol alt) --
^FO40,590^BQN,2,5
^FDQA,https://hb.track/5567890123456^FS

^FX -- Barkod (Code 128, sag alt) --
^FO370,620^BY2
^BCN,100,Y,N,N
^FD5567890123456^FS

^XZ"""


# ── Label 4: Layout F ─ Iki sutunlu: sol bilgiler, sag QR+barkod ─────
LABEL_4 = """^XA
^PW812^LL1218
^CI28
^FO0,0^GB812,1218,2^FS

^FX -- Kargo Firma --
^FO30,30^A0N,30,30^FDPTT Kargo^FS

^FX -- Ayirici --
^FO30,75^GB750,2,2^FS

^FX -- Dikey ayirici --
^FO420,75^GB2,500,2^FS

^FX -- Sol sutun: Alici Bilgileri --
^FO30,95^A0N,22,22^FDAlici:^FS
^FO30,127^A0N,26,26^FDAyse Ozturk^FS
^FO30,163^A0N,18,18^FDYeni Mah. Bahar Sok.^FS
^FO30,191^A0N,18,18^FDNo:34 Kat:2^FS
^FO30,219^A0N,18,18^FDMeram / Konya 42090^FS
^FO30,247^A0N,18,18^FDTel: 0538 456 7890^FS

^FX -- Satis Kanali --
^FO30,290^A0N,38,38^FDAmazon^FS

^FX -- Siparis --
^FO30,345^A0N,18,18^FDSiparis: AMZ-TR-445566^FS
^FO30,373^A0N,18,18^FDGonderi: 6612345678901^FS

^FX -- Ek bilgi --
^FO30,410^A0N,18,18^FDTarih: 03.03.2026^FS
^FO30,438^A0N,18,18^FDAgirlk: 3.1 kg^FS
^FO30,466^A0N,18,18^FDKoli: 2/3^FS
^FO30,494^A0N,18,18^FDUrun: Kitap^FS

^FX -- Sag sutun: QR --
^FO460,100^BQN,2,4
^FDQA,https://ptt.track/6612345678901^FS

^FX -- Sag sutun: Barkod (Code128) --
^FO445,370^BY2
^BCN,100,Y,N,N
^FD6612345678901^FS

^FX -- Ayirici yatay --
^FO30,575^GB750,2,2^FS

^FX -- Alt bolum: Teslimat notu --
^FO30,600^A0N,22,22^FDTeslimat Notu:^FS
^FO30,635^A0N,18,18^FDLutfen kapida teslim ediniz.^FS
^FO30,663^A0N,18,18^FDZil bozuk, telefon ile arayin.^FS

^XZ"""


# ── Label 5: Layout G ─ Barcode top, info middle, QR bottom ──────────
LABEL_5 = """^XA
^PW812^LL1218
^CI28
^FO0,0^GB812,1218,2^FS

^FX -- Kargo Firma --
^FO30,25^A0N,28,28^FDSurat Kargo^FS

^FX -- Ayirici --
^FO30,65^GB750,2,2^FS

^FX -- Barkod ust (Code 39) --
^FO100,100^BY2
^B3N,N,120,Y,N
^FD9901234567890^FS

^FX -- Ayirici --
^FO30,275^GB750,2,2^FS

^FX -- Alici Bilgileri --
^FO30,300^A0N,22,22^FDAlici:^FS
^FO30,332^A0N,26,26^FDAli Celik^FS
^FO30,370^A0N,20,20^FDZafer Mah. Vatan Cad. No:56^FS
^FO30,400^A0N,20,20^FDMelikgazi / Kayseri 38030^FS
^FO30,430^A0N,20,20^FDTel: 0542 333 4455^FS

^FX -- Ayirici --
^FO30,470^GB750,2,2^FS

^FX -- Satis Kanali --
^FO30,500^A0N,40,40^FDGittiGidiyor^FS

^FX -- Ayirici --
^FO30,555^GB750,2,2^FS

^FX -- Siparis ve Gonderi --
^FO30,580^A0N,20,20^FDSiparis: GG-998877^FS
^FO30,610^A0N,20,20^FDGonderi No: 9901234567890^FS

^FX -- Ek bilgiler --
^FO30,650^A0N,18,18^FDTarih: 02.03.2026^FS
^FO400,580^A0N,18,18^FDAgirlk: 0.5 kg^FS
^FO400,610^A0N,18,18^FDKoli: 1/1^FS
^FO400,650^A0N,18,18^FDUrun: Aksesuar^FS

^FX -- QR Kod (alt orta) --
^FO300,900^BQN,2,4
^FDQA,https://surat.track/9901234567890^FS

^XZ"""


# ── Label 6: Layout B ─ QR sol, bilgiler sagda, barcode altta ────────
LABEL_6 = """^XA
^PW812^LL1218
^CI28
^FO0,0^GB812,1218,2^FS

^FX -- Kargo Firma --
^FO30,25^A0N,30,30^FDHepsiJet^FS

^FX -- Ayirici --
^FO30,70^GB750,2,2^FS

^FX -- QR Kod (sol orta) --
^FO40,100^BQN,2,5
^FDQA,https://hepsijet.track/3345678901234^FS

^FX -- Bilgiler sagda --
^FO310,100^A0N,22,22^FDAlici:^FS
^FO310,132^A0N,26,26^FDZeynep Arslan^FS
^FO310,168^A0N,18,18^FDKurtulis Mah. Cicek Sok.^FS
^FO310,196^A0N,18,18^FDNo:23 Kat:4 D:8^FS
^FO310,224^A0N,18,18^FDCankaya / Ankara 06690^FS
^FO310,252^A0N,18,18^FDTel: 0533 111 2233^FS

^FX -- Satis Kanali (sag) --
^FO310,295^A0N,36,36^FDCiceksepeti^FS

^FX -- Ayirici --
^FO30,355^GB750,2,2^FS

^FX -- Siparis bilgileri --
^FO30,380^A0N,20,20^FDSiparis No: CS-2026-334455^FS
^FO30,410^A0N,20,20^FDGonderi No: 3345678901234^FS

^FX -- Ek bilgiler --
^FO30,450^A0N,18,18^FDTarih: 01.03.2026^FS
^FO400,380^A0N,18,18^FDAgirlk: 1.8 kg^FS
^FO400,410^A0N,18,18^FDKoli: 1/1^FS
^FO400,450^A0N,18,18^FDUrun: Hediye^FS

^FX -- Ayirici --
^FO30,490^GB750,2,2^FS

^FX -- Barkod altta (Code 128) --
^FO140,530^BY3
^BCN,110,Y,N,N
^FD3345678901234^FS

^XZ"""


# ── Label 7: Layout E ─ QR buyuk ortada, bilgiler ust ve alt ─────────
LABEL_7 = """^XA
^PW812^LL1218
^CI28
^FO0,0^GB812,1218,2^FS

^FX -- Kargo Firma --
^FO30,25^A0N,34,34^FDTrendyol Express^FS

^FX -- Ayirici --
^FO30,72^GB750,2,2^FS

^FX -- Alici Bilgileri (ust) --
^FO30,95^A0N,22,22^FDAlici:^FS
^FO30,125^A0N,28,28^FDHasan Sahin^FS
^FO30,163^A0N,20,20^FDYesilvadi Mah. Ozgur Sok. No:9^FS
^FO30,193^A0N,20,20^FDPendik / Istanbul 34893^FS
^FO30,223^A0N,20,20^FDTel: 0546 777 8899^FS

^FX -- Satis Kanali --
^FO500,95^A0N,40,40^FDTrendyol^FS

^FX -- Ayirici --
^FO30,270^GB750,2,2^FS

^FX -- QR Kod buyuk (ortada) --
^FO270,310^BQN,2,5
^FDQA,https://ty.track/1123456789012^FS

^FX -- Ayirici --
^FO30,580^GB750,2,2^FS

^FX -- Siparis Bilgileri --
^FO30,605^A0N,20,20^FDSiparis: TY-2026-667788^FS
^FO30,635^A0N,20,20^FDGonderi No: 1123456789012^FS
^FO400,605^A0N,18,18^FDTarih: 28.02.2026^FS
^FO400,635^A0N,18,18^FDAgirlk: 4.2 kg^FS

^FX -- Ayirici --
^FO30,670^GB750,2,2^FS

^FX -- Barkod (Code128, alt) --
^FO140,710^BY2
^BCN,100,Y,N,N
^FD1123456789012^FS

^XZ"""


# ── Label 8: Layout H ─ Compact ust, buyuk barkod ortada, kucuk QR ───
LABEL_8 = """^XA
^PW812^LL1218
^CI28
^FO0,0^GB812,1218,2^FS

^FX -- Kargo Firma --
^FO30,20^A0N,26,26^FDYurtici Kargo^FS
^FO500,20^A0N,20,20^FD05.03.2026^FS

^FX -- Ayirici --
^FO30,55^GB750,2,2^FS

^FX -- Compact bilgi --
^FO30,70^A0N,20,20^FDAlici: Burak Tekin^FS
^FO30,100^A0N,18,18^FDHurriyet Mah. Dag Cad. No:67^FS
^FO30,126^A0N,18,18^FDSelcuklu / Konya 42060^FS
^FO30,152^A0N,18,18^FDTel: 0537 444 5566^FS

^FX -- Satis Kanali --
^FO500,70^A0N,36,36^FDN11^FS

^FX -- Ayirici --
^FO30,190^GB750,2,2^FS

^FX -- Siparis/Gonderi --
^FO30,210^A0N,18,18^FDSiparis: N11-2026-ABCDEF^FS
^FO30,238^A0N,18,18^FDGonderi: 4456789012345^FS
^FO400,210^A0N,18,18^FDAgirlk: 0.3 kg^FS
^FO400,238^A0N,18,18^FDKoli: 1/1^FS

^FX -- Ayirici --
^FO30,275^GB750,2,2^FS

^FX -- Buyuk Barkod (Code128, ortada) --
^FO100,320^BY3
^BCN,150,Y,N,N
^FD4456789012345^FS

^FX -- Ayirici --
^FO30,530^GB750,2,2^FS

^FX -- Ek bilgi --
^FO30,555^A0N,18,18^FDUrun: Giyim^FS
^FO30,583^A0N,18,18^FDTeslimat: Kapida^FS

^FX -- QR kucuk (sag alt kose) --
^FO620,555^BQN,2,3
^FDQA,https://n11.track/4456789012345^FS

^XZ"""


LABELS = {
    "gen_label_A": LABEL_1,
    "gen_label_B": LABEL_6,
    "gen_label_C": LABEL_2,
    "gen_label_D": LABEL_3,
    "gen_label_E": LABEL_7,
    "gen_label_F": LABEL_4,
    "gen_label_G": LABEL_5,
    "gen_label_H": LABEL_8,
}


def main():
    from zpl_editor.core.zpl_renderer import render_zpl_to_png_bytes

    print(f"Generating {len(LABELS)} ZPL labels...")
    print("=" * 60)

    for name, zpl_code in LABELS.items():
        print(f"\n  {name}:")

        # Save ZPL
        zpl_path = os.path.join(OUT_ZPL, f"{name}.zpl")
        with open(zpl_path, "w", encoding="utf-8") as f:
            f.write(zpl_code)
        print(f"    ZPL saved: {zpl_path}")

        # Render to PNG
        png_bytes = render_zpl_to_png_bytes(zpl_code, dpi=203)
        if png_bytes is None:
            print(f"    ERROR: render returned None!")
            continue

        # Decode and save
        arr = np.frombuffer(png_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            print(f"    ERROR: cannot decode PNG!")
            continue

        h, w = img.shape[:2]
        png_path = os.path.join(OUT_PNG, f"{name}.png")
        cv2.imwrite(png_path, img)
        print(f"    PNG saved: {png_path}  ({w}x{h})")

    print(f"\n{'=' * 60}")
    print("Done! Now run test_pixel_loop.py to test analysis accuracy.")


if __name__ == "__main__":
    main()
