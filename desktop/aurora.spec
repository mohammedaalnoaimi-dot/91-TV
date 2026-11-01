# PyInstaller spec - builds dist/91TV/91TV.exe (onedir). Run via build.ps1.
import os
from PyInstaller.utils.hooks import collect_submodules, copy_metadata

mpv_dll = os.path.join("build", "mpv", "libmpv-2.dll")
binaries = [(mpv_dll, ".")] if os.path.exists(mpv_dll) else []
datas = [("assets", "assets")] + copy_metadata("keyring") + copy_metadata("python-mpv")
hidden = collect_submodules("keyring.backends") + ["mpv", "win32ctypes.pywin32.pywintypes", "win32ctypes.pywin32.win32cred"]

a = Analysis(["main.py"], pathex=["."], binaries=binaries, datas=datas, hiddenimports=hidden, hookspath=[], runtime_hooks=[],
             excludes=["tkinter", "unittest", "PySide6.QtWebEngineCore", "PySide6.QtQml", "PySide6.QtQuick"], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="91TV", console=False, icon="assets/aurora.ico", upx=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="91TV")
