# -*- mode: python ; coding: utf-8 -*-
# PyInstaller recipe for a single-file executable.
#
#   pip install pyinstaller
#   pyinstaller packaging/RetroArcadeCollection.spec
#
# Output: dist/RetroArcadeCollection(.exe)
#
# Why "hiddenimports"? The launcher imports every game lazily with
# importlib.import_module(), so PyInstaller cannot discover them by itself.
from pathlib import Path

ROOT = Path(SPECPATH).parent  # noqa: F821 - SPECPATH is injected by PyInstaller
GAMES = [
    "tris", "snake", "tetris", "pong", "breakout",
    "space_invaders", "maze_runner", "memory_game", "puzzle15",
]
ICON = ROOT / "assets" / "icon.ico"

a = Analysis(  # noqa: F821
    [str(ROOT / "retro_arcade_interface.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[],
    hiddenimports=GAMES,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "unittest", "pytest", "numpy"],
    noarchive=False,
)
pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="RetroArcadeCollection",
    console=False,          # no black console window behind the game
    upx=False,              # UPX-packed exes are often flagged by antivirus software
    icon=str(ICON) if ICON.exists() else None,
)
