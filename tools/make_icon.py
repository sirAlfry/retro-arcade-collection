# make_icon.py
"""
Generate the application icon files from the same pixel art used at runtime.

    python tools/make_icon.py

Creates:
    assets/icon.png  - 256x256 PNG (README, Linux/macOS)
    assets/icon.ico  - multi-size Windows icon for the PyInstaller .exe
                       (needs Pillow: ``pip install pillow``; skipped otherwise)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pygame  # noqa: E402

from game_shared import make_icon  # noqa: E402


def main() -> None:
    assets = ROOT / "assets"
    assets.mkdir(exist_ok=True)
    big = pygame.transform.scale(make_icon(), (256, 256))  # nearest-neighbour: crisp pixels
    png = assets / "icon.png"
    pygame.image.save(big, str(png))
    print("Creato", png.relative_to(ROOT))
    try:
        from PIL import Image
    except ImportError:
        print("Pillow non installato: salto icon.ico (pip install pillow)")
        return
    ico = assets / "icon.ico"
    Image.open(png).save(ico, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64),
                                     (128, 128), (256, 256)])
    print("Creato", ico.relative_to(ROOT))


if __name__ == "__main__":
    main()
