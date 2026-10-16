# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH)
datas = collect_data_files("sia_app", includes=["ui/*.json"])
# O banco é criado no primeiro acesso. Dados reais não são incorporados ao EXE.
datas += collect_data_files("customtkinter")

hiddenimports = collect_submodules("customtkinter") + [
    "sia_app.ui.dashboard_tab",
    "sia_app.ui.file_upload_tab",
    "sia_app.ui.filters_tab",
    "sia_app.ui.reports_tab",
    "sia_app.ui.estabelecimentos_tab",
    "sia_app.ui.prd_editor_tab",
    "sia_app.ui.database_tab",
    "sia_app.ui.config_tab",
    "matplotlib.backends.backend_tkagg",
    "PIL._tkinter_finder",
]

a = Analysis(
    [str(ROOT / "run.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "IPython", "jupyter", "notebook"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="RelatorioSIA",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="RelatorioSIA",
)
