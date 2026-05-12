# game_shared.py
# Shared helpers for in-game menus, font management, and graphics utilities
# Provides safe font handling, UI components, and color constants for all games

from __future__ import annotations

import pygame
from typing import Optional
from collections import OrderedDict


# ============================================================================
# Color Constants - Shared across all games
# ============================================================================

BG: tuple[int, int, int] = (20, 20, 40)  # Dark space-like background
WHITE: tuple[int, int, int] = (255, 255, 255)
GRAY_LIGHT: tuple[int, int, int] = (220, 220, 220)
GRAY_MEDIUM: tuple[int, int, int] = (180, 180, 180)
GRAY_DARK: tuple[int, int, int] = (100, 100, 100)

# Neon colors for retro arcade aesthetic
NEON_GREEN: tuple[int, int, int] = (0, 255, 0)
NEON_BLUE: tuple[int, int, int] = (0, 100, 255)
NEON_PINK: tuple[int, int, int] = (255, 0, 150)
NEON_CYAN: tuple[int, int, int] = (0, 255, 255)
NEON_YELLOW: tuple[int, int, int] = (255, 255, 0)

# Game-specific colors
SCORE_COLOR: tuple[int, int, int] = NEON_CYAN
HUD_TEXT_COLOR: tuple[int, int, int] = NEON_GREEN
WARNING_COLOR: tuple[int, int, int] = NEON_PINK

# Screen dimensions
W: int = 800
H: int = 600


# ============================================================================
# Font Cache - LRU-style caching to avoid recreating fonts
# ============================================================================

_font_cache: OrderedDict[tuple[Optional[str], int, bool], pygame.font.Font] = OrderedDict()
_FONT_CACHE_MAX_SIZE: int = 20


def in_game_menu(
    screen: pygame.Surface,
    title: str,
    commands_lines: list[str],
    title_font: pygame.font.Font,
    small_font: pygame.font.Font,
) -> str:
    """
    Display an in-game pause/menu overlay and handle user input.

    Shows a semi-transparent overlay with title and command instructions.
    Handles keyboard input for resume, restart, menu, and quit actions.
    The overlay surface is cached to avoid recreation every frame.

    Args:
        screen: The pygame Surface to draw to (game screen).
        title: Title text to display at top (e.g., "PAUSED").
        commands_lines: List of instruction lines to display (e.g., ["Lives: 3", "Score: 1250"]).
        title_font: Font for the title text.
        small_font: Font for command and info text.

    Returns:
        One of: "restart", "menu", "quit", "resume"
            - "restart": User pressed R (restart level)
            - "menu": User pressed M (return to main menu)
            - "quit": User pressed Q (quit application)
            - "resume": User pressed ESC (resume game)

    Keyboard Controls:
        R - Restart level
        M - Return to main menu
        Q - Quit application
        ESC - Resume game
        Window close button - Return to menu

    Note:
        The overlay surface is created once and reused, improving performance.
    """
    clock = pygame.time.Clock()
    w, h = screen.get_size()

    # Create overlay surface once, reuse it
    overlay = pygame.Surface((w, h), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 180))

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "menu"
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    return "restart"
                if event.key == pygame.K_m:
                    return "menu"
                if event.key == pygame.K_q:
                    return "quit"
                if event.key == pygame.K_ESCAPE:
                    return "resume"

        # Blit cached overlay
        screen.blit(overlay, (0, 0))

        # Draw title
        title_surf = title_font.render(title, True, WHITE)
        screen.blit(title_surf, (w // 2 - title_surf.get_width() // 2, 60))

        # Draw command lines
        y = 140
        for line in commands_lines:
            surf = small_font.render(line, True, GRAY_LIGHT)
            screen.blit(surf, (w // 2 - surf.get_width() // 2, y))
            y += 28

        # Draw control legend
        opts = "R: Ricomincia   |   M: Torna al menu   |   Q: Chiudi app   |   ESC: Riprendi"
        opts_surf = small_font.render(opts, True, GRAY_MEDIUM)
        screen.blit(opts_surf, (w // 2 - opts_surf.get_width() // 2, h - 80))

        pygame.display.flip()
        clock.tick(30)

# ============================================================================
# Text and Drawing Utilities
# ============================================================================

def draw_text_centered(
    screen: pygame.Surface,
    text: str,
    font: pygame.font.Font,
    color: tuple[int, int, int],
    y: int,
    x: Optional[int] = None,
) -> pygame.Rect:
    """
    Render text centered on screen horizontally, at a given Y position.

    A convenience function for centering text that all games can use consistently.
    Handles the boilerplate of rendering and centering calculations.

    Args:
        screen: The pygame Surface to draw to.
        text: The text string to render.
        font: The pygame Font to use for rendering.
        color: RGB tuple for text color.
        y: Y coordinate where text should be drawn.
        x: Optional X coordinate. If None, centers horizontally on screen width.

    Returns:
        The Rect of the rendered text surface (useful for collision detection, etc).

    Example:
        title_font = safe_font(48)
        draw_text_centered(screen, "GAME OVER", title_font, NEON_GREEN, 100)
    """
    surf = font.render(text, True, color)
    w = screen.get_size()[0]
    x_pos = (w // 2 - surf.get_width() // 2) if x is None else x
    screen.blit(surf, (x_pos, y))
    return surf.get_rect(x=x_pos, y=y)


def draw_hud(
    screen: pygame.Surface,
    score: int,
    level: int,
    hud_font: pygame.font.Font,
    extra_text: Optional[str] = None,
) -> None:
    """
    Draw a consistent HUD (Heads-Up Display) at the top of the screen.

    Shows score and level in a standardized format across all games. Optionally
    includes custom text (lives, time, etc.) on the right side.

    Args:
        screen: The pygame Surface to draw to.
        score: Current game score (integer).
        level: Current level number (integer).
        hud_font: The pygame Font to use for HUD text.
        extra_text: Optional additional text to display on the right (e.g., "Lives: 3").

    Example:
        hud_font = safe_font(18)
        draw_hud(screen, score=1250, level=2, hud_font=hud_font, extra_text="Lives: 3")
    """
    w = screen.get_size()[0]

    # Left-side: Score
    score_text = f"SCORE: {score:08d}"
    score_surf = hud_font.render(score_text, True, SCORE_COLOR)
    screen.blit(score_surf, (10, 10))

    # Center: Level
    level_text = f"LEVEL: {level}"
    level_surf = hud_font.render(level_text, True, HUD_TEXT_COLOR)
    level_x = w // 2 - level_surf.get_width() // 2
    screen.blit(level_surf, (level_x, 10))

    # Right-side: Extra text (if provided)
    if extra_text:
        extra_surf = hud_font.render(extra_text, True, HUD_TEXT_COLOR)
        screen.blit(extra_surf, (w - extra_surf.get_width() - 10, 10))


# ============================================================================
# Font Management - LRU-style caching to avoid recreating fonts
# ============================================================================

def safe_font(
    name_or_size: int | str | None = None,
    size: Optional[int] = None,
    bold: bool = False,
) -> pygame.font.Font:
    """
    Get or create a pygame Font with caching to avoid redundant font creation.

    Uses an LRU cache to store frequently used fonts. This prevents performance
    degradation from creating the same font multiple times per frame.

    Compatible with multiple calling conventions:
      safe_font(24)                    # System font, size 24
      safe_font("arial", 32, bold=True)  # Named font, bold
      safe_font(None, 16)              # Default font, size 16

    Args:
        name_or_size: Font name (str), size (int), or None for default.
                     If int, treated as size and uses system default font.
        size: Font size in pixels. Required if name_or_size is a string.
              Ignored if name_or_size is an int.
        bold: Whether to render the font as bold.

    Returns:
        A pygame Font object, cached and reused when possible.

    Raises:
        ValueError: If name_or_size is a string but size is not provided.

    Examples:
        font1 = safe_font(24)  # System font, size 24
        font2 = safe_font("arial", 32, bold=True)  # Named font, bold
        font3 = safe_font(None, 16)  # Default font, size 16
    """
    try:
        pygame.font.init()
    except Exception:
        pass

    # Normalize arguments to (name, size_val)
    if isinstance(name_or_size, int):
        actual_name: Optional[str] = None
        actual_size = name_or_size
    elif isinstance(name_or_size, str):
        if size is None:
            raise ValueError("size parameter required when name_or_size is a string")
        actual_name = name_or_size
        try:
            actual_size = int(size)
        except (ValueError, TypeError):
            actual_size = 14
    else:  # None or other type
        if size is None:
            raise ValueError("size parameter required when name_or_size is None")
        actual_name = None
        try:
            actual_size = int(size)
        except (ValueError, TypeError):
            actual_size = 14

    # Create cache key
    cache_key: tuple[Optional[str], int, bool] = (actual_name, actual_size, bold)

    # Return cached font if available
    if cache_key in _font_cache:
        # Move to end (mark as recently used)
        _font_cache.move_to_end(cache_key)
        return _font_cache[cache_key]

    # Try to create requested font
    try:
        f = pygame.font.SysFont(actual_name, actual_size, bold=bold)
        if f:
            _font_cache[cache_key] = f
            # Evict oldest entry if cache is too large
            if len(_font_cache) > _FONT_CACHE_MAX_SIZE:
                _font_cache.popitem(last=False)
            return f
    except Exception:
        pass

    # Fallback: try common font names
    common = [actual_name, "consolas", "arial", "dejavusans", "freesans",
              "timesnewroman", "couriernew", None]
    for nm in common:
        try:
            f = pygame.font.SysFont(nm, actual_size, bold=bold)
            if f:
                _font_cache[cache_key] = f
                if len(_font_cache) > _FONT_CACHE_MAX_SIZE:
                    _font_cache.popitem(last=False)
                return f
        except Exception:
            pass

    # Fallback: try default font
    try:
        default_name = pygame.font.get_default_font()
        candidate = pygame.font.match_font(default_name) or pygame.font.match_font("freesansbold")
        if candidate:
            f = pygame.font.Font(candidate, actual_size)
            _font_cache[cache_key] = f
            if len(_font_cache) > _FONT_CACHE_MAX_SIZE:
                _font_cache.popitem(last=False)
            return f
    except Exception:
        pass

    # Fallback: try None font
    try:
        f = pygame.font.Font(None, actual_size)
        _font_cache[cache_key] = f
        if len(_font_cache) > _FONT_CACHE_MAX_SIZE:
            _font_cache.popitem(last=False)
        return f
    except Exception:
        pass

    # Last resort: return DummyFont
    class DummyFont:
        """Fallback font when pygame fonts are unavailable."""
        def __init__(self, s: int):
            self.size = int(s)

        def render(self, text: str, aa: bool, color: tuple[int, int, int]) -> pygame.Surface:
            """Render text as a colored rectangle."""
            w = max(8, int(len(str(text)) * (self.size * 0.6)))
            h = max(8, int(self.size * 1.2))
            surf = pygame.Surface((w, h), pygame.SRCALPHA)
            surf.fill((0, 0, 0, 0))
            try:
                pygame.draw.rect(surf, color, (0, h // 3, w, h // 3))
            except Exception:
                pass
            return surf

    return DummyFont(actual_size)


def clear_font_cache() -> None:
    """
    Clear the font cache. Useful between scene transitions or level loads.

    This forces recreation of fonts on next use, freeing memory if needed.
    Generally not required unless managing memory tightly.
    """
    _font_cache.clear()

# ============================================================================
# Exit Menu Handler
# ============================================================================

def open_exit_menu(
    screen: pygame.Surface,
    title: str,
    commands: list[str],
    title_font: pygame.font.Font,
    body_font: pygame.font.Font,
) -> str | None:
    """
    Open a pause/exit menu and handle the user's choice.

    Wrapper around in_game_menu that handles the menu result and performs
    appropriate application-level actions (quit pygame, etc).

    Args:
        screen: The pygame Surface to draw to.
        title: Menu title text.
        commands: List of command instruction lines to display.
        title_font: Font for the title.
        body_font: Font for body text.

    Returns:
        "menu": User chose to return to main menu
        "restart": User chose to restart the level
        "quit": User chose to quit (pygame.quit called automatically)
        None: Menu was closed without a definitive choice

    Side Effects:
        Calls pygame.quit() if user selects quit option.

    Example:
        result = open_exit_menu(
            screen, "PAUSED", ["Score: 1250"], title_font, body_font
        )
        if result == "menu":
            return to_main_menu()
    """
    choice = in_game_menu(screen, title, commands, title_font, body_font)

    if choice == "menu":
        return "menu"
    if choice == "quit":
        pygame.quit()
        return "quit"
    if choice == "restart":
        return "restart"

    return None
