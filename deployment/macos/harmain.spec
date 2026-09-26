# PyInstaller spec for macOS.
# Build ON macOS with:  pyinstaller deployment/macos/harmain.spec
# (PyInstaller cannot cross-compile - you must build on the target OS.)

# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

block_cipher = None
project_root = Path(SPECPATH).parent.parent

a = Analysis(
    [str(project_root / 'main.py')],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        (str(project_root / 'assets'), 'assets'),
    ],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='HaramaIn',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name='HaramaIn',
)
app = BUNDLE(
    coll,
    name='HaramaIn.app',
    icon=str(project_root / 'assets' / 'icon.icns') if (project_root / 'assets' / 'icon.icns').exists() else None,
    bundle_identifier='com.haramainbysheraz.app',
    info_plist={
        'NSHighResolutionCapable': 'True',
        'CFBundleShortVersionString': '1.0.0',
    },
)
