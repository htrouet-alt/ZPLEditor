# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for ZPL Visual Editor."""

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Paths
VENV_SITE = os.path.join('.venv', 'Lib', 'site-packages')

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
    'PIL',
    'PIL.Image',
]

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=pyzbar_datas,
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
