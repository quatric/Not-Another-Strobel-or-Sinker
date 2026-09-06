# -*- mode: python ; coding: utf-8 -*-
import sys

exe_suffix = ".exe" if sys.platform.startswith("win") else ""
vendor_names = ["ffmpeg", "ffprobe", "rclone"]
binaries = [(f"vendor/{n}{exe_suffix}", "vendor") for n in vendor_names]

if sys.platform == "darwin":
    icon = "icon.icns"
elif sys.platform.startswith("win"):
    icon = "icon.ico"
else:
    icon = None

a = Analysis(
    ['gui.py'],
    pathex=[],
    binaries=binaries,
    datas=[('icon.png', '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='nass-gui',
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
    icon=[icon] if icon else None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='nass-gui',
)
# BUNDLE only produces a .app; PyInstaller silently skips it on non-macOS.
app = BUNDLE(
    coll,
    name='Not Another Strobel or Sinker.app',
    icon='icon.icns',
    bundle_identifier=None,
    version='1.0',
    # Without this, macOS restores this app's window to whatever frame it
    # last closed at (keyed to the bundle), which can be narrower than the
    # content needs and make widgets overlap.
    info_plist={'NSQuitAlwaysKeepsWindows': False},
)
