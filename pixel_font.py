# pixel_font.py
"""
A tiny built-in 5x7 bitmap font for authentic arcade-style titles.

Why a bitmap font instead of scaling a TTF?
    Scaling an anti-aliased system font (the old ``pixel_text`` approach) gives
    blurry, smeared letters. Drawing every glyph from a hand-made bitmap gives
    crisp, square pixels at any integer scale, needs no font files (so it works
    the same on Windows, macOS, Linux and inside a PyInstaller build) and costs
    nothing at runtime thanks to a small render cache.

Usage:
    from pixel_font import render_pixel_text
    surf = render_pixel_text("GAME OVER", scale=4, color=(0, 240, 255), glow=True)
    screen.blit(surf, surf.get_rect(center=(400, 300)))

Characters that are not in the table are upper-cased, stripped of accents
(``è`` -> ``E``) and, if still unknown, drawn as a small box.
"""
from __future__ import annotations

import unicodedata
from collections import OrderedDict

import pygame

GLYPH_HEIGHT = 7
LETTER_SPACING = 1  # empty columns between two glyphs (in font pixels)

# Each glyph is a tuple of rows; "#" is an "on" pixel. Glyphs may have
# different widths (narrow punctuation looks much better that way).
_GLYPHS: dict[str, tuple[str, ...]] = {
    "A": (".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "B": ("####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."),
    "C": (".###.", "#...#", "#....", "#....", "#....", "#...#", ".###."),
    "D": ("####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."),
    "E": ("#####", "#....", "#....", "####.", "#....", "#....", "#####"),
    "F": ("#####", "#....", "#....", "####.", "#....", "#....", "#...."),
    "G": (".###.", "#...#", "#....", "#.###", "#...#", "#...#", ".####"),
    "H": ("#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "I": (".###.", "..#..", "..#..", "..#..", "..#..", "..#..", ".###."),
    "J": ("..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."),
    "K": ("#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"),
    "L": ("#....", "#....", "#....", "#....", "#....", "#....", "#####"),
    "M": ("#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"),
    "N": ("#...#", "#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#"),
    "O": (".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "P": ("####.", "#...#", "#...#", "####.", "#....", "#....", "#...."),
    "Q": (".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"),
    "R": ("####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"),
    "S": (".####", "#....", "#....", ".###.", "....#", "....#", "####."),
    "T": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."),
    "U": ("#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "V": ("#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."),
    "W": ("#...#", "#...#", "#...#", "#.#.#", "#.#.#", "#.#.#", ".#.#."),
    "X": ("#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"),
    "Y": ("#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."),
    "Z": ("#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"),
    "0": (".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."),
    "1": ("..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."),
    "2": (".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"),
    "3": ("#####", "...#.", "..#..", "...#.", "....#", "#...#", ".###."),
    "4": ("...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."),
    "5": ("#####", "#....", "####.", "....#", "....#", "#...#", ".###."),
    "6": ("..##.", ".#...", "#....", "####.", "#...#", "#...#", ".###."),
    "7": ("#####", "....#", "...#.", "..#..", ".#...", ".#...", ".#..."),
    "8": (".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."),
    "9": (".###.", "#...#", "#...#", ".####", "....#", "...#.", ".##.."),
    " ": ("...", "...", "...", "...", "...", "...", "..."),
    ".": ("..", "..", "..", "..", "..", "##", "##"),
    ",": ("..", "..", "..", "..", "##", ".#", "#."),
    ":": ("..", "##", "##", "..", "##", "##", ".."),
    ";": ("..", "##", "##", "..", "##", ".#", "#."),
    "!": ("#", "#", "#", "#", "#", ".", "#"),
    "?": (".###.", "#...#", "....#", "...#.", "..#..", ".....", "..#.."),
    "-": ("....", "....", "....", "####", "....", "....", "...."),
    "+": (".....", "..#..", "..#..", "#####", "..#..", "..#..", "....."),
    "=": (".....", ".....", "#####", ".....", "#####", ".....", "....."),
    "/": ("....#", "....#", "...#.", "..#..", ".#...", "#....", "#...."),
    "'": ("#", "#", ".", ".", ".", ".", "."),
    '"': ("#.#", "#.#", "...", "...", "...", "...", "..."),
    "(": (".#", "#.", "#.", "#.", "#.", "#.", ".#"),
    ")": ("#.", ".#", ".#", ".#", ".#", ".#", "#."),
    "[": ("##", "#.", "#.", "#.", "#.", "#.", "##"),
    "]": ("##", ".#", ".#", ".#", ".#", ".#", "##"),
    "<": ("...#", "..#.", ".#..", "#...", ".#..", "..#.", "...#"),
    ">": ("#...", ".#..", "..#.", "...#", "..#.", ".#..", "#..."),
    "_": (".....", ".....", ".....", ".....", ".....", ".....", "#####"),
    "%": ("##..#", "##..#", "...#.", "..#..", ".#...", "#..##", "#..##"),
    "#": (".#.#.", ".#.#.", "#####", ".#.#.", "#####", ".#.#.", ".#.#."),
    "*": (".....", "#.#.#", ".###.", "#####", ".###.", "#.#.#", "....."),
    "|": ("#", "#", "#", "#", "#", "#", "#"),
    "·": ("..", "..", "..", "##", "##", "..", ".."),
    "♥": (".....", ".#.#.", "#####", "#####", ".###.", "..#..", "....."),
    "★": ("..#..", "..#..", "#####", ".###.", ".###.", "##.##", "#...#"),
    "→": (".....", "...#.", "....#", "#####", "....#", "...#.", "....."),
    "←": (".....", ".#...", "#....", "#####", "#....", ".#...", "....."),
    "↑": ("..#..", ".###.", "#.#.#", "..#..", "..#..", "..#..", "..#.."),
    "↓": ("..#..", "..#..", "..#..", "..#..", "#.#.#", ".###.", "..#.."),
}
_FALLBACK: tuple[str, ...] = ("###", "#.#", "#.#", "#.#", "#.#", "#.#", "###")

# Cache of rendered surfaces: (text, scale, color, shadow, glow) -> Surface
_RENDER_CACHE: OrderedDict[tuple, pygame.Surface] = OrderedDict()
_RENDER_CACHE_MAX = 256


def _normalize_char(ch: str) -> str:
    """Map a character to a key of the glyph table (upper-case, no accents)."""
    if ch in _GLYPHS:
        return ch
    up = ch.upper()
    if up in _GLYPHS:
        return up
    # Strip accents: "È" -> "E" + combining grave accent -> "E"
    decomposed = unicodedata.normalize("NFKD", up)
    base = "".join(c for c in decomposed if not unicodedata.combining(c))
    if base and base[0] in _GLYPHS:
        return base[0]
    return "\0"


def glyph_for(ch: str) -> tuple[str, ...]:
    """Return the bitmap rows used to draw ``ch`` (a fallback box if unknown)."""
    key = _normalize_char(ch)
    return _GLYPHS.get(key, _FALLBACK)


def measure(text: str, scale: int = 1) -> tuple[int, int]:
    """Return the pixel size ``(width, height)`` that ``text`` would occupy."""
    if not text:
        return (0, GLYPH_HEIGHT * scale)
    width = sum(len(glyph_for(ch)[0]) for ch in text)
    width += LETTER_SPACING * (len(text) - 1)
    return (width * scale, GLYPH_HEIGHT * scale)


def _draw_bitmap(text: str, scale: int, color: tuple[int, int, int]) -> pygame.Surface:
    """Draw the raw glyphs (no effects) onto a transparent surface."""
    w, h = measure(text, scale)
    surf = pygame.Surface((max(1, w), max(1, h)), pygame.SRCALPHA)
    x = 0
    for ch in text:
        rows = glyph_for(ch)
        for ry, row in enumerate(rows):
            for rx, px in enumerate(row):
                if px == "#":
                    surf.fill(color, (x + rx * scale, ry * scale, scale, scale))
        x += (len(rows[0]) + LETTER_SPACING) * scale
    return surf


def render_pixel_text(
    text: str,
    scale: int = 3,
    color: tuple[int, int, int] = (255, 255, 255),
    shadow: tuple[int, int, int] | None = None,
    glow: bool = False,
) -> pygame.Surface:
    """
    Render ``text`` with the bitmap font.

    Args:
        text: The string to draw (single line).
        scale: Integer size multiplier (1 font pixel = ``scale`` screen pixels).
        color: RGB color of the letters.
        shadow: Optional RGB color of a 1-font-pixel drop shadow.
        glow: If True, adds a soft neon halo around the letters.

    Returns:
        A per-pixel-alpha Surface. Results are cached, so calling this every
        frame with the same arguments is cheap.
    """
    scale = max(1, int(scale))
    key = (text, scale, tuple(color), tuple(shadow) if shadow else None, glow)
    cached = _RENDER_CACHE.get(key)
    if cached is not None:
        _RENDER_CACHE.move_to_end(key)
        return cached

    base = _draw_bitmap(text, scale, color)
    pad = scale * 3 if glow else (scale if shadow else 0)
    out = pygame.Surface(
        (base.get_width() + pad * 2, base.get_height() + pad * 2), pygame.SRCALPHA
    )

    if glow:
        # Cheap blur: shrink then smooth-scale back up. Done once, then cached.
        halo = pygame.Surface(out.get_size(), pygame.SRCALPHA)
        halo.blit(base, (pad, pad))
        small_size = (max(1, out.get_width() // 4), max(1, out.get_height() // 4))
        halo = pygame.transform.smoothscale(halo, small_size)
        halo = pygame.transform.smoothscale(halo, out.get_size())
        halo.fill((255, 255, 255, 170), special_flags=pygame.BLEND_RGBA_MULT)
        out.blit(halo, (0, 0))

    if shadow:
        out.blit(_draw_bitmap(text, scale, shadow), (pad + scale, pad + scale))
    out.blit(base, (pad, pad))

    _RENDER_CACHE[key] = out
    if len(_RENDER_CACHE) > _RENDER_CACHE_MAX:
        _RENDER_CACHE.popitem(last=False)
    return out


def blit_pixel_text(
    target: pygame.Surface,
    text: str,
    pos: tuple[int, int],
    scale: int = 3,
    color: tuple[int, int, int] = (255, 255, 255),
    anchor: str = "topleft",
    shadow: tuple[int, int, int] | None = None,
    glow: bool = False,
) -> pygame.Rect:
    """
    Render and blit pixel text in one call.

    Args:
        target: Surface to draw on.
        text: String to draw.
        pos: Anchor position.
        scale, color, shadow, glow: See :func:`render_pixel_text`.
        anchor: Any ``pygame.Rect`` attribute name, e.g. ``"center"``,
            ``"midtop"``, ``"topright"``.

    Returns:
        The Rect where the text was drawn.
    """
    surf = render_pixel_text(text, scale, color, shadow, glow)
    rect = surf.get_rect(**{anchor: pos})
    target.blit(surf, rect)
    return rect


def clear_cache() -> None:
    """Drop every cached rendering (e.g. to free memory)."""
    _RENDER_CACHE.clear()
