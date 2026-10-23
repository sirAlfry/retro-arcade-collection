# retro_arcade_interface.py
"""
Retro Arcade Collection - main launcher.

Run it with::

    python retro_arcade_interface.py              # normal start
    python retro_arcade_interface.py --game snake # jump straight into a game
    python retro_arcade_interface.py --save out.png  # render the menu headless

Highlights:
    * Synthwave look (scrolling perspective grid, twinkling stars, neon glow)
      matching the project banner.
    * One data table (``GAMES``) drives everything: tiles, info panel, records
      and the dynamic import of each game (``GAME_DISPATCH`` pattern).
    * Persistent records shown in the info panel, last played game remembered.
    * A crash inside a game is caught, logged to ``retro_arcade.log`` and shown
      in a message box instead of killing the whole collection.
"""
from __future__ import annotations

import argparse
import importlib
import logging
import math
import os
import random
import sys
from collections.abc import Callable
from dataclasses import dataclass

import pygame

import game_shared as gs
import sfx
from game_shared import BG_DARK, TEXT, TEXT_DIM, H, W, format_time
from pixel_font import blit_pixel_text
from scores import ScoreStore

TITLE = "RETRO ARCADE COLLECTION"
SUBTITLE = "Python + Pygame-CE"
VERSION = "3.0.0"

log = logging.getLogger("retro_arcade")

# ============================================================================
# Game catalogue
# ============================================================================

ScoresDict = dict


def _rec(key: str, label: str = "RECORD") -> Callable[[ScoresDict], str | None]:
    def fmt(s: ScoresDict) -> str | None:
        value = s.get(key)
        return f"{label} {value}" if value else None
    return fmt


def _rec_tris(s: ScoresDict) -> str | None:
    x, o, d = s.get("tris_x", 0), s.get("tris_o", 0), s.get("tris_draw", 0)
    return f"X {x}  O {o}  PARI {d}" if (x or o or d) else None


def _rec_maze(s: ScoresDict) -> str | None:
    for key, label in (("maze_time_medium", "MEDIO"), ("maze_time_small", "PICCOLO"),
                       ("maze_time_large", "GRANDE"), ("maze_time_dark", "BUIO")):
        if s.get(key):
            return f"RECORD {format_time(s[key])} ({label})"
    return None


def _rec_memory(s: ScoresDict) -> str | None:
    value = s.get("memory_moves_normal") or s.get("memory_moves_easy") or s.get("memory_moves_hard")
    return f"MIN. MOSSE {value}" if value else None


def _rec_puzzle(s: ScoresDict) -> str | None:
    moves, secs = s.get("puzzle15_moves"), s.get("puzzle15_time")
    if not moves:
        return None
    return f"MOSSE {moves}  TEMPO {format_time(secs or 0)}"


@dataclass(frozen=True)
class GameInfo:
    """Everything the launcher needs to know about one game."""

    name: str
    module: str
    func: str
    description: str
    controls: tuple[str, ...]
    record: Callable[[ScoresDict], str | None]
    accent: gs.Color


GAMES: tuple[GameInfo, ...] = (
    GameInfo("Tic Tac Toe", "tris", "main",
             "Tris contro un amico o una CPU imbattibile (Minimax + Alpha-Beta).",
             ("Mouse o frecce + INVIO: piazza il segno",
              "TAB: cambia modalità   1/2/3: difficoltà CPU   ESC: pausa"),
             _rec_tris, gs.NEON_BLUE),
    GameInfo("Snake", "snake", "main",
             "Mangia, cresci, non morderti la coda. Il frutto blu vale +5 ma scade!",
             ("Frecce o WASD: muovi il serpente", "ESC o P: pausa"),
             _rec("snake"), gs.NEON_GREEN),
    GameInfo("Tetris", "tetris", "main",
             "Rotazione SRS con wall kick, hold, ghost piece, 3 pezzi in anteprima.",
             ("←/→ muovi  ↓ soft drop  SPAZIO hard drop  ↑/X ruota  Z ruota indietro",
              "C o SHIFT: hold   ESC o P: pausa"),
             _rec("tetris"), gs.NEON_PURPLE),
    GameInfo("Pong", "pong", "main",
             "Il primo videogioco da bar: contro la CPU (3 livelli) o in due.",
             ("Giocatore 1: W/S   Giocatore 2: frecce ↑/↓",
              "ESC o P: pausa   Vince chi arriva a 11"),
             _rec("pong_wins", "VITTORIE VS CPU"), gs.NEON_CYAN),
    GameInfo("Breakout", "breakout", "main",
             "Distruggi i mattoni, raccogli i power-up, sopravvivi ai livelli.",
             ("Mouse o frecce/A-D: muovi   SPAZIO/clic: lancia la palla",
              "Power-up: L larga  M multi-palla  S lenta  ♥ vita   ESC: pausa"),
             _rec("breakout"), gs.NEON_ORANGE),
    GameInfo("Space Invaders", "space_invaders", "main",
             "Ondate di alieni, scudi distruttibili e il misterioso UFO bonus.",
             ("Frecce o A/D: muovi   SPAZIO: spara", "ESC o P: pausa"),
             _rec("space_invaders"), gs.NEON_GREEN),
    GameInfo("Maze Runner", "maze_runner", "main",
             "Labirinti generati con DFS, 4 difficoltà (anche al buio) e aiuto BFS.",
             ("Frecce o WASD: muovi (tieni premuto per correre)",
              "H: suggerimento (+10 s)   ESC: pausa"),
             _rec_maze, gs.NEON_BLUE),
    GameInfo("Memory Game", "memory_game", "main",
             "Trova le coppie con meno mosse possibili. Tre dimensioni di griglia.",
             ("Mouse: gira le carte   Frecce + INVIO: gioca da tastiera",
              "ESC: pausa"),
             _rec_memory, gs.NEON_MAGENTA),
    GameInfo("Puzzle 15", "puzzle15", "main",
             "Il gioco del quindici: sempre risolvibile, con mosse multiple a clic.",
             ("Clic su una tessera (anche più tessere in fila) o frecce",
              "Le tessere al posto giusto si illuminano   ESC: pausa"),
             _rec_puzzle, gs.NEON_YELLOW),
)

# Backwards-compatible views of the catalogue (kept for older code/docs).
TILES: list[str] = [g.name for g in GAMES]
GAME_DISPATCH: dict[str, tuple[str, str, bool]] = {g.name: (g.module, g.func, True) for g in GAMES}
COMMANDS_PER_GAME: dict[str, list[str]] = {g.name: list(g.controls) for g in GAMES}

# ============================================================================
# Layout
# ============================================================================

COLS = 3
TILE_W, TILE_H = 210, 112
GAP_X, GAP_Y = 22, 14
GRID_X = (W - (COLS * TILE_W + (COLS - 1) * GAP_X)) // 2
GRID_Y = 98
INFO_RECT = pygame.Rect(GRID_X, GRID_Y + 3 * TILE_H + 2 * GAP_Y + 10,
                        COLS * TILE_W + (COLS - 1) * GAP_X, 98)
HORIZON_Y = 300

STATE_MAIN = "main"
STATE_CREDITS = "credits"
CREDITS_AREA = pygame.Rect(60, 90, W - 120, H - 150)


def tile_rects() -> list[pygame.Rect]:
    """Screen rectangles of the 3x3 game tiles."""
    return [pygame.Rect(GRID_X + (i % COLS) * (TILE_W + GAP_X),
                        GRID_Y + (i // COLS) * (TILE_H + GAP_Y), TILE_W, TILE_H)
            for i in range(len(GAMES))]


# ============================================================================
# Background: gradient sky, stars and a scrolling synthwave grid
# ============================================================================

class SynthwaveBackground:
    """Animated backdrop inspired by the README banner."""

    def __init__(self, seed: int = 7) -> None:
        rng = random.Random(seed)
        self.sky = pygame.Surface((W, H))
        top, mid, bottom = (6, 4, 20), (46, 10, 66), (12, 4, 26)
        for y in range(H):
            if y < HORIZON_Y:
                c = gs.lerp_color(top, mid, (y / HORIZON_Y) ** 1.6)
            else:
                c = gs.lerp_color(mid, bottom, ((y - HORIZON_Y) / (H - HORIZON_Y)) ** 0.6)
            self.sky.fill(c, (0, y, W, 1))
        pygame.draw.line(self.sky, (255, 80, 200), (0, HORIZON_Y), (W, HORIZON_Y), 2)
        self.stars = [(rng.randrange(W), rng.randrange(HORIZON_Y - 10), rng.uniform(0, math.tau),
                       rng.choice((1, 1, 1, 2))) for _ in range(90)]
        self.scroll = 0.0

    def update(self, dt: float) -> None:
        self.scroll = (self.scroll + dt * 0.35) % 1.0

    def draw(self, surf: pygame.Surface, t: float) -> None:
        surf.blit(self.sky, (0, 0))
        for x, y, phase, size in self.stars:
            b = int(120 + 120 * (0.5 + 0.5 * math.sin(t * 2.2 + phase)))
            surf.fill((b, b, min(255, b + 30)), (x, y, size, size))
        grid = (150, 40, 170)
        # Horizontal lines: perspective spacing, scrolling towards the viewer.
        depth = H - HORIZON_Y
        for i in range(14):
            z = (i + self.scroll) / 14
            y = HORIZON_Y + int(depth * z * z)
            pygame.draw.line(surf, grid, (0, y), (W, y), 1)
        # Vertical lines converging to the vanishing point.
        vx = W // 2
        for i in range(-12, 13):
            pygame.draw.line(surf, grid, (vx + i * 18, HORIZON_Y), (vx + i * 130, H), 1)


# ============================================================================
# Tile thumbnails (t = animation time; only the selected tile animates)
# ============================================================================

def _thumb_tris(s: pygame.Surface, r: pygame.Rect, t: float) -> None:
    cw, ch = r.w // 3, r.h // 3
    for i in (1, 2):
        pygame.draw.line(s, (60, 110, 200), (r.x + i * cw, r.y + 4), (r.x + i * cw, r.bottom - 4), 2)
        pygame.draw.line(s, (60, 110, 200), (r.x + 6, r.y + i * ch), (r.right - 6, r.y + i * ch), 2)
    marks = [(0, 0, "X"), (1, 1, "O"), (2, 0, "X"), (0, 2, "O"), (2, 2, "X")]
    shown = len(marks) if t == 0 else int(t * 2) % (len(marks) + 3)
    for col, row, m in marks[:shown]:
        c = pygame.Rect(r.x + col * cw, r.y + row * ch, cw, ch).inflate(-cw // 2, -8)
        if m == "X":
            pygame.draw.line(s, gs.NEON_RED, c.topleft, c.bottomright, 3)
            pygame.draw.line(s, gs.NEON_RED, c.topright, c.bottomleft, 3)
        else:
            pygame.draw.circle(s, gs.NEON_BLUE, c.center, min(c.w, c.h) // 2, 3)


def _thumb_snake(s: pygame.Surface, r: pygame.Rect, t: float) -> None:
    seg = 10
    cols = r.w // seg
    head = int(t * 8) % cols if t else cols // 2
    y = r.centery
    for i in range(7):
        x = r.x + ((head - i) % cols) * seg
        color = gs.lerp_color((120, 255, 120), (20, 110, 40), i / 7)
        pygame.draw.rect(s, color, (x, y - seg // 2, seg - 1, seg - 1), border_radius=3)
    pygame.draw.circle(s, gs.NEON_RED, (r.right - 26, r.y + 14), 5)
    pygame.draw.circle(s, gs.NEON_BLUE, (r.x + 24, r.bottom - 12), 4)


def _thumb_tetris(s: pygame.Surface, r: pygame.Rect, t: float) -> None:
    c = 10
    stack = [(0, 5, gs.NEON_RED), (1, 5, gs.NEON_RED), (2, 5, gs.NEON_YELLOW), (3, 5, gs.NEON_YELLOW),
             (5, 5, gs.NEON_GREEN), (6, 5, gs.NEON_GREEN), (7, 5, gs.NEON_BLUE), (8, 5, gs.NEON_BLUE),
             (0, 4, gs.NEON_PURPLE), (1, 4, gs.NEON_PURPLE), (6, 4, gs.NEON_ORANGE), (7, 4, gs.NEON_ORANGE)]
    ox = r.centerx - 5 * c
    oy = r.bottom - 6 * c - 2
    for x, y, col in stack:
        pygame.draw.rect(s, col, (ox + x * c, oy + y * c, c - 1, c - 1))
    fall = (int(t * 4) % 6) if t else 2
    for x, y in ((4, 0), (4, 1), (4, 2), (4, 3)):
        pygame.draw.rect(s, gs.NEON_CYAN, (ox + x * c, oy + (y + fall - 4) * c, c - 1, c - 1))


def _thumb_pong(s: pygame.Surface, r: pygame.Rect, t: float) -> None:
    for y in range(r.y + 4, r.bottom - 4, 10):
        pygame.draw.rect(s, (90, 90, 130), (r.centerx - 1, y, 2, 5))
    if t:
        bx = r.centerx + int(math.sin(t * 2.5) * (r.w // 2 - 22))
        by = r.centery + int(math.sin(t * 3.7) * (r.h // 2 - 8))
    else:
        bx, by = r.centerx + 30, r.centery - 10
    left_y = max(r.y + 12, min(r.bottom - 12, by if bx < r.centerx else r.centery))
    right_y = max(r.y + 12, min(r.bottom - 12, by if bx >= r.centerx else r.centery))
    pygame.draw.rect(s, gs.WHITE, (r.x + 8, left_y - 12, 4, 24))
    pygame.draw.rect(s, gs.WHITE, (r.right - 12, right_y - 12, 4, 24))
    pygame.draw.circle(s, gs.WHITE, (bx, by), 4)


def _thumb_breakout(s: pygame.Surface, r: pygame.Rect, t: float) -> None:
    colors = (gs.NEON_RED, gs.NEON_ORANGE, gs.NEON_YELLOW, gs.NEON_GREEN)
    bw = (r.w - 8) // 8
    for row, col in enumerate(colors):
        for i in range(8):
            if t and (i + row * 3 + int(t * 3)) % 11 == 0:
                continue
            pygame.draw.rect(s, col, (r.x + 4 + i * bw, r.y + 4 + row * 8, bw - 2, 6))
    px = r.centerx + (int(math.sin(t * 2) * 50) if t else 0)
    pygame.draw.rect(s, TEXT, (px - 18, r.bottom - 8, 36, 5), border_radius=2)
    bounce = int(abs(math.sin(t * 4)) * 14) if t else 0
    pygame.draw.circle(s, gs.WHITE, (px + 10, r.bottom - 22 - bounce), 3)


_ALIEN = ("..#.....#..", "...#...#...", "..#######..", ".##.###.##.",
          "###########", "#.#######.#", "#.#.....#.#", "...##.##...")


def _thumb_invaders(s: pygame.Surface, r: pygame.Rect, t: float) -> None:
    sway = int(math.sin(t * 2) * 12) if t else 0
    for k in range(3):
        ox = r.x + 26 + k * 52 + sway
        oy = r.y + 8
        for y, row in enumerate(_ALIEN):
            for x, ch in enumerate(row):
                if ch == "#":
                    s.fill(gs.NEON_GREEN if k != 1 else gs.NEON_MAGENTA, (ox + x * 3, oy + y * 3, 3, 3))
    sx = r.centerx + (int(math.sin(t * 1.3) * 60) if t else 0)
    ship = [(sx, r.bottom - 16), (sx - 9, r.bottom - 4), (sx + 9, r.bottom - 4)]
    pygame.draw.polygon(s, gs.NEON_CYAN, ship)
    if t:
        by = r.bottom - 20 - int((t * 120) % 40)
        pygame.draw.rect(s, gs.NEON_YELLOW, (sx - 1, by, 2, 6))


def _thumb_maze(s: pygame.Surface, r: pygame.Rect, t: float) -> None:
    wall = (40, 110, 230)
    c = 9
    maze = ("#############", "#...#.......#", "#.#.#.#####.#", "#.#...#...#.#",
            "#.#####.#.#.#", "#.......#..E#", "#############")
    ox = r.centerx - len(maze[0]) * c // 2
    oy = r.centery - len(maze) * c // 2
    path = [(1, 1), (1, 2), (1, 3), (1, 4), (1, 5), (2, 5), (3, 5), (4, 5), (5, 5), (6, 5), (7, 5),
            (7, 4), (7, 3), (8, 3), (9, 3), (9, 4), (9, 5), (10, 5)]
    for y, row in enumerate(maze):
        for x, ch in enumerate(row):
            if ch == "#":
                s.fill(wall, (ox + x * c, oy + y * c, c - 1, c - 1))
            elif ch == "E":
                s.fill(gs.NEON_GREEN, (ox + x * c + 1, oy + y * c + 1, c - 3, c - 3))
    step = int(t * 6) % len(path) if t else 0
    for px, py in path[:step]:
        s.fill((70, 70, 120), (ox + px * c + 3, oy + py * c + 3, c - 7, c - 7))
    px, py = path[step]
    s.fill(gs.NEON_YELLOW, (ox + px * c + 1, oy + py * c + 1, c - 3, c - 3))


def _thumb_memory(s: pygame.Surface, r: pygame.Rect, t: float) -> None:
    colors = (gs.NEON_RED, gs.NEON_BLUE, gs.NEON_GREEN, gs.NEON_YELLOW)
    size = 26
    gap = 8
    ox = r.centerx - (4 * size + 3 * gap) // 2
    for row in range(2):
        for i in range(4):
            x = ox + i * (size + gap)
            y = r.centery - size - gap // 2 + row * (size + gap)
            flip = abs(math.cos(t * 2 + i + row * 2)) if t else 1.0
            w = max(2, int(size * flip))
            rect = pygame.Rect(x + (size - w) // 2, y, w, size)
            face_up = (i + row) % 2 == 0 if not t else math.cos(t * 2 + i + row * 2) > 0
            if face_up:
                pygame.draw.rect(s, (230, 230, 240), rect, border_radius=3)
                pygame.draw.circle(s, colors[(i + row) % 4], rect.center, max(1, w // 4))
            else:
                pygame.draw.rect(s, (90, 50, 150), rect, border_radius=3)
                pygame.draw.rect(s, gs.NEON_MAGENTA, rect, 1, border_radius=3)


def _thumb_puzzle(s: pygame.Surface, r: pygame.Rect, t: float) -> None:
    font = gs.safe_font(10, bold=True)
    tile = 15
    gap = 2
    ox = r.centerx - (4 * tile + 3 * gap) // 2
    oy = r.centery - (4 * tile + 3 * gap) // 2
    slide = (math.sin(t * 2) * 0.5 + 0.5) if t else 0.0
    for n in range(15):
        row, col = divmod(n, 4)
        x = ox + col * (tile + gap)
        y = oy + row * (tile + gap)
        if n == 14:
            x += int(slide * (tile + gap))
        pygame.draw.rect(s, (70, 70, 110), (x, y, tile, tile), border_radius=2)
        txt = font.render(str(n + 1), True, gs.NEON_YELLOW)
        s.blit(txt, txt.get_rect(center=(x + tile // 2, y + tile // 2)))


THUMB_DRAWERS: tuple[Callable[[pygame.Surface, pygame.Rect, float], None], ...] = (
    _thumb_tris, _thumb_snake, _thumb_tetris,
    _thumb_pong, _thumb_breakout, _thumb_invaders,
    _thumb_maze, _thumb_memory, _thumb_puzzle,
)

# ============================================================================
# Launcher
# ============================================================================

CREDITS: tuple[tuple[str, str], ...] = (
    ("h", "RETRO ARCADE COLLECTION"),
    ("t", f"Versione {VERSION}"),
    ("s", ""),
    ("h", "IDEATO E SVILUPPATO DA"),
    ("t", "Sir Alfry  (Alfredo De Donno)"),
    ("s", ""),
    ("h", "TECNOLOGIE"),
    ("t", "Python 3.10+  ·  Pygame-CE"),
    ("t", "Effetti sonori sintetizzati in tempo reale (zero file audio)"),
    ("t", "Font bitmap 5x7 disegnato a mano"),
    ("t", "AI Minimax / Alpha-Beta con iterative deepening"),
    ("s", ""),
    ("h", "I GIOCHI"),
    *(("t", g.name) for g in GAMES),
    ("s", ""),
    ("h", "SEGUIMI"),
    ("t", "Instagram: instagram.com/sir_alfry"),
    ("t", "ArtStation: artstation.com/siralfry"),
    ("t", "GitHub: github.com/sirAlfry"),
    ("s", ""),
    ("h", "GRAZIE PER AVER GIOCATO!"),
    ("s", ""), ("s", ""),
)


class Launcher:
    """The main menu: owns the window, the score store and the game loop."""

    def __init__(self, screen: pygame.Surface, store: ScoreStore) -> None:
        self.screen = screen
        self.store = store
        self.clock = gs.GameClock(60)
        self.background = SynthwaveBackground()
        self.rects = tile_rects()
        self.state = STATE_MAIN
        self.time = 0.0
        self.credits_scroll = 0.0
        self.fade = 1.0  # 1 = black, fades in to 0
        try:
            self.selected = int(store.get_setting("last_game", 0)) % len(GAMES)
        except (TypeError, ValueError):
            self.selected = 0
        self.records: dict = {}
        self.refresh_records()
        self.desc_font = gs.safe_font(15)
        self.small_font = gs.safe_font(13)

    # ------------------------------------------------------------- helpers
    def refresh_records(self) -> None:
        try:
            self.records = self.store.load_scores()
        except Exception:
            self.records = {}

    def move_selection(self, delta_col: int, delta_row: int) -> None:
        col = (self.selected % COLS + delta_col) % COLS
        row = (self.selected // COLS + delta_row) % (len(GAMES) // COLS)
        self.selected = row * COLS + col
        sfx.play("move")

    # -------------------------------------------------------------- launch
    def launch(self, index: int) -> str | None:
        """Fade out, run the game, come back. Returns ``"quit"`` if requested."""
        info = GAMES[index]
        self.selected = index
        self.store.set_setting("last_game", index)
        sfx.play("launch")
        for i in range(12):  # quick fade to black
            self.draw()
            shade = pygame.Surface((W, H))
            shade.set_alpha(int(255 * (i + 1) / 12))
            self.screen.blit(shade, (0, 0))
            gs.present(self.screen)
            self.clock.tick()
        result = launch_game(info.name, self.store.load_scores, self.store.save_scores)
        if result == "quit":
            return "quit"
        self.screen = gs.setup_screen(f"{TITLE} - {SUBTITLE}")
        self.refresh_records()
        self.fade = 1.0
        self.clock.reset()
        if isinstance(result, Exception):
            gs.message_box(self.screen, "OPS!", [
                f"{info.name} si è interrotto per un errore:",
                f"{type(result).__name__}: {str(result)[:58]}",
                "I dettagli sono nel file retro_arcade.log",
            ])
            self.clock.reset()
        return None

    # --------------------------------------------------------------- input
    def handle_event(self, event: pygame.event.Event) -> str | None:
        if gs.handle_global_event(event):
            return None
        if event.type == pygame.QUIT:
            return "quit"
        if self.state == STATE_CREDITS:
            if event.type == pygame.KEYDOWN and event.key in (
                pygame.K_ESCAPE, pygame.K_b, pygame.K_c, pygame.K_RETURN, pygame.K_SPACE
            ):
                sfx.play("back")
                self.state = STATE_MAIN
            elif event.type == pygame.MOUSEBUTTONDOWN:
                self.state = STATE_MAIN
            return None

        if event.type == pygame.KEYDOWN:
            key = event.key
            if key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                return self.launch(self.selected)
            if key in (pygame.K_RIGHT, pygame.K_d):
                self.move_selection(1, 0)
            elif key in (pygame.K_LEFT, pygame.K_a):
                self.move_selection(-1, 0)
            elif key in (pygame.K_DOWN, pygame.K_s):
                self.move_selection(0, 1)
            elif key in (pygame.K_UP, pygame.K_w):
                self.move_selection(0, -1)
            elif key == pygame.K_c:
                sfx.play("select")
                self.state = STATE_CREDITS
                self.credits_scroll = CREDITS_AREA.h - 24  # first lines visible at once
            elif key == pygame.K_m:
                gs.toggle_sound()
            elif key == pygame.K_v:
                gs.toggle_crt()
            elif key in (pygame.K_ESCAPE, pygame.K_q):
                return "quit"
            elif pygame.K_1 <= key <= pygame.K_9:
                index = key - pygame.K_1
                if index < len(GAMES):
                    return self.launch(index)
        elif event.type == pygame.MOUSEMOTION:
            for i, r in enumerate(self.rects):
                if r.collidepoint(event.pos) and i != self.selected:
                    self.selected = i
                    sfx.play("move", 0.4)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, r in enumerate(self.rects):
                if r.collidepoint(event.pos):
                    return self.launch(i)
        return None

    # ---------------------------------------------------------------- draw
    def draw_tile(self, i: int, rect: pygame.Rect, selected: bool) -> None:
        info = GAMES[i]
        s = self.screen
        pulse = 0.5 + 0.5 * math.sin(self.time * 4)
        if selected:
            glow = pygame.Surface((rect.w + 36, rect.h + 36), pygame.SRCALPHA)
            for k in range(6):
                alpha = int((14 + 14 * pulse) * (1 - k / 6))
                pygame.draw.rect(glow, (*gs.NEON_MAGENTA, alpha), glow.get_rect().inflate(-k * 6, -k * 6),
                                 border_radius=22)
            s.blit(glow, (rect.x - 18, rect.y - 18))
        body = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(body, (12, 8, 30, 235), body.get_rect(), border_radius=12)
        s.blit(body, rect)
        thumb = pygame.Rect(rect.x + 10, rect.y + 10, rect.w - 20, rect.h - 40)
        pygame.draw.rect(s, (4, 2, 12), thumb, border_radius=6)
        clip = s.get_clip()
        s.set_clip(thumb)
        THUMB_DRAWERS[i](s, thumb, self.time if selected else 0.0)
        s.set_clip(clip)
        border = gs.NEON_CYAN if selected else (70, 45, 120)
        pygame.draw.rect(s, border, rect, 3 if selected else 2, border_radius=12)
        label_color = gs.WHITE if selected else TEXT_DIM
        blit_pixel_text(s, info.name.upper(), (rect.x + 12, rect.bottom - 17), 2, label_color, "midleft")
        if info.record(self.records):
            blit_pixel_text(s, "★", (rect.right - 12, rect.bottom - 17), 2, gs.NEON_YELLOW, "midright")
        blit_pixel_text(s, str(i + 1), (rect.right - 8, rect.y + 6), 1, (110, 90, 160), "topright")

    def draw_info_panel(self) -> None:
        info = GAMES[self.selected]
        s = self.screen
        gs.draw_panel(s, INFO_RECT, info.accent, fill_alpha=215, radius=10)
        x = INFO_RECT.x + 16
        blit_pixel_text(s, info.name.upper(), (x, INFO_RECT.y + 12), 3, info.accent)
        record = info.record(self.records) or "NESSUN RECORD... ANCORA!"
        blit_pixel_text(s, record, (INFO_RECT.right - 16, INFO_RECT.y + 16), 2, gs.NEON_YELLOW, "topright")
        gs.draw_text(s, info.description, self.desc_font, TEXT, (x, INFO_RECT.y + 38))
        for k, line in enumerate(info.controls):
            gs.draw_text(s, line, self.small_font, TEXT_DIM, (x, INFO_RECT.y + 59 + k * 16))

    def draw_main(self) -> None:
        s = self.screen
        self.background.draw(s, self.time)
        gs.pixel_title(s, "RETRO ARCADE", (W // 2, 34), 4, gs.NEON_CYAN)
        gs.pixel_title(s, "COLLECTION", (W // 2, 72), 3, gs.NEON_MAGENTA)
        for i, rect in enumerate(self.rects):
            if i != self.selected:
                self.draw_tile(i, rect, False)
        self.draw_tile(self.selected, self.rects[self.selected], True)
        self.draw_info_panel()
        footer = ("↑↓←→ SCEGLI · INVIO GIOCA · C CREDITI · M AUDIO "
                  f"{'ON' if gs.sound_enabled() else 'OFF'} · V CRT · F11 SCHERMO INTERO · ESC ESCI")
        blit_pixel_text(s, footer, (W // 2, H - 14), 1, TEXT_DIM, "center")
        fps = self.clock.get_fps()
        blit_pixel_text(s, f"{fps:2.0f} FPS", (W - 10, 8), 1, (110, 200, 120), "topright")
        blit_pixel_text(s, f"V{VERSION}", (10, 8), 1, (110, 90, 160))

    def draw_credits(self) -> None:
        s = self.screen
        self.background.draw(s, self.time)
        gs.pixel_title(s, "CREDITI", (W // 2, 44), 5, gs.NEON_YELLOW)
        area = CREDITS_AREA
        gs.draw_panel(s, area, gs.NEON_PURPLE, fill_alpha=200)
        clip = s.get_clip()
        s.set_clip(area.inflate(-8, -8))
        line_h = 30
        total = len(CREDITS) * line_h
        start = area.bottom - (self.credits_scroll % (total + area.h))
        font = gs.safe_font(17)
        for k, (kind, text) in enumerate(CREDITS):
            y = int(start + k * line_h)
            if y < area.top - line_h or y > area.bottom:
                continue
            if kind == "h":
                blit_pixel_text(s, text, (W // 2, y), 3, gs.NEON_CYAN, "midtop")
            elif kind == "t":
                gs.draw_text(s, text, font, TEXT, (W // 2, y + 2), "midtop")
        s.set_clip(clip)
        blit_pixel_text(s, "ESC / B / C: TORNA AL MENU", (W // 2, H - 30), 2, TEXT_DIM, "center")

    def draw(self) -> None:
        if self.state == STATE_CREDITS:
            self.draw_credits()
        else:
            self.draw_main()

    # ---------------------------------------------------------------- loop
    def run(self) -> None:
        while True:
            dt = self.clock.tick()
            self.time += dt
            self.background.update(dt)
            if self.state == STATE_CREDITS:
                self.credits_scroll += dt * 45
            for event in pygame.event.get():
                if self.handle_event(event) == "quit":
                    return
            self.draw()
            if self.fade > 0:
                shade = pygame.Surface((W, H))
                shade.fill(BG_DARK)
                shade.set_alpha(int(255 * self.fade))
                self.screen.blit(shade, (0, 0))
                self.fade = max(0.0, self.fade - dt * 4)
            gs.present(self.screen)


# ============================================================================
# Game launching
# ============================================================================

def find_game(query: str) -> GameInfo | None:
    """Find a game by display name or module name (case-insensitive)."""
    q = query.strip().lower().replace("_", " ")
    for g in GAMES:
        if q in (g.name.lower(), g.module.lower().replace("_", " ")):
            return g
    return None


def launch_game(
    game_name: str,
    scores_getter: Callable[[], dict],
    scores_setter: Callable[[dict], None],
) -> str | Exception | None:
    """
    Import a game module on demand and run it (dispatch pattern).

    Args:
        game_name: Display name (``"Snake"``) or module name (``"snake"``).
        scores_getter / scores_setter: Persistence callables passed to the game.

    Returns:
        ``"quit"`` if the player asked to close the app, ``None`` when the game
        returned to the menu, or the ``Exception`` if the game crashed.
    """
    info = find_game(game_name)
    if info is None:
        log.error("Unknown game: %s", game_name)
        return None
    try:
        module = importlib.import_module(info.module)
        entry = getattr(module, info.func)
        result = entry(scores_getter, scores_setter)
        return "quit" if result == "quit" else None
    except Exception as exc:  # a broken game must not take the launcher down
        log.exception("Error while running %s", info.name)
        return exc


def _configure_logging() -> None:
    from scores import default_path
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    try:
        handlers.append(logging.FileHandler(default_path().parent / "retro_arcade.log",
                                            encoding="utf-8", delay=True))
    except OSError:
        pass
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=handlers)


def render_preview(path: str) -> str:
    """Render one launcher frame to ``path`` without opening a window."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    screen = gs.setup_screen(TITLE)
    launcher = Launcher(screen, ScoreStore())
    launcher.fade = 0.0
    launcher.time = 1.3
    launcher.draw()
    if gs.crt_enabled():
        screen.blit(gs.build_crt_overlay(), (0, 0))
    pygame.image.save(screen, path)
    return path


def main(argv: list[str] | None = None) -> None:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description=f"{TITLE} v{VERSION}")
    parser.add_argument("--game", help="avvia direttamente un gioco (es. snake, tetris)")
    parser.add_argument("--save", "--headless", nargs="?", const="retro_arcade_generated.png",
                        metavar="PNG", help="salva un'immagine del menu senza aprire finestre")
    args = parser.parse_args(argv)

    if args.save:
        print("Saved", render_preview(args.save))
        gs.shutdown()
        return

    _configure_logging()
    store = ScoreStore()
    screen = gs.setup_screen(f"{TITLE} - {SUBTITLE}")
    sfx.preload()

    try:
        if args.game:
            info = find_game(args.game)
            if info is None:
                names = ", ".join(g.module for g in GAMES)
                parser.error(f"gioco sconosciuto '{args.game}'. Disponibili: {names}")
            result = launch_game(info.name, store.load_scores, store.save_scores)
            if result == "quit" or isinstance(result, Exception):
                return
            screen = gs.setup_screen(f"{TITLE} - {SUBTITLE}")
        Launcher(screen, store).run()
    finally:
        gs.shutdown()


if __name__ == "__main__":
    main()
    sys.exit(0)
