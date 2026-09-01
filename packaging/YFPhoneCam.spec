# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

root = Path.cwd()
web_data = [
    (str(root / "yfphonecam" / "web"), "yfphonecam/web"),
    (str(root / "LICENSE"), "."),
    (str(root / "THIRD_PARTY_NOTICES.md"), "."),
    (str(root / "licenses"), "licenses"),
    (str(root / "vendor" / "UnityCapture" / "LICENSE.Filter.txt"), "licenses/UnityCapture"),
    (
        str(root / "vendor" / "UnityCapture" / "LICENSE.SharedProtocol.txt"),
        "licenses/UnityCapture",
    ),
]

a = Analysis(
    [str(root / "packaging" / "launcher.py")],
    pathex=[str(root)],
    binaries=[],
    datas=web_data,
    hiddenimports=["PySide6.QtNetwork"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "pytest", "mypy", "ruff"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="YFPhoneCam",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch="x86_64",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="YFPhoneCam",
)
