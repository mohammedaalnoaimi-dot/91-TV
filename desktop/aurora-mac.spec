# PyInstaller spec for macOS: builds dist/91 TV.app. Set MPV_DYLIB to the libmpv .dylib to bundle (its dependencies are collected automatically).
import os
from PyInstaller.utils.hooks import collect_submodules, copy_metadata

lib = os.environ.get("MPV_DYLIB", "")
binaries = [(lib, ".")] if lib and os.path.exists(lib) else []
datas = [("assets", "assets")] + copy_metadata("keyring") + copy_metadata("python-mpv")
hidden = collect_submodules("keyring.backends") + ["mpv"]
ver = os.environ.get("APP_VERSION", "1.0")

a = Analysis(["main.py"], pathex=["."], binaries=binaries, datas=datas, hiddenimports=hidden, hookspath=[], runtime_hooks=[],
             excludes=["tkinter", "unittest", "PySide6.QtWebEngineCore", "PySide6.QtQml", "PySide6.QtQuick"], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="91TV", console=False, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="91TV")
app = BUNDLE(coll, name="91 TV.app", icon="assets/aurora.icns", bundle_identifier="com.ninetyone.tv",
             info_plist={"CFBundleName": "91 TV", "CFBundleDisplayName": "91 TV", "CFBundleShortVersionString": ver,
                         "NSHighResolutionCapable": True, "LSMinimumSystemVersion": "11.0",
                         "NSLocalNetworkUsageDescription": "91 TV connects to your IPTV provider."})
