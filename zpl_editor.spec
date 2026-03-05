# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for ZPL Visual Editor."""

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Paths
VENV_SITE = os.path.join('.venv', 'Lib', 'site-packages')

# Collect data files for key packages
rapidocr_datas = collect_data_files('rapidocr_onnxruntime', include_py_files=False)
onnxruntime_datas = collect_data_files('onnxruntime', include_py_files=False)
easyocr_datas = collect_data_files('easyocr', include_py_files=False)

# pyzbar DLLs
pyzbar_dir = os.path.join(VENV_SITE, 'pyzbar')
pyzbar_datas = [
    (os.path.join(pyzbar_dir, 'libiconv.dll'), 'pyzbar'),
    (os.path.join(pyzbar_dir, 'libzbar-64.dll'), 'pyzbar'),
]

# Hidden imports for packages that PyInstaller can't detect
hidden_imports = [
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    'PyQt6.QtSvg',
    'cv2',
    'numpy',
    'pytesseract',
    'pyzbar',
    'pyzbar.pyzbar',
    'qrcode',
    'qrcode.image.pure',
    'barcode',
    'barcode.codex',
    'barcode.ean',
    'barcode.code128',
    'barcode.code39',
    'requests',
    'rapidocr_onnxruntime',
    'onnxruntime',
    'easyocr',
    'easyocr.easyocr',
    'PIL',
    'PIL.Image',
]
hidden_imports += collect_submodules('rapidocr_onnxruntime')
hidden_imports += collect_submodules('onnxruntime')

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=rapidocr_datas + onnxruntime_datas + easyocr_datas + pyzbar_datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'scipy',
        'pandas',
        'IPython',
        'jupyter',
        'notebook',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ZPL_Editor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # windowed mode (no console)
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ZPL_Editor',
)
