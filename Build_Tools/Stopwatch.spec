# -*- coding: utf-8 -*-
import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

block_cipher = None

# ========================================================
# 🔧 CONFIGURATION SECTION
# ========================================================
APP_NAME = 'Stopwatch'
MAIN_SCRIPT = 'Stopwatch.pyw'  # e.g., 'main.py'
ICON_FILE = 'logo.ico'      # e.g., 'logo.ico' or None

# List of hidden imports (modules that PyInstaller cannot detect)
HIDDEN_IMPORTS = [
    'keyboard',
    'pyautogui',
    'pygetwindow',
    'pygame',
    'pyperclip',
    'version'
]

# List of extra data files to include INSIDE the exe (src, dst)
# Note: For external config files, use post_build.py instead.
ADDED_FILES = [
    # ('../README.md', '.'),
]
# ========================================================

spec_path = os.path.abspath(sys.argv[0])
spec_dir = os.path.dirname(spec_path)
project_root = os.path.abspath(os.path.join(spec_dir, '..'))

# Resolve paths
script_path = os.path.join(project_root, MAIN_SCRIPT)
icon_path = os.path.join(project_root, ICON_FILE) if ICON_FILE else None

# Collect resources for specific libraries if needed
# Example: tmp_ret = collect_all('some_lib')
# datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

a = Analysis(
    [script_path],
    pathex=[project_root],
    binaries=[],
    datas=ADDED_FILES,
    hiddenimports=HIDDEN_IMPORTS,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _validate_binary_origins(binaries) -> None:
    """Stop a build if PyInstaller collects a native binary from an untrusted root."""
    allowed_roots = tuple(
        Path(path).resolve()
        for path in (
            project_root,
            sys.prefix,
            sys.base_prefix,
            os.environ.get("SystemRoot", r"C:\\Windows"),
        )
    )
    unexpected = []
    for binary in binaries:
        source = binary[1]
        source_path = Path(source).resolve()
        if not any(_is_within(source_path, root) for root in allowed_roots):
            unexpected.append(str(source_path))
    if unexpected:
        details = "\n".join(f"  - {path}" for path in unexpected)
        raise SystemExit(
            "Refusing PyInstaller build: Analysis.binaries contains foreign origins:\n"
            f"{details}"
        )


def _pin_qt_msvc_runtime() -> None:
    """Use PySide6's complete MSVC runtime at the bundle root.

    Python can contribute an older VCRUNTIME140*.dll to the root of a frozen
    bundle. Qt requires its matching PySide6 runtime instead, so replace every
    root-level MSVC entry with the version shipped by the selected binding.
    """
    binding_root = Path(sys.prefix, "Lib", "site-packages", "PySide6")
    runtime_files = sorted(
        path
        for path in binding_root.glob("*.dll")
        if path.name.lower().startswith(("vcruntime", "msvcp"))
    )
    if not runtime_files:
        raise SystemExit(f"PySide6 MSVC runtime is missing from {binding_root}")

    def is_root_msvc(entry) -> bool:
        destination = Path(entry[0])
        return (
            str(destination.parent) == "."
            and destination.name.lower().startswith(("vcruntime", "msvcp"))
        )

    a.binaries[:] = [entry for entry in a.binaries if not is_root_msvc(entry)]
    for runtime in runtime_files:
        a.binaries.append((runtime.name, str(runtime), "BINARY"))


_pin_qt_msvc_runtime()
_validate_binary_origins(a.binaries)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Set to True if you want a terminal window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=APP_NAME,
)
