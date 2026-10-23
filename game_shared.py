# game_shared.py
"""
Shared toolkit used by the launcher and by every game.

What lives here (in reading order):
    * Palette and screen constants
    * Window management: scalable window, F11 fullscreen, F12 screenshots,
      toast notifications, optional CRT filter (``present``)
    * Font helpers: ``safe_font`` with an LRU cache, text drawing helpers
    * Menus: pause menu, end-of-game screen, pre-game option picker
    * Small engine helpers: ``GameClock``, ``Stopwatch``, ``Particles``,
      ``FloatingTexts``, ``ScreenShake``

Every game follows the same contract::

    def main(load_scores=None, save_scores=None) -> str:   # "menu" | "quit"

Games never call ``pygame.quit()`` themselves: they return ``"quit"`` and the
launcher shuts everything down cleanly.
"""
from __future__ import annotations

import math
import random
import time
from collections import OrderedDict
from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path

import pygame

import sfx
from pixel_font import blit_pixel_text, render_pixel_text

# ============================================================================
# Palette & screen constants
# ============================================================================

Color = tuple[int, int, int]

W: int = 800
H: int = 600
FPS: int = 60

BG: Color = (20, 20, 40)          # dark "space" background used by every game
BG_DARK: Color = (10, 8, 24)
PANEL_BG: Color = (14, 12, 32)
WHITE: Color = (255, 255, 255)
BLACK: Color = (0, 0, 0)
GRAY_LIGHT: Color = (220, 220, 220)
GRAY_MEDIUM: Color = (180, 180, 180)
GRAY_DARK: Color = (100, 100, 100)
TEXT: Color = (220, 220, 255)
TEXT_DIM: Color = (140, 140, 185)

# Neon palette (matches the README banner: cyan + magenta synthwave)
NEON_CYAN: Color = (0, 240, 255)
NEON_MAGENTA: Color = (255, 60, 200)
NEON_PURPLE: Color = (150, 70, 255)
NEON_GREEN: Color = (60, 255, 120)
NEON_YELLOW: Color = (255, 230, 60)
NEON_ORANGE: Color = (255, 150, 40)
NEON_RED: Color = (255, 70, 90)
NEON_BLUE: Color = (60, 130, 255)
NEON_PINK: Color = NEON_MAGENTA   # backwards-compatible alias

SCORE_COLOR: Color = NEON_CYAN
HUD_TEXT_COLOR: Color = NEON_GREEN
WARNING_COLOR: Color = NEON_MAGENTA

MAX_DT: float = 0.05  # seconds; protects physics from huge frame spikes

# ============================================================================
# Settings (sound / CRT filter), persisted through scores.ScoreStore
# ============================================================================

_settings: dict[str, bool] = {"sound": True, "crt": True}
_settings_loaded: bool = False


def _store():
    from scores import ScoreStore  # local import keeps module import cheap
    return ScoreStore()


def load_settings() -> None:
    """Read persisted settings once and apply them (audio on/off, CRT)."""
    global _settings_loaded
    if _settings_loaded:
        return
    _settings_loaded = True
    try:
        store = _store()
        _settings["sound"] = bool(store.get_setting("sound", True))
        _settings["crt"] = bool(store.get_setting("crt", True))
    except Exception:
        pass
    sfx.set_enabled(_settings["sound"])


def _persist(key: str) -> None:
    try:
        _store().set_setting(key, _settings[key])
    except Exception:
        pass


def sound_enabled() -> bool:
    return _settings["sound"]


def toggle_sound() -> bool:
    """Switch audio on/off, persist the choice and return the new state."""
    _settings["sound"] = not _settings["sound"]
    sfx.set_enabled(_settings["sound"])
    _persist("sound")
    if _settings["sound"]:
        sfx.play("select")
    notify("AUDIO ON" if _settings["sound"] else "AUDIO OFF")
    return _settings["sound"]


def crt_enabled() -> bool:
    return _settings["crt"]


def toggle_crt() -> bool:
    """Switch the CRT scanline filter on/off and persist the choice."""
    _settings["crt"] = not _settings["crt"]
    _persist("crt")
    notify("FILTRO CRT ON" if _settings["crt"] else "FILTRO CRT OFF")
    return _settings["crt"]


# ============================================================================
# Window management
# ============================================================================

def make_icon() -> pygame.Surface:
    """Draw the window icon (a little neon space invader) - no file needed."""
    art = (
        "..#.....#..",
        "...#...#...",
        "..#######..",
        ".##.###.##.",
        "###########",
        "#.#######.#",
        "#.#.....#.#",
        "...##.##...",
    )
    icon = pygame.Surface((32, 32), pygame.SRCALPHA)
    icon.fill((0, 0, 0, 0))
    pygame.draw.rect(icon, (18, 10, 40), (0, 0, 32, 32), border_radius=6)
    px = 2
    ox = (32 - len(art[0]) * px) // 2
    oy = (32 - len(art) * px) // 2
    for y, row in enumerate(art):
        for x, ch in enumerate(row):
            if ch == "#":
                color = NEON_CYAN if y < 4 else NEON_MAGENTA
                icon.fill(color, (ox + x * px, oy + y * px, px, px))
    return icon


_icon_set: bool = False


def setup_screen(caption: str = "Retro Arcade Collection") -> pygame.Surface:
    """
    Return the game window, creating it only if needed.

    The window uses ``pygame.SCALED | pygame.RESIZABLE``: the game always draws
    on an 800x600 canvas, while the window can be resized or made fullscreen
    (F11) with crisp, aspect-correct scaling. Because the window is reused,
    switching between launcher and games no longer flickers or drops out of
    fullscreen.
    """
    global _icon_set
    pygame.init()
    load_settings()
    if not _icon_set:
        try:
            pygame.display.set_icon(make_icon())
        except pygame.error:
            pass
        _icon_set = True
    surf = pygame.display.get_surface()
    if surf is None or surf.get_size() != (W, H):
        try:
            surf = pygame.display.set_mode((W, H), pygame.SCALED | pygame.RESIZABLE)
        except pygame.error:
            surf = pygame.display.set_mode((W, H))
    pygame.display.set_caption(caption)
    pygame.key.set_repeat()  # games read held keys themselves
    return surf


def shutdown() -> None:
    """Release cached pygame resources and quit pygame cleanly.

    Fonts and surfaces cached by this module would become invalid after
    ``pygame.quit()``; clearing them makes it safe to call ``setup_screen``
    again later in the same process (tests, ``--game`` runs...).
    """
    global _icon_set, _crt_overlay
    clear_font_cache()
    _crt_overlay = None
    _icon_set = False
    pygame.quit()


def toggle_fullscreen() -> None:
    """Switch between window and fullscreen (keeps the 4:3 aspect ratio)."""
    try:
        pygame.display.toggle_fullscreen()
    except pygame.error:
        notify("SCHERMO INTERO NON DISPONIBILE")


def screenshots_dir() -> Path:
    from scores import default_path
    return default_path().parent / "screenshots"


def take_screenshot(surface: pygame.Surface | None = None) -> Path | None:
    """Save the current frame as PNG in ``screenshots/`` and return its path."""
    surface = surface or pygame.display.get_surface()
    if surface is None:
        return None
    folder = screenshots_dir()
    try:
        folder.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        path = folder / f"retro_arcade_{stamp}.png"
        pygame.image.save(surface, str(path))
    except (OSError, pygame.error):
        notify("SCREENSHOT NON RIUSCITO")
        return None
    sfx.play("blip")
    notify("SCREENSHOT SALVATO")
    return path


def handle_global_event(event: pygame.event.Event) -> bool:
    """
    Handle keys that work everywhere (launcher, games, menus).

    * F11 or Alt+Enter: fullscreen on/off
    * F12: save a screenshot

    Returns:
        True if the event was consumed and the caller should ignore it.
    """
    if event.type != pygame.KEYDOWN:
        return False
    if event.key == pygame.K_F11 or (
        event.key == pygame.K_RETURN and event.mod & pygame.KMOD_ALT
    ):
        toggle_fullscreen()
        return True
    if event.key == pygame.K_F12:
        take_screenshot()
        return True
    return False


# --- toast notifications (drawn by present) --------------------------------

_toast: dict[str, object] = {"text": "", "until": 0.0}


def notify(text: str, seconds: float = 1.6) -> None:
    """Show a short message in the bottom-right corner of the screen."""
    _toast["text"] = text
    _toast["until"] = time.monotonic() + seconds


def _draw_toast(screen: pygame.Surface) -> None:
    remaining = float(_toast["until"]) - time.monotonic()
    if remaining <= 0 or not _toast["text"]:
        return
    surf = render_pixel_text(str(_toast["text"]), 2, NEON_YELLOW)
    box = surf.get_rect(bottomright=(W - 14, H - 14)).inflate(18, 14)
    panel = pygame.Surface(box.size, pygame.SRCALPHA)
    alpha = int(220 * min(1.0, remaining / 0.3))
    pygame.draw.rect(panel, (10, 8, 24, alpha), panel.get_rect(), border_radius=6)
    pygame.draw.rect(panel, (*NEON_YELLOW, alpha), panel.get_rect(), 2, border_radius=6)
    screen.blit(panel, box)
    surf.set_alpha(alpha + 35)
    screen.blit(surf, surf.get_rect(center=box.center))


# --- CRT filter -----------------------------------------------------------

_crt_overlay: pygame.Surface | None = None


def build_crt_overlay(size: tuple[int, int] = (W, H)) -> pygame.Surface:
    """Pre-render scanlines + vignette into one transparent surface."""
    w, h = size
    overlay = pygame.Surface((w, h), pygame.SRCALPHA)
    for y in range(0, h, 3):
        pygame.draw.line(overlay, (0, 0, 0, 34), (0, y), (w, y))
    steps = 60
    for i in range(steps):
        alpha = int(70 * (1 - i / steps) ** 3)
        if alpha <= 0:
            continue
        pygame.draw.rect(overlay, (0, 0, 0, alpha), (i, i, w - 2 * i, h - 2 * i),
                         width=1, border_radius=24)
    return overlay


def present(screen: pygame.Surface | None = None) -> None:
    """Finish a frame: CRT filter (if enabled), toast message, flip."""
    global _crt_overlay
    screen = screen or pygame.display.get_surface()
    if screen is None:
        return
    if _settings["crt"]:
        if _crt_overlay is None or _crt_overlay.get_size() != screen.get_size():
            _crt_overlay = build_crt_overlay(screen.get_size())
        screen.blit(_crt_overlay, (0, 0))
    _draw_toast(screen)
    pygame.display.flip()


# ============================================================================
# Fonts
# ============================================================================

_font_cache: OrderedDict[tuple[str | None, int, bool], pygame.font.Font] = OrderedDict()
_FONT_CACHE_MAX_SIZE: int = 32

# Monospace fonts tried in order (Windows, Linux, macOS), then pygame's own.
_MONO_FALLBACKS = ("consolas", "dejavusansmono", "liberationmono", "menlo",
                   "couriernew", "freemono")


def _create_font(name: str | None, size: int, bold: bool) -> pygame.font.Font:
    candidates = ([name] if name else []) + list(_MONO_FALLBACKS)
    for candidate in candidates:
        try:
            path = pygame.font.match_font(candidate, bold=bold)
        except Exception:
            path = None
        if path:
            try:
                font = pygame.font.Font(path, size)
                if bold and "bold" not in path.lower():
                    font.set_bold(True)
                return font
            except (OSError, pygame.error):
                continue
    font = pygame.font.Font(None, int(size * 1.25))  # pygame's bundled font
    font.set_bold(bold)
    return font


def safe_font(
    name_or_size: int | str | None = None,
    size: int | None = None,
    bold: bool = False,
) -> pygame.font.Font:
    """
    Get (or create and cache) a font, with automatic fallbacks.

    Calling conventions::

        safe_font(24)                      # default monospace font, size 24
        safe_font("consolas", 32, bold=True)
        safe_font(None, 16)

    Fallback chain: requested font -> Consolas -> DejaVu Sans Mono ->
    Liberation Mono -> Menlo -> Courier New -> FreeMono -> pygame default.
    Fonts live in an LRU cache (32 entries), so creating them every frame
    costs nothing.

    Raises:
        ValueError: if a name (or None) is given without ``size``.
    """
    if not pygame.font.get_init():
        pygame.font.init()

    if isinstance(name_or_size, int) and not isinstance(name_or_size, bool):
        actual_name: str | None = None
        actual_size = name_or_size
    else:
        if size is None:
            raise ValueError("size parameter required when name_or_size is a string or None")
        actual_name = name_or_size if isinstance(name_or_size, str) else None
        try:
            actual_size = int(size)
        except (TypeError, ValueError):
            actual_size = 14
    actual_size = max(1, actual_size)

    key = (actual_name, actual_size, bold)
    font = _font_cache.get(key)
    if font is not None:
        _font_cache.move_to_end(key)
        return font
    font = _create_font(actual_name, actual_size, bold)
    _font_cache[key] = font
    if len(_font_cache) > _FONT_CACHE_MAX_SIZE:
        _font_cache.popitem(last=False)
    return font


def clear_font_cache() -> None:
    """Forget every cached font (they will be recreated on demand)."""
    _font_cache.clear()


# ============================================================================
# Text & drawing helpers
# ============================================================================

def draw_text(
    screen: pygame.Surface,
    text: str,
    font: pygame.font.Font,
    color: Color,
    pos: tuple[int, int],
    anchor: str = "topleft",
    shadow: bool = False,
) -> pygame.Rect:
    """Render ``text`` and blit it using any Rect anchor (``"center"``...)."""
    surf = font.render(text, True, color)
    rect = surf.get_rect(**{anchor: pos})
    if shadow:
        screen.blit(font.render(text, True, BLACK), rect.move(2, 2))
    screen.blit(surf, rect)
    return rect


def draw_text_centered(
    screen: pygame.Surface,
    text: str,
    font: pygame.font.Font,
    color: Color,
    y: int,
    x: int | None = None,
) -> pygame.Rect:
    """Draw text horizontally centered at height ``y`` (or at ``x`` if given)."""
    surf = font.render(text, True, color)
    w = screen.get_width()
    x_pos = (w // 2 - surf.get_width() // 2) if x is None else x
    screen.blit(surf, (x_pos, y))
    return surf.get_rect(x=x_pos, y=y)


def draw_hud(
    screen: pygame.Surface,
    score: int,
    level: int,
    hud_font: pygame.font.Font,
    extra_text: str | None = None,
) -> None:
    """Classic one-line HUD: score left, level center, extra text right."""
    w = screen.get_width()
    draw_text(screen, f"SCORE: {score:08d}", hud_font, SCORE_COLOR, (10, 10))
    draw_text(screen, f"LEVEL: {level}", hud_font, HUD_TEXT_COLOR, (w // 2, 10), "midtop")
    if extra_text:
        draw_text(screen, extra_text, hud_font, HUD_TEXT_COLOR, (w - 10, 10), "topright")


def pixel_title(
    screen: pygame.Surface,
    text: str,
    pos: tuple[int, int],
    scale: int = 4,
    color: Color = NEON_CYAN,
    anchor: str = "center",
    glow: bool = True,
) -> pygame.Rect:
    """Big glowing bitmap-font title (see :mod:`pixel_font`)."""
    return blit_pixel_text(screen, text, pos, scale, color, anchor, glow=glow)


def draw_panel(
    screen: pygame.Surface,
    rect: pygame.Rect,
    border: Color = NEON_CYAN,
    fill_alpha: int = 225,
    radius: int = 12,
) -> None:
    """Translucent dark panel with a neon border."""
    panel = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(panel, (*PANEL_BG, fill_alpha), panel.get_rect(), border_radius=radius)
    pygame.draw.rect(panel, (*border, 90), panel.get_rect(), 6, border_radius=radius)
    pygame.draw.rect(panel, (*border, 255), panel.get_rect().inflate(-4, -4), 2,
                     border_radius=radius - 2)
    screen.blit(panel, rect)


def draw_hearts(screen: pygame.Surface, lives: int, pos: tuple[int, int],
                color: Color = NEON_RED, scale: int = 2, anchor: str = "topright") -> None:
    """Draw ``lives`` little pixel hearts."""
    blit_pixel_text(screen, "♥" * max(0, lives), pos, scale, color, anchor)


def format_time(seconds: float) -> str:
    """Format seconds as ``m:ss`` (e.g. 75.4 -> ``"1:15"``)."""
    seconds = max(0, int(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


def lerp_color(a: Color, b: Color, t: float) -> Color:
    """Linear interpolation between two RGB colors (t in 0..1)."""
    t = max(0.0, min(1.0, t))
    return (int(a[0] + (b[0] - a[0]) * t),
            int(a[1] + (b[1] - a[1]) * t),
            int(a[2] + (b[2] - a[2]) * t))


# ============================================================================
# Menus
# ============================================================================

MenuOption = tuple[object, str]  # (label or callable returning label, value)

_CONFIRM_KEYS = (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE)


def _option_label(label: object) -> str:
    return label() if callable(label) else str(label)


def _run_menu(
    screen: pygame.Surface,
    title: str,
    info_lines: Sequence[str],
    options: Sequence[MenuOption],
    hotkeys: dict[int, str] | None = None,
    cancel_value: str | None = None,
    title_color: Color = NEON_CYAN,
    backdrop: pygame.Surface | None = None,
    dim: bool = True,
    default: int = 0,
    subtitle: str | None = None,
    subtitle_color: Color = NEON_YELLOW,
    input_delay: float = 0.0,
) -> str:
    """
    Generic keyboard + mouse menu drawn in a neon panel.

    The frame under the menu is captured once and redrawn every tick, so the
    translucent overlay stays translucent (the old menu re-blitted a 70%-black
    layer on top of itself every frame, turning the screen fully black).

    Special option values ``"toggle_sound"`` and ``"toggle_crt"`` flip the
    setting in place without closing the menu. ``input_delay`` ignores
    confirmations for a moment, so a player hammering SPACE to shoot does not
    skip the game-over screen by accident.
    """
    hotkeys = hotkeys or {}
    snapshot = backdrop if backdrop is not None else screen.copy()
    shade = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
    shade.fill((4, 2, 14, 170 if dim else 0))
    body_font = safe_font(16)
    clock = pygame.time.Clock()
    selected = max(0, min(default, len(options) - 1))
    option_rects: list[pygame.Rect] = []
    t0 = time.monotonic()

    while True:
        choice: str | None = None
        accepting = time.monotonic() - t0 >= input_delay
        for event in pygame.event.get():
            if handle_global_event(event):
                continue
            if event.type == pygame.QUIT:
                return "quit"
            if not accepting and event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                continue
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_UP, pygame.K_w):
                    selected = (selected - 1) % len(options)
                    sfx.play("move")
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    selected = (selected + 1) % len(options)
                    sfx.play("move")
                elif event.key in _CONFIRM_KEYS:
                    choice = options[selected][1]
                elif event.key == pygame.K_ESCAPE and cancel_value is not None:
                    sfx.play("back")
                    return cancel_value
                elif event.key in hotkeys:
                    choice = hotkeys[event.key]
            elif event.type == pygame.MOUSEMOTION:
                for i, r in enumerate(option_rects):
                    if r.collidepoint(event.pos) and i != selected:
                        selected = i
                        sfx.play("move", 0.5)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for i, r in enumerate(option_rects):
                    if r.collidepoint(event.pos):
                        selected = i
                        choice = options[i][1]

        if choice == "toggle_sound":
            toggle_sound()
        elif choice == "toggle_crt":
            toggle_crt()
            sfx.play("select")
        elif choice is not None:
            sfx.play("select")
            return choice

        # ---------------------------------------------------------- draw
        screen.blit(snapshot, (0, 0))
        screen.blit(shade, (0, 0))

        title_surf = render_pixel_text(title, 4 if len(title) <= 16 else 3, title_color, glow=True)
        opt_h = 34
        info_h = len(info_lines) * 22 + (12 if info_lines else 0)
        sub_h = 30 if subtitle else 0
        widths = [460, title_surf.get_width() + 60]
        widths += [body_font.size(line)[0] + 60 for line in info_lines]
        panel_w = min(max(widths), W - 40)
        panel_h = 40 + title_surf.get_height() + sub_h + info_h + len(options) * opt_h + 44
        panel = pygame.Rect(0, 0, panel_w, panel_h)
        panel.center = (W // 2, H // 2)
        draw_panel(screen, panel, title_color)

        y = panel.top + 22
        screen.blit(title_surf, title_surf.get_rect(midtop=(W // 2, y)))
        y += title_surf.get_height() + 6
        if subtitle:
            pulse = 0.6 + 0.4 * math.sin((time.monotonic() - t0) * 6)
            blit_pixel_text(screen, subtitle, (W // 2, y + 6), 2,
                            lerp_color(BG, subtitle_color, pulse), "midtop")
            y += sub_h
        for line in info_lines:
            draw_text(screen, line, body_font, TEXT_DIM, (W // 2, y), "midtop")
            y += 22
        if info_lines:
            y += 12

        option_rects = []
        for i, (label, _value) in enumerate(options):
            text = _option_label(label)
            row = pygame.Rect(0, 0, panel_w - 80, opt_h - 6)
            row.midtop = (W // 2, y)
            option_rects.append(row)
            if i == selected:
                pygame.draw.rect(screen, (*title_color,), row, 2, border_radius=6)
                hl = pygame.Surface(row.size, pygame.SRCALPHA)
                hl.fill((*title_color, 40))
                screen.blit(hl, row)
                blit_pixel_text(screen, "> " + text + " <", row.center, 2, WHITE, "center")
            else:
                blit_pixel_text(screen, text, row.center, 2, TEXT_DIM, "center")
            y += opt_h

        hint = "↑↓ SCEGLI   INVIO CONFERMA" + ("   ESC INDIETRO" if cancel_value else "")
        blit_pixel_text(screen, hint, (W // 2, panel.bottom - 22), 1, TEXT_DIM, "center")
        present(screen)
        clock.tick(30)


def in_game_menu(
    screen: pygame.Surface,
    title: str,
    commands_lines: Sequence[str],
    title_font: pygame.font.Font | None = None,
    small_font: pygame.font.Font | None = None,
) -> str:
    """
    Pause menu shown over the frozen game frame.

    Returns one of ``"resume"``, ``"restart"``, ``"menu"``, ``"quit"``.
    Shortcuts: ESC/P = resume, R = restart, M = main menu, Q = quit.
    The font arguments are kept for backwards compatibility and ignored.
    """
    sfx.play("pause")
    options: list[MenuOption] = [
        ("RIPRENDI", "resume"),
        ("RICOMINCIA", "restart"),
        (lambda: f"AUDIO: {'ON' if sound_enabled() else 'OFF'}", "toggle_sound"),
        (lambda: f"FILTRO CRT: {'ON' if crt_enabled() else 'OFF'}", "toggle_crt"),
        ("TORNA AL MENU", "menu"),
        ("ESCI DAL GIOCO", "quit"),
    ]
    hotkeys = {pygame.K_r: "restart", pygame.K_m: "menu", pygame.K_q: "quit",
               pygame.K_p: "resume"}
    return _run_menu(screen, "PAUSA", list(commands_lines), options, hotkeys,
                     cancel_value="resume", title_color=NEON_CYAN, subtitle=title.upper())


def end_screen(
    screen: pygame.Surface,
    title: str,
    lines: Sequence[str] = (),
    *,
    new_record: bool = False,
    win: bool = False,
) -> str:
    """
    Game-over / victory screen over the last frame.

    Returns ``"restart"``, ``"menu"`` or ``"quit"`` (ESC = back to menu).
    """
    sfx.play("record" if new_record else ("win" if win else "lose"))
    options: list[MenuOption] = [
        ("GIOCA ANCORA", "restart"),
        ("TORNA AL MENU", "menu"),
        ("ESCI DAL GIOCO", "quit"),
    ]
    hotkeys = {pygame.K_r: "restart", pygame.K_m: "menu", pygame.K_q: "quit"}
    color = NEON_GREEN if win else NEON_MAGENTA
    return _run_menu(screen, title, list(lines), options, hotkeys, cancel_value="menu",
                     title_color=color,
                     subtitle="★ NUOVO RECORD! ★" if new_record else None,
                     input_delay=0.6)


def open_exit_menu(
    screen: pygame.Surface,
    title: str,
    commands: Sequence[str],
    title_font: pygame.font.Font | None = None,
    body_font: pygame.font.Font | None = None,
) -> str | None:
    """
    Backwards-compatible wrapper around :func:`end_screen`.

    Returns ``"restart"``, ``"menu"`` or ``"quit"``. Unlike the old version it
    no longer calls ``pygame.quit()``: the launcher owns the shutdown.
    """
    return end_screen(screen, title, commands)


def message_box(
    screen: pygame.Surface,
    title: str,
    lines: Sequence[str],
    button: str = "OK",
    title_color: Color = NEON_ORANGE,
) -> str:
    """Simple modal message with a single button. Returns ``"ok"`` or ``"quit"``."""
    result = _run_menu(screen, title, list(lines), [(button, "ok")],
                       cancel_value="ok", title_color=title_color)
    return "quit" if result == "quit" else "ok"


def select_menu(
    screen: pygame.Surface,
    title: str,
    options: Sequence[str],
    info_lines: Sequence[str] = (),
    default: int = 0,
    title_color: Color = NEON_CYAN,
    backdrop: pygame.Surface | None = None,
) -> int | str:
    """
    Pre-game option picker (mode, difficulty...).

    Returns:
        The index of the chosen option, or ``"menu"`` (ESC) / ``"quit"``.
    """
    if backdrop is None:
        backdrop = pygame.Surface(screen.get_size())
        backdrop.fill(BG)
    opts: list[MenuOption] = [(label, str(i)) for i, label in enumerate(options)]
    result = _run_menu(screen, title, list(info_lines), opts, cancel_value="menu",
                       title_color=title_color, backdrop=backdrop, dim=False,
                       default=default)
    if result in ("menu", "quit"):
        return result
    return int(result)


# ============================================================================
# Small engine helpers
# ============================================================================

class GameClock:
    """``pygame.time.Clock`` wrapper returning a clamped delta in seconds."""

    def __init__(self, fps: int = FPS) -> None:
        self.fps = fps
        self._clock = pygame.time.Clock()

    def tick(self) -> float:
        """Wait for the next frame; return elapsed seconds (max ``MAX_DT``)."""
        return min(self._clock.tick(self.fps) / 1000.0, MAX_DT)

    def reset(self) -> None:
        """Discard the time spent in a menu (call right after it closes)."""
        self._clock.tick()

    def get_fps(self) -> float:
        return self._clock.get_fps()


class Stopwatch:
    """Game timer driven by frame deltas, so pauses are automatically excluded."""

    def __init__(self) -> None:
        self.elapsed: float = 0.0
        self.running: bool = True

    def update(self, dt: float) -> None:
        if self.running:
            self.elapsed += dt

    def stop(self) -> None:
        self.running = False

    def reset(self) -> None:
        self.elapsed = 0.0
        self.running = True

    def __str__(self) -> str:
        return format_time(self.elapsed)


class Particles:
    """
    Minimal, fast particle system (sparks, debris, confetti).

    Particles are plain lists ``[x, y, vx, vy, life, max_life, color, size,
    gravity]`` drawn as shrinking squares - no per-particle surfaces.
    """

    def __init__(self, max_particles: int = 600) -> None:
        self.items: list[list] = []
        self.max_particles = max_particles

    def burst(
        self,
        x: float,
        y: float,
        color: Color | Sequence[Color],
        count: int = 14,
        speed: tuple[float, float] = (60.0, 240.0),
        life: tuple[float, float] = (0.3, 0.8),
        size: tuple[int, int] = (2, 4),
        gravity: float = 0.0,
        angle: float = 0.0,
        spread: float = math.tau,
    ) -> None:
        """Emit ``count`` particles from ``(x, y)``."""
        colors = [color] if isinstance(color[0], int) else list(color)  # type: ignore[index]
        for _ in range(count):
            if len(self.items) >= self.max_particles:
                self.items.pop(0)
            a = angle + random.uniform(-spread / 2, spread / 2)
            v = random.uniform(*speed)
            lt = random.uniform(*life)
            self.items.append([x, y, math.cos(a) * v, math.sin(a) * v, lt, lt,
                               random.choice(colors), random.randint(*size), gravity])

    def update(self, dt: float) -> None:
        alive = []
        for p in self.items:
            p[4] -= dt
            if p[4] <= 0:
                continue
            p[3] += p[8] * dt
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            alive.append(p)
        self.items = alive

    def draw(self, surface: pygame.Surface, offset: tuple[int, int] = (0, 0)) -> None:
        ox, oy = offset
        for x, y, _vx, _vy, life, max_life, color, size, _g in self.items:
            s = max(1, int(size * (life / max_life) + 0.5))
            surface.fill(color, (int(x) - s // 2 + ox, int(y) - s // 2 + oy, s, s))

    def clear(self) -> None:
        self.items.clear()

    def __len__(self) -> int:
        return len(self.items)


class FloatingTexts:
    """Score pop-ups ("+10") that float upwards and fade out."""

    def __init__(self) -> None:
        self.items: list[list] = []  # [surface, x, y, life, max_life]

    def add(self, text: str, x: float, y: float, color: Color = NEON_YELLOW,
            life: float = 0.8, scale: int = 2) -> None:
        surf = render_pixel_text(text, scale, color, shadow=(0, 0, 0)).copy()
        self.items.append([surf, x, y, life, life])

    def update(self, dt: float) -> None:
        for item in self.items:
            item[2] -= 40 * dt
            item[3] -= dt
        self.items = [i for i in self.items if i[3] > 0]

    def draw(self, surface: pygame.Surface) -> None:
        for surf, x, y, life, max_life in self.items:
            surf.set_alpha(int(255 * min(1.0, life / max_life * 1.5)))
            surface.blit(surf, surf.get_rect(center=(int(x), int(y))))

    def clear(self) -> None:
        self.items.clear()


class ScreenShake:
    """Trauma-based screen shake: ``add(0.4)`` on impact, ``apply`` each frame."""

    def __init__(self, max_offset: float = 9.0) -> None:
        self.trauma: float = 0.0
        self.max_offset = max_offset

    def add(self, amount: float) -> None:
        self.trauma = min(1.0, self.trauma + amount)

    def update(self, dt: float) -> None:
        self.trauma = max(0.0, self.trauma - dt * 1.8)

    def offset(self) -> tuple[int, int]:
        mag = self.max_offset * self.trauma * self.trauma
        return (int(random.uniform(-mag, mag)), int(random.uniform(-mag, mag)))

    def apply(self, screen: pygame.Surface, fill: Color = BG) -> None:
        """Shift the finished frame by the current shake offset."""
        if self.trauma <= 0.01:
            return
        dx, dy = self.offset()
        if dx or dy:
            frame = screen.copy()
            screen.fill(fill)
            screen.blit(frame, (dx, dy))


def ensure_scores(
    load_scores: Callable[[], dict] | None,
    save_scores: Callable[[dict], None] | None,
) -> tuple[Callable[[], dict], Callable[[dict], None]]:
    """Shortcut for :func:`scores.resolve` (standalone games still save)."""
    from scores import resolve
    return resolve(load_scores, save_scores)
