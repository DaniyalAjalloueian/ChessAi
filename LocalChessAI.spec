# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build configuration for Local Chess AI.

Build with:
    pyinstaller --noconfirm --clean LocalChessAI.spec
"""
from pathlib import Path

block_cipher = None

PROJECT_ROOT = Path(SPECPATH).resolve()

datas = []
assets = PROJECT_ROOT / "assets"
if assets.is_dir():
    datas.append((str(assets), "assets"))

hiddenimports = [
    "chess",
    "chess.engine",
    "chess.pgn",
    "chess.polyglot",
    "pyqtgraph",
    "numpy",
]

a = Analysis(
    ["main.py"],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "PyQt5", "PyQt6", "PySide2"],
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
    name="LocalChessAI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="LocalChessAI",
)