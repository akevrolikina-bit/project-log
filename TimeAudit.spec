# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build specification for TimeAudit.

Produces a single-file Windows executable (dist/TimeAudit.exe) that bundles:
  - the Python backend (FastAPI + uvicorn),
  - the statically-built frontend (frontend/out),
  - the reference permitted-tasks workbook,
  - the backend/.env file (embedded API keys, per project decision).

Run from the project root:  pyinstaller TimeAudit.spec
"""

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# --- Hidden imports -------------------------------------------------------
# uvicorn loads its protocol/loop/lifespan implementations dynamically, so
# PyInstaller cannot detect them by static analysis. Our own "app" package is
# imported lazily inside run.py, so collect it explicitly too.
hiddenimports = []
hiddenimports += collect_submodules("uvicorn")
hiddenimports += collect_submodules("app")

# --- Bundled data files ---------------------------------------------------
# The destination paths mirror what backend/app/config.py expects to find
# under the bundle directory (sys._MEIPASS) at runtime.
datas = [
    ("frontend/out", "frontend/out"),
    ("backend/.env", "backend"),
    ("data/input/Issues CHANGE (3).xlsx", "data/input"),
    ("backend/config/employee_countries.json", "config"),
]

# google-api-python-client ships JSON discovery/data files it loads at runtime.
try:
    datas += collect_data_files("googleapiclient")
except Exception:
    pass


a = Analysis(
    ["backend/run.py"],
    pathex=["backend"],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="TimeAudit",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
