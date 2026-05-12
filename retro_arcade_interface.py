# retro_arcade_interface.py
"""
retro_arcade_interface.py

Improved launcher for retro arcade games with:
- Consolidated game dispatch (single launch_game function)
- Cached fonts and surfaces
- Type hints and comprehensive docstrings
- Transition effects and info panels
- Enhanced credits screen with animated scrolling
"""
import os
import sys
import math
import json
import pygame
from typing import Optional, Dict, Callable, Any

from game_shared import safe_font, BG, W as SH_W, H as SH_H

W, H = 800, 600
TITLE = "RETRO ARCADE COLLECTION"
SUBTITLE = "Python + Pygame"
TILES = [
    "Tic Tac Toe", "Snake", "Tetris",
    "Pong", "Breakout", "Space Invaders",
    "Maze Runner", "Memory Game", "Puzzle 15"
]

# Game scores in memory
SCORES = {
    "snake": 0,
    "tris_x": 0,
    "tris_o": 0,
    "tetris": 0
}

MARGIN_X, MARGIN_Y = 40, 120
SPACING_X, SPACING_Y = 30, 22
TILE_W, TILE_H = 200, 120

GRID_LINE = (30, 30, 50)
NEON_OUTER = (140, 50, 220)
NEON_INNER = (60, 200, 255)
TEXT_COLOR = (220, 220, 255)
HUD_COLOR = (120, 240, 120)

STATE_MAIN = "main"
STATE_CREDITS = "credits"

CREDITS_TEXT = [
    "RETRO ARCADE COLLECTION",
    "Creato da: Sir Alfry",
    "Tecnologie: Python, Pygame",
    "Instagram: https://www.instagram.com/sir_alfry",
    "ArtStation: https://siralfry.artstation.com/"
]

COMMANDS_PER_GAME = {
    "Tic Tac Toe": [
        "Classico 3x3. Clicca per posizionare X/O.",
        "R: Riavvia   ESC: Menu"
    ],
    "Snake": [
        "Muovi: Frecce o WASD. Mangia cibo per crescere.",
        "Cibo blu: bonus (cooldown). ESC: Menu (R/M/Q)"
    ],
    "Tetris": [
        "Frecce: sposta, UP: ruota, SPACE: hard drop.",
        "ESC: Menu (R/M/Q)"
    ],
    "Pong": [
        "W/S: Player 1, Freccia SU/GIU: Player 2.",
        "TAB: toggle 1P/2P, SPACE pausa, ESC: Menu"
    ],
    "Breakout": [
        "Muovi paddle e distruggi le mattonelle.",
        "ESC: Menu"
    ],
    "Space Invaders": [
        "Muovi e spara agli invasori (Frecce + Spazio).",
        "ESC: Menu"
    ],
    "Maze Runner": [
        "Trova l'uscita del labirinto.",
        "ESC: Menu"
    ],
    "Memory Game": [
        "Abbina le coppie cliccando le tessere.",
        "ESC: Menu"
    ],
    "Puzzle 15": [
        "Sposta le tessere per riordinare 1..15.",
        "Clicca per muovere. ESC: Menu"
    ]
}

# Game dispatch dictionary: maps game names to (module_name, function_name, needs_scores)
GAME_DISPATCH: Dict[str, tuple] = {
    "Snake": ("snake", "snake_game", True),
    "Tic Tac Toe": ("tris", "tris_game", True),
    "Tetris": ("tetris", "tetris_game", True),
    "Pong": ("pong", "main", False),
    "Breakout": ("breakout", "main_loop", False),
    "Space Invaders": ("space_invaders", "main", False),
    "Maze Runner": ("maze_runner", "main", False),
    "Memory Game": ("memory_game", "main", False),
    "Puzzle 15": ("puzzle15", "main", False),
}

# Font cache
_FONT_CACHE: Dict[tuple, pygame.font.Font] = {}


def get_cached_font(name: str, size: int, bold: bool = False) -> pygame.font.Font:
    """
    Get a cached font to avoid recreating font objects every frame.

    Args:
        name: Font name (e.g., "consolas")
        size: Font size in pixels
        bold: Whether to use bold variant

    Returns:
        pygame.font.Font object
    """
    key = (name, size, bold)
    if key not in _FONT_CACHE:
        _FONT_CACHE[key] = safe_font(name, size, bold=bold)
    return _FONT_CACHE[key]


def draw_rounded_rect(surf: pygame.Surface, rect: pygame.Rect,
                      color: tuple, radius: int = 12, width: int = 0) -> None:
    """Draw a rounded rectangle on a surface."""
    pygame.draw.rect(surf, color, rect, border_radius=radius, width=width)


def pixel_text(surf: pygame.Surface, text: str, size: int, pos: tuple,
               color: tuple = TEXT_COLOR, scale: float = 2, center: bool = False) -> None:
    """
    Render scaled pixel-style text on a surface.

    Args:
        surf: Target surface
        text: Text to render
        size: Base font size
        pos: Position (x, y)
        color: RGB color tuple
        scale: Scale multiplier for text
        center: If True, position is the center; otherwise top-left
    """
    small = get_cached_font("consolas", size)
    txt = small.render(text, True, color)
    sw = int(txt.get_width() * scale)
    sh = int(txt.get_height() * scale)
    scaled = pygame.transform.scale(txt, (max(1, sw), max(1, sh)))
    if center:
        r = scaled.get_rect(center=pos)
        surf.blit(scaled, r.topleft)
    else:
        surf.blit(scaled, pos)


# ============================================================================
# Thumbnail drawers
# ============================================================================

def draw_tic_tac_toe_thumb(surf: pygame.Surface, rect: pygame.Rect) -> None:
    """Draw Tic Tac Toe game thumbnail."""
    inner = rect.inflate(-16, -16)
    pygame.draw.rect(surf, (6, 6, 12), inner)
    cx, cy, w, h = inner.x, inner.y, inner.w, inner.h
    cell_w, cell_h = w // 3, h // 3
    for i in range(1, 3):
        pygame.draw.line(surf, (50, 100, 160), (cx + i*cell_w, cy), (cx + i*cell_w, cy + h), 3)
        pygame.draw.line(surf, (50, 100, 160), (cx, cy + i*cell_h), (cx + w, cy + i*cell_h), 3)
    f = get_cached_font("consolas", 24, bold=True)
    Xs = [(0, 0), (0, 2), (2, 1)]
    Os = [(1, 0), (1, 1), (1, 2)]
    for (r, c) in Xs:
        txt = f.render("X", True, (230, 50, 50))
        surf.blit(txt, (cx + c*cell_w + 6, cy + r*cell_h + 2))
    for (r, c) in Os:
        txt = f.render("O", True, (90, 140, 255))
        surf.blit(txt, (cx + c*cell_w + 8, cy + r*cell_h + 6))


def draw_snake_thumb(surf: pygame.Surface, rect: pygame.Rect) -> None:
    """Draw Snake game thumbnail."""
    inner = rect.inflate(-16, -16)
    pygame.draw.rect(surf, (0, 0, 0), inner)
    seg_w = 12
    snake_color = (30, 200, 40)
    sx = inner.x + 12
    sy = inner.y + inner.h // 2 - seg_w // 2
    for i in range(6):
        pygame.draw.rect(surf, snake_color, (sx + i*(seg_w + 2), sy, seg_w, seg_w))
    pygame.draw.circle(surf, (220, 50, 50), (inner.x + inner.w - 18, inner.y + 18), 6)


def draw_tetris_thumb(surf: pygame.Surface, rect: pygame.Rect) -> None:
    """Draw Tetris game thumbnail."""
    inner = rect.inflate(-16, -16)
    pygame.draw.rect(surf, (4, 4, 6), inner)
    colors = [(200, 40, 40), (40, 120, 220), (220, 200, 30), (60, 200, 80)]
    blocks = [
        (inner.x+28, inner.y+10, 20, 20, colors[0]),
        (inner.x+68, inner.y+6, 30, 12, colors[1]),
        (inner.x+108, inner.y+26, 12, 30, colors[2]),
        (inner.x+148, inner.y+8, 24, 18, colors[3])
    ]
    for x, y, w, h, c in blocks:
        pygame.draw.rect(surf, c, (x, y, w, h))


def draw_pong_thumb(surf: pygame.Surface, rect: pygame.Rect) -> None:
    """Draw Pong game thumbnail."""
    inner = rect.inflate(-16, -16)
    pygame.draw.rect(surf, (0, 0, 0), inner)
    left_paddle = (inner.x + 12, inner.y + inner.h // 2 - 18, 6, 36)
    right_paddle = (inner.x + inner.w - 18, inner.y + inner.h // 2 - 18, 6, 36)
    pygame.draw.rect(surf, (255, 255, 255), left_paddle)
    pygame.draw.rect(surf, (255, 255, 255), right_paddle)
    pygame.draw.circle(surf, (255, 255, 255), (inner.x + inner.w // 2, inner.y + inner.h // 2), 5)


def draw_breakout_thumb(surf: pygame.Surface, rect: pygame.Rect) -> None:
    """Draw Breakout game thumbnail."""
    inner = rect.inflate(-16, -16)
    pygame.draw.rect(surf, (8, 8, 8), inner)
    brick_h = 10
    cols = max(4, inner.w // 20)
    colors = [(255, 80, 80), (255, 170, 0), (255, 230, 60), (100, 220, 120), (80, 180, 255)]
    for row in range(4):
        for col in range(cols):
            bx = inner.x + col*20
            by = inner.y + row*(brick_h+2)
            c = colors[row % len(colors)]
            pygame.draw.rect(surf, c, (bx, by, 18, brick_h))
    pygame.draw.rect(surf, (255, 255, 255), (inner.x + inner.w // 2 - 20, inner.y + inner.h - 18, 40, 6))
    pygame.draw.circle(surf, (255, 255, 255), (inner.x + inner.w // 2 + 36, inner.y + inner.h - 26), 4)


def draw_space_invaders_thumb(surf: pygame.Surface, rect: pygame.Rect) -> None:
    """Draw Space Invaders game thumbnail."""
    inner = rect.inflate(-16, -16)
    pygame.draw.rect(surf, (0, 0, 8), inner)
    alien = [(0, 1, 0, 1, 0), (1, 1, 1, 1, 1), (1, 0, 1, 0, 1), (1, 1, 1, 1, 1)]
    px = 6
    base_x = inner.x + 24
    base_y = inner.y + 12
    for r, row in enumerate(alien):
        for c, v in enumerate(row):
            if v:
                pygame.draw.rect(surf, (220, 220, 220), (base_x + c*px*2, base_y + r*px*2, px, px))


def draw_maze_runner_thumb(surf: pygame.Surface, rect: pygame.Rect) -> None:
    """Draw Maze Runner game thumbnail."""
    inner = rect.inflate(-16, -16)
    pygame.draw.rect(surf, (10, 10, 12), inner)
    wall = (20, 120, 220)
    pygame.draw.rect(surf, wall, (inner.x + 10, inner.y + 10, inner.w - 20, 8))
    pygame.draw.rect(surf, wall, (inner.x + 10, inner.y + 28, 8, inner.h - 38))
    pygame.draw.rect(surf, wall, (inner.x + 40, inner.y + 28, inner.w - 80, 8))
    pygame.draw.rect(surf, wall, (inner.x + inner.w - 18, inner.y + 28, 8, inner.h - 38))
    pygame.draw.circle(surf, (240, 220, 70), (inner.x + 18, inner.y + inner.h - 22), 5)


def draw_memory_game_thumb(surf: pygame.Surface, rect: pygame.Rect) -> None:
    """Draw Memory Game game thumbnail."""
    inner = rect.inflate(-16, -16)
    pygame.draw.rect(surf, (8, 8, 8), inner)
    colors = [(220, 60, 60), (60, 130, 240), (70, 200, 80), (240, 220, 70)]
    size = min(inner.w // 4 - 6, inner.h - 16)
    start_x = inner.x + (inner.w - (size*4 + 3*6)) // 2
    y = inner.y + inner.h // 2 - size // 2
    for i, c in enumerate(colors):
        x = start_x + i*(size + 6)
        pygame.draw.rect(surf, c, (x, y, size, size))


def draw_puzzle15_thumb(surf: pygame.Surface, rect: pygame.Rect) -> None:
    """Draw Puzzle 15 game thumbnail."""
    inner = rect.inflate(-16, -16)
    pygame.draw.rect(surf, (6, 6, 6), inner)
    cols = 4
    tile = (inner.w - 6*(cols-1)) // cols
    f = get_cached_font("consolas", 12)
    n = 1
    for r in range(4):
        for c in range(4):
            if n == 16:
                break
            x = inner.x + c*(tile + 6)
            y = inner.y + r*(tile + 6)
            pygame.draw.rect(surf, (80, 80, 80), (x, y, tile, tile))
            txt = f.render(str(n), True, (230, 230, 230))
            surf.blit(txt, (x + tile // 2 - txt.get_width() // 2, y + tile // 2 - txt.get_height() // 2))
            n += 1


THUMB_DRAWERS = [
    draw_tic_tac_toe_thumb,
    draw_snake_thumb,
    draw_tetris_thumb,
    draw_pong_thumb,
    draw_breakout_thumb,
    draw_space_invaders_thumb,
    draw_maze_runner_thumb,
    draw_memory_game_thumb,
    draw_puzzle15_thumb
]


def create_background() -> pygame.Surface:
    """Create the gridded background surface."""
    surf = pygame.Surface((W, H))
    surf.fill(BG)
    for x in range(0, W, 24):
        pygame.draw.line(surf, GRID_LINE, (x, 0), (x, H))
    for y in range(0, H, 24):
        pygame.draw.line(surf, GRID_LINE, (0, y), (W, y))
    return surf


def create_scanlines_surface() -> pygame.Surface:
    """Create a scanlines effect surface."""
    scan = pygame.Surface((W, H), pygame.SRCALPHA)
    for y in range(0, H, 3):
        pygame.draw.line(scan, (0, 0, 0, 24), (0, y), (W, y))
    return scan


def create_crt_vignette_surface() -> pygame.Surface:
    """Create a CRT vignette effect surface."""
    vign = pygame.Surface((W, H), pygame.SRCALPHA)
    for i in range(120):
        a = int(140 * (i/120)**2)
        pygame.draw.rect(vign, (0, 0, 0, a//40), (i, i, W-2*i, H-2*i), border_radius=20)
    return vign


def _save_display_state() -> tuple:
    """Save current display state (size and caption)."""
    try:
        surf = pygame.display.get_surface()
        size = surf.get_size() if surf else (W, H)
    except Exception:
        size = (W, H)
    caption = pygame.display.get_caption()[0]
    return size, caption


def _restore_display_state(size: tuple, caption: str) -> None:
    """Restore saved display state."""
    try:
        pygame.display.set_mode(size)
        pygame.display.set_caption(caption or f"{TITLE} - {SUBTITLE}")
    except Exception:
        pygame.display.set_mode((W, H))
        pygame.display.set_caption(f"{TITLE} - {SUBTITLE}")


def launch_game(game_name: str, scores_getter: Callable[[], Dict],
                scores_setter: Callable[[Dict], None]) -> Optional[str]:
    """
    Unified game launcher using dispatch dictionary.

    Args:
        game_name: Name of the game to launch
        scores_getter: Callable that returns the scores dictionary
        scores_setter: Callable that accepts and saves scores dictionary

    Returns:
        "quit" if the game requested application exit, None otherwise
    """
    if game_name not in GAME_DISPATCH:
        print(f"Unknown game: {game_name}")
        return None

    module_name, func_name, needs_scores = GAME_DISPATCH[game_name]

    try:
        prev_size, prev_caption = _save_display_state()

        # Import the game module
        module = __import__(module_name)

        # Get the function or class to call
        func = getattr(module, func_name)

        # Call with appropriate arguments
        if needs_scores:
            result = func(scores_getter, scores_setter)
        else:
            result = func()

        _restore_display_state(prev_size, prev_caption)
        return result

    except Exception as e:
        print(f"Error launching {game_name}: {e}")
        import traceback
        traceback.print_exc()
        return None


def draw_transition_fade(surf: pygame.Surface, progress: float) -> None:
    """
    Draw a fade-to-black transition overlay.

    Args:
        surf: Target surface
        progress: Transition progress (0.0 to 1.0)
    """
    alpha = int(255 * progress)
    overlay = pygame.Surface((W, H))
    overlay.set_alpha(alpha)
    overlay.fill((0, 0, 0))
    surf.blit(overlay, (0, 0))


def draw_game_info_panel(surf: pygame.Surface, game_name: str, tiny_font: pygame.font.Font) -> None:
    """
    Draw an info panel at the bottom showing game commands.

    Args:
        surf: Target surface
        game_name: Name of the currently selected game
        tiny_font: Font for rendering text
    """
    if game_name not in COMMANDS_PER_GAME:
        return

    commands = COMMANDS_PER_GAME[game_name]
    panel_height = 60
    panel_y = H - panel_height

    # Semi-transparent panel background
    panel = pygame.Surface((W, panel_height), pygame.SRCALPHA)
    pygame.draw.rect(panel, (0, 0, 0, 120), panel.get_rect())
    pygame.draw.rect(panel, (60, 200, 255, 200), panel.get_rect(), width=2)
    surf.blit(panel, (0, panel_y))

    # Render commands
    y_offset = panel_y + 6
    for line in commands:
        txt = tiny_font.render(line, True, (200, 200, 220))
        surf.blit(txt, (12, y_offset))
        y_offset += 20


def draw_credits_screen(surf: pygame.Surface, big_font: pygame.font.Font,
                        small_font: pygame.font.Font, scroll_offset: float = 0.0) -> None:
    """
    Draw the credits screen with animated scrolling.

    Args:
        surf: Target surface
        big_font: Large font for title
        small_font: Regular font for credits
        scroll_offset: Vertical scroll offset in pixels
    """
    surf.blit(create_background(), (0, 0))
    pixel_text(surf, "CREDITS", 16, (W // 2, 80), color=(250, 200, 100), scale=2.5, center=True)

    y = 140 - int(scroll_offset) % 600  # Wrap scrolling
    for line in CREDITS_TEXT:
        txt = small_font.render(line, True, (220, 220, 220))
        if 0 <= y <= H:  # Only render if visible
            surf.blit(txt, (W // 2 - txt.get_width() // 2, y))
        y += 30

    # Add extra space for seamless loop
    y += 30
    for line in CREDITS_TEXT:
        txt = small_font.render(line, True, (220, 220, 220))
        if 0 <= y <= H:
            surf.blit(txt, (W // 2 - txt.get_width() // 2, y))
        y += 30

    pixel_text(surf, "C: Chiudi app   |   B o ESC: Torna al menu", 10,
               (W // 2, H - 80), color=(180, 180, 200), scale=1.5, center=True)


def draw_main_ui(surf: pygame.Surface, tile_rects: list, small_font: pygame.font.Font,
                 title_font: pygame.font.Font, sub_font: pygame.font.Font,
                 tiny_font: pygame.font.Font, selected: int = 4, pulse: float = 0.5,
                 clock: Optional[pygame.time.Clock] = None,
                 background_surf: Optional[pygame.Surface] = None,
                 scanlines_surf: Optional[pygame.Surface] = None,
                 vignette_surf: Optional[pygame.Surface] = None) -> None:
    """
    Draw the main launcher UI.

    Args:
        surf: Target surface
        tile_rects: List of pygame.Rect objects for game tiles
        small_font: Small font for labels
        title_font: Font for main title
        sub_font: Font for subtitle
        tiny_font: Tiny font for FPS/status text
        selected: Index of currently selected game
        pulse: Pulse factor for glow effect (0.0-1.0)
        clock: pygame.time.Clock for FPS display
        background_surf: Pre-rendered background surface
        scanlines_surf: Pre-rendered scanlines effect
        vignette_surf: Pre-rendered vignette effect
    """
    if background_surf is None:
        surf.blit(create_background(), (0, 0))
    else:
        surf.blit(background_surf, (0, 0))

    pixel_text(surf, TITLE, 16, (W // 2, 50), color=(50, 230, 255), scale=2.5, center=True)
    pixel_text(surf, SUBTITLE, 10, (W // 2, 85), color=(240, 240, 240), scale=2, center=True)

    # Draw tile borders
    for i, rect in enumerate(tile_rects):
        draw_rounded_rect(surf, rect, (18, 18, 30), radius=14, width=2)

    # Draw selection glow
    if 0 <= selected < len(tile_rects):
        rect = tile_rects[selected]
        glow = pygame.Surface((rect.w+40, rect.h+40), pygame.SRCALPHA)
        outer_alpha = int(110 * (0.6 + 0.4 * pulse))
        pygame.draw.rect(glow, (*NEON_OUTER, outer_alpha), glow.get_rect(), border_radius=22)
        surf.blit(glow, (rect.x-20, rect.y-20), special_flags=pygame.BLEND_RGBA_ADD)
        pygame.draw.rect(surf, NEON_INNER, rect, width=3, border_radius=14)
        pygame.draw.rect(surf, (*NEON_INNER, 160), rect.inflate(-8, -8), width=2, border_radius=12)

    # Draw thumbnails
    for i, rect in enumerate(tile_rects):
        THUMB_DRAWERS[i](surf, rect)

    # Draw tile labels
    for i, rect in enumerate(tile_rects):
        pixel_text(surf, TILES[i].upper(), 10, (rect.x + 14, rect.y + rect.h - 28),
                   color=(220, 220, 240), scale=1, center=False)

    # Draw FPS
    if clock is None:
        fps = 60
    else:
        fps = int(clock.get_fps() or 60)
    fps_text = tiny_font.render(f"{fps:2d} FPS", True, HUD_COLOR)
    surf.blit(fps_text, (16, 16))

    # Draw instructions
    pixel_text(surf, "SPACE: Select  |  ESC: Credits", 10, (W // 2, H - 40),
               color=(180, 180, 200), scale=1.5, center=True)

    # Draw watermark
    wm = tiny_font.render("pygame", True, (180, 180, 180))
    surf.blit(wm, (W - 8 - wm.get_width(), H - 8 - wm.get_height()))

    # Draw game info panel
    if 0 <= selected < len(TILES):
        draw_game_info_panel(surf, TILES[selected], tiny_font)

    # Apply effects
    if scanlines_surf is None:
        surf.blit(create_scanlines_surface(), (0, 0))
    else:
        surf.blit(scanlines_surf, (0, 0))

    if vignette_surf is None:
        surf.blit(create_crt_vignette_surface(), (0, 0))
    else:
        surf.blit(vignette_surf, (0, 0))


def main() -> None:
    """Main launcher loop."""
    headless = "--save" in sys.argv or "--headless" in sys.argv
    if headless:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

    pygame.init()

    screen = None
    if not headless:
        screen = pygame.display.set_mode((W, H))
        pygame.display.set_caption(f"{TITLE} - {SUBTITLE} ({W}x{H})")

        # Set window icon
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon_32.png")
        if os.path.exists(icon_path):
            icon_surface = pygame.image.load(icon_path)
            pygame.display.set_icon(icon_surface)

    # Cache fonts at startup
    title_font = get_cached_font("consolas", 18)
    sub_font = get_cached_font("consolas", 12)
    small_font = get_cached_font("consolas", 14)
    tiny_font = get_cached_font("consolas", 12)

    # Create tile rectangles
    tile_rects = []
    sx = MARGIN_X
    sy = MARGIN_Y
    for row in range(3):
        for col in range(3):
            x = sx + col * (TILE_W + SPACING_X)
            y = sy + row * (TILE_H + SPACING_Y)
            tile_rects.append(pygame.Rect(x, y, TILE_W, TILE_H))

    clock = pygame.time.Clock()
    selected = 4
    running = True
    pulse = 0.0
    current_state = STATE_MAIN
    transition_time = 0.0
    credits_scroll = 0.0

    # Pre-render surfaces
    background_surf = create_background()
    scanlines_surf = create_scanlines_surface()
    vignette_surf = create_crt_vignette_surface()

    # Headless/save mode
    if headless:
        surf = pygame.Surface((W, H), pygame.SRCALPHA)
        draw_main_ui(surf, tile_rects=tile_rects, small_font=small_font,
                     title_font=title_font, sub_font=sub_font, tiny_font=tiny_font,
                     selected=selected, pulse=0.5,
                     background_surf=background_surf, scanlines_surf=scanlines_surf,
                     vignette_surf=vignette_surf)
        out = "retro_arcade_generated.png"
        pygame.image.save(surf, out)
        print("Saved", out)
        return

    surf = pygame.Surface((W, H), pygame.SRCALPHA)

    # Main loop
    while running:
        dt = clock.tick(60) / 1000.0
        pulse += dt * 2.0
        pulse_factor = (1.0 + math.sin(pulse)) * 0.5
        credits_scroll += dt * 20.0  # Smooth scrolling in credits

        # Handle events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if current_state == STATE_MAIN:
                    if event.key == pygame.K_SPACE:
                        game_name = TILES[selected]
                        print(f"Launching: {game_name}")
                        transition_time = 0.2  # Start transition
                        # Transition will be drawn, then game launches in next frame
                    elif event.key == pygame.K_RIGHT:
                        selected = (selected + 1) % len(tile_rects)
                    elif event.key == pygame.K_LEFT:
                        selected = (selected - 1) % len(tile_rects)
                    elif event.key == pygame.K_DOWN:
                        selected = (selected + 3) % len(tile_rects)
                    elif event.key == pygame.K_UP:
                        selected = (selected - 3) % len(tile_rects)
                    elif event.key == pygame.K_ESCAPE:
                        current_state = STATE_CREDITS

                elif current_state == STATE_CREDITS:
                    if event.key == pygame.K_c:
                        pygame.quit()
                        sys.exit()
                    elif event.key == pygame.K_ESCAPE or event.key == pygame.K_b:
                        current_state = STATE_MAIN

            elif event.type == pygame.MOUSEMOTION and current_state == STATE_MAIN:
                mx, my = event.pos
                for i, r in enumerate(tile_rects):
                    if r.collidepoint(mx, my):
                        selected = i
                        break

            elif event.type == pygame.MOUSEBUTTONDOWN and current_state == STATE_MAIN:
                if event.button == 1:
                    mx, my = event.pos
                    for i, r in enumerate(tile_rects):
                        if r.collidepoint(mx, my):
                            game_name = TILES[i]
                            print(f"Clicked: {game_name}")
                            transition_time = 0.2  # Start transition
                            selected = i
                            break

        # Handle transition and game launch
        if transition_time > 0:
            transition_time -= dt
            if transition_time <= 0:
                # Launch game
                game_name = TILES[selected]
                result = launch_game(game_name, lambda: SCORES, lambda s: SCORES.update(s))
                if result == "quit":
                    pygame.quit()
                    sys.exit()
                transition_time = 0

        # Draw current state
        if current_state == STATE_MAIN:
            draw_main_ui(surf, tile_rects=tile_rects, small_font=small_font,
                         title_font=title_font, sub_font=sub_font, tiny_font=tiny_font,
                         selected=selected, pulse=pulse_factor, clock=clock,
                         background_surf=background_surf, scanlines_surf=scanlines_surf,
                         vignette_surf=vignette_surf)

            # Draw transition overlay
            if transition_time > 0:
                progress = 1.0 - (transition_time / 0.2)
                draw_transition_fade(surf, progress)

        elif current_state == STATE_CREDITS:
            draw_credits_screen(surf, title_font, small_font, credits_scroll)

        if screen:
            screen.blit(surf, (0, 0))
            pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
