# -*- mode: python ; coding: utf-8 -*-
import os
import sys
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

# PyInstaller also searches PATH when resolving native dependencies. Build hosts
# can add unrelated tool directories there (for example Poppler or libheif), and
# an incompatible DLL with a familiar name can then silently enter the package.
# Only accept binaries supplied by this project, its Python environment, the
# base Python installation, or Windows itself.
trusted_binary_roots = tuple(
    path.resolve()
    for path in (
        root,
        Path(sys.prefix),
        Path(sys.base_prefix),
        Path(os.environ["SystemRoot"]),
    )
)


def is_trusted_binary(entry):
    source = Path(entry[1]).resolve()
    trusted = any(source == base or base in source.parents for base in trusted_binary_roots)
    if not trusted:
        print(f"Excluding untrusted PATH binary: {entry[0]} <- {source}")
    return trusted


a.binaries = [entry for entry in a.binaries if is_trusted_binary(entry)]
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
