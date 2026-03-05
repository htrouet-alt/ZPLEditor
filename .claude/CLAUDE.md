# ZPL Visual Editor

## Proje Tanımı

Python 3.10+ ve PyQt6 ile geliştirilmiş, ZPL (Zebra Programming Language) kodunu görsel olarak düzenleyebilen tam özellikli bir 2D etiket tasarım editörü. Sol panelde ZPL kod editörü, sağ panelde WYSIWYG görsel canvas bulunur. Bidirectional sync ile her görsel değişiklik anında ZPL koduna, her kod değişikliği anında görsele yansır.

## Teknoloji Stack

- **Dil:** Python 3.10+
- **GUI:** PyQt6 (QGraphicsScene/QGraphicsView)
- **OCR:** Tesseract (pytesseract), RapidOCR (ONNX Runtime), EasyOCR
- **Görüntü İşleme:** OpenCV (cv2), NumPy
- **Barkod:** python-barcode (1D), qrcode (QR), pyzbar (detection)
- **API:** Labelary API (api.labelary.com) — ZPL → PNG render
- **Sanal ortam:** `.venv/` dizininde
- #Metinleri resim yapma
- #Qr kodları resim yapma , bakrodları resim yapma
## Proje Yapısı

```
zpl_editor/
├── main.py, app.py                    # Giriş noktaları
├── core/
│   ├── zpl_parser.py                  # ZPL kodu → LabelModel (regex tabanlı parser)
│   ├── zpl_generator.py               # LabelModel → ZPL kodu
│   ├── zpl_commands.py                # ZPLElement, LabelSettings dataclass'ları
│   ├── label_model.py                 # Etiket veri modeli (settings + elements)
│   └── coordinate_system.py           # DPI/dot/mm/inch dönüşümleri
├── elements/
│   ├── base_element.py                # Abstract base class — tüm elementler
│   ├── text_element.py                # Metin (^FO + ^A + ^FD)
│   ├── barcode_element.py             # Barkod (^BC, ^B3, ^BY)
│   ├── qr_element.py                  # QR kod (^BQ)
│   ├── box_element.py                 # Kutu/dikdörtgen (^GB)
│   ├── line_element.py                # Çizgi (^GB, w/h ≤ thickness)
│   ├── circle_element.py              # Daire (^GC)
│   ├── diagonal_line.py               # Çapraz çizgi (^GD)
│   ├── image_element.py               # Bitmap grafik (^GFA)
│   └── field_element.py               # Bileşik alan elementi
├── ui/
│   ├── main_window.py                 # QMainWindow — splitter, menüler, toolbar
│   ├── code_editor.py                 # Sol panel — ZPL editörü (syntax highlighting)
│   ├── canvas_view.py                 # Sağ panel — QGraphicsView (zoom/pan/grid)
│   ├── canvas_scene.py                # QGraphicsScene — element yönetimi
│   ├── property_panel.py              # Seçili element özellikleri
│   ├── toolbar.py                     # Üst araç çubuğu
│   ├── statusbar.py                   # Alt durum çubuğu
│   ├── linter_panel.py                # Kod linting/doğrulama
│   ├── label_list_panel.py            # Etiket listesi
│   ├── label_size_dialog.py           # Etiket boyutu dialog'u
│   └── image_analysis_view.py         # OCR bölge tespiti önizleme
├── image_processing/
│   ├── image_analyzer.py              # Görüntü analizi — barkod/QR/metin/çizgi tespiti
│   └── zpl_from_image.py              # Tespit edilen bölgeler → ZPL kodu
├── graphics/
│   ├── resizable_item.py              # Resize handle'lı QGraphicsItem
│   ├── selection_handles.py           # 8 nokta resize handle sistemi
│   ├── grid_overlay.py                # Snap-to-grid ızgara
│   ├── ruler.py                       # Cetvel (üst/sol)
│   └── zoom_controller.py             # Zoom yönetimi
├── fonts/
│   ├── zebra_fonts.py                 # Zebra font tanımları (0-9, A-Z)
│   └── font_mapper.py                 # ZPL font ID → QFont eşleme
├── utils/
│   ├── undo_redo.py                   # QUndoStack tabanlı geri al/yinele
│   ├── clipboard.py                   # Kopyala/yapıştır
│   ├── export.py                      # PNG/PDF export
│   └── settings.py                    # Uygulama ayarları
└── resources/                         # İkonlar, fontlar, QSS temalar
```

## Temel Mimari Kurallar

### Bidirectional Sync
- Kod → Canvas: 500ms debounce ile parser çalışır, canvas güncellenir
- Canvas → Kod: Element değiştiğinde generator ZPL kodunu günceller
- `_syncing` flag'i ile sonsuz döngü önlenir

### ZPL Parsing Algoritması
1. `^XA` ... `^XZ` arasındaki kodu al
2. `^` karakterinden böl (her biri bir komut)
3. Komut kodu + virgülle ayrılmış parametreleri ayır
4. State machine: `^FO` element başlatır, `^FS` bitirir
5. `^A`, `^FD`, `^GB` vb. mevcut elemente özellik ekler
6. `^CF`, `^CI`, `^PW`, `^LL` global ayarları günceller

### Koordinat Sistemi
- Sol üst köşe (0,0), sağa ve aşağıya artar
- DPI dönüşümleri: 203 DPI → 1mm=8dot, 1inch=203dot
- ZPL font boyutları dot cinsinden (piksel değil)

### Element Sistemi
- Tüm elementler `BaseElement(QGraphicsItem)` sınıfından türer
- 8 resize handle (4 köşe + 4 kenar ortası, 8x8px mavi kare)
- Seçim: tek tık, Ctrl+tık (çoklu), rubber band, Ctrl+A
- Sürükleme: snap-to-grid, hizalama çizgileri, pozisyon tooltip

## ZPL Komut Öncelikleri

### Öncelik 1 — Temel (Zorunlu)
`^XA/^XZ`, `^FO`, `^FD/^FS`, `^A`, `^CF`, `^GB`, `^FT`, `^CI`

### Öncelik 2 — Barkod ve Grafik
`^BC` (Code128), `^B3` (Code39), `^BY`, `^BQ` (QR), `^GC`, `^GD`

### Öncelik 3 — Gelişmiş
`^FB` (çok satırlı), `^FW`, `^GFA` (bitmap), `^PW`, `^LL`, `^LH`, `^FX`

## Veri Yapıları

### ZPLElement (dataclass)
- `element_type`: "text", "barcode", "qrcode", "box", "line", "circle" vb.
- `x, y`: Pozisyon (dot)
- `use_ft`: ^FT kullanımı (baseline konum)
- `properties`: dict — elemente özgü özellikler

### LabelSettings (dataclass)
- `width=812, height=1218`: 4"x6" @ 203 DPI
- `dpi=203`: Yazıcı DPI (203/300/600)
- `default_font="0"`, `default_font_height=30`
- Barkod varsayılanları: `module_width=2, ratio=3.0, height=10`

## Test ve Karşılaştırma

```
test_pixel_loop.py    # Etiket benzerlik metrikleri (strict/relaxed)
test_compare.py       # Band bazlı detaylı karşılaştırma
create_diff.py        # Piksel farkı görselleştirme
Examples/
├── input/            # Kaynak etiket PNG'leri (label_1..4.png)
├── output/
│   ├── ZPLCode/      # Üretilen ZPL kodları
│   ├── ZplImage/     # Labelary render çıktıları
│   └── Diff/         # Fark analizi görselleri
```

- **Benzerlik hedefi:** ≥ %95 piksel eşleşme
- **Relaxed mod:** 1px toleranslı (dilation ile)
- **Band analizi:** 50px yatay bantlar, missed/false-positive oranları

## Kritik Notlar

1. **^FO vs ^FT:** ^FO = sol üst köşe, ^FT = baseline (sol alt). İkisi de desteklenmeli
2. **^GB ikili kullanım:** width/height ≤ thickness → çizgi; aksi → dikdörtgen
3. **ZPL whitespace-insensitive:** Boşluk ve satır sonu önemsiz
4. **Boş parametre:** `^A0N,30,` → width varsayılan değer alır
5. **Global komutlar:** ^CF, ^BY, ^CI state olarak tutulmalı, sonraki elementlere uygulanmalı
6. **Font height ×0.75:** Labelary, ZPL font height'ın ~%75'ini ink olarak render eder
7. **Resize handle'lar:** Sabit ekran boyutunda olmalı (zoom'dan bağımsız)
8. **Koordinat mapping:** Mouse event'lerinde `mapToScene()`/`mapFromScene()` kullanılmalı

## Çalıştırma

```bash
# Virtual environment aktifleştir
source .venv/Scripts/activate   # Windows bash
# veya
.venv\Scripts\activate          # Windows cmd

# Uygulamayı çalıştır
python main.py

# Testleri çalıştır
python test_pixel_loop.py
python test_compare.py
```

## Geliştirme Fazları

1. **Faz 1 — Temel Altyapı:** Ana pencere, editör, canvas, parser, generator
2. **Faz 2 — Grafik Elementler:** BaseElement, metin, dikdörtgen/çizgi, bidirectional sync
3. **Faz 3 — Gelişmiş Elementler:** Daire, çapraz çizgi, barkod, QR, özellik paneli
4. **Faz 4 — UX:** Undo/redo, snap-to-grid, sağ tık menüsü, tema sistemi
5. **Faz 5 — İleri:** Labelary API, export, ^FB, ^GFA, performans
