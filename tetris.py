# tetris.py
"""
Tetris - modern-guideline flavour, in two layers:

* ``TetrisLogic``: pure game rules, no pygame (unit-tested in ``tests/``).
    - 7-bag randomizer (no more 5 S-pieces in a row)
    - SRS rotation system with official wall-kick tables
    - lock delay (0.5 s) with move-reset, like modern Tetris
    - hold piece, ghost piece, 3-piece preview queue
    - guideline scoring (100/300/500/800 x level, soft/hard drop points)
    - guideline gravity curve, a new level every 10 lines
* ``main()``: rendering, input (DAS/ARR auto-shift), sounds and effects.
"""
from __future__ import annotations

import random
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field

import pygame

import game_shared as gs
import sfx
from pixel_font import blit_pixel_text
from scores import get_best, record_best

W, H = gs.W, gs.H
COLUMNS = 10
ROWS = 20
CELL = 26
BOARD_W = COLUMNS * CELL
BOARD_H = ROWS * CELL
OFF_X = (W - BOARD_W) // 2
OFF_Y = 46

LOCK_DELAY = 0.5        # seconds a grounded piece waits before locking
MAX_LOCK_RESETS = 15    # moves/rotations that may postpone the lock
CLEAR_ANIM_TIME = 0.32  # duration of the line-clear animation
DAS = 0.16              # delayed auto shift (hold left/right)
ARR = 0.045             # auto repeat rate once DAS has elapsed
PREVIEW_COUNT = 3

COMMANDS = [
    "←/→ muovi   ↓ soft drop   SPAZIO hard drop",
    "↑ o X ruota   Z ruota indietro   C/SHIFT hold",
]

# Spawn orientation of every tetromino (SRS bounding boxes).
SHAPES: dict[str, list[list[int]]] = {
    "I": [[0, 0, 0, 0], [1, 1, 1, 1], [0, 0, 0, 0], [0, 0, 0, 0]],
    "J": [[1, 0, 0], [1, 1, 1], [0, 0, 0]],
    "L": [[0, 0, 1], [1, 1, 1], [0, 0, 0]],
    "O": [[1, 1], [1, 1]],
    "S": [[0, 1, 1], [1, 1, 0], [0, 0, 0]],
    "T": [[0, 1, 0], [1, 1, 1], [0, 0, 0]],
    "Z": [[1, 1, 0], [0, 1, 1], [0, 0, 0]],
}

COLORS: dict[str, tuple[int, int, int]] = {
    "I": (0, 230, 255), "J": (60, 110, 255), "L": (255, 150, 30), "O": (255, 225, 40),
    "S": (60, 230, 90), "T": (180, 70, 255), "Z": (255, 60, 80),
}

# SRS wall kicks, (dx, dy) with y pointing UP as in the official tables.
_KICKS_JLSTZ: dict[tuple[int, int], list[tuple[int, int]]] = {
    (0, 1): [(0, 0), (-1, 0), (-1, 1), (0, -2), (-1, -2)],
    (1, 0): [(0, 0), (1, 0), (1, -1), (0, 2), (1, 2)],
    (1, 2): [(0, 0), (1, 0), (1, -1), (0, 2), (1, 2)],
    (2, 1): [(0, 0), (-1, 0), (-1, 1), (0, -2), (-1, -2)],
    (2, 3): [(0, 0), (1, 0), (1, 1), (0, -2), (1, -2)],
    (3, 2): [(0, 0), (-1, 0), (-1, -1), (0, 2), (-1, 2)],
    (3, 0): [(0, 0), (-1, 0), (-1, -1), (0, 2), (-1, 2)],
    (0, 3): [(0, 0), (1, 0), (1, 1), (0, -2), (1, -2)],
}
_KICKS_I: dict[tuple[int, int], list[tuple[int, int]]] = {
    (0, 1): [(0, 0), (-2, 0), (1, 0), (-2, -1), (1, 2)],
    (1, 0): [(0, 0), (2, 0), (-1, 0), (2, 1), (-1, -2)],
    (1, 2): [(0, 0), (-1, 0), (2, 0), (-1, 2), (2, -1)],
    (2, 1): [(0, 0), (1, 0), (-2, 0), (1, -2), (-2, 1)],
    (2, 3): [(0, 0), (2, 0), (-1, 0), (2, 1), (-1, -2)],
    (3, 2): [(0, 0), (-2, 0), (1, 0), (-2, -1), (1, 2)],
    (3, 0): [(0, 0), (1, 0), (-2, 0), (1, -2), (-2, 1)],
    (0, 3): [(0, 0), (-1, 0), (2, 0), (-1, 2), (2, -1)],
}

LINE_SCORES = (0, 100, 300, 500, 800)
LINE_NAMES = ("", "SINGLE", "DOUBLE", "TRIPLE", "TETRIS!")


def rotate(shape: list[list[int]]) -> list[list[int]]:
    """Rotate a matrix 90 degrees clockwise."""
    return [list(row) for row in zip(*shape[::-1], strict=True)]


def rotated(kind: str, rotation: int) -> list[list[int]]:
    """Matrix of ``kind`` after ``rotation`` clockwise quarter turns."""
    m = SHAPES[kind]
    if kind == "O":
        return m
    for _ in range(rotation % 4):
        m = rotate(m)
    return m


def gravity_interval(level: int) -> float:
    """Seconds per row at ``level`` (Tetris guideline curve)."""
    level = max(1, level)
    return max(0.02, (0.8 - (level - 1) * 0.007) ** (level - 1))


@dataclass
class Piece:
    kind: str
    x: int
    y: int
    rotation: int = 0

    @property
    def matrix(self) -> list[list[int]]:
        return rotated(self.kind, self.rotation)

    def cells(self) -> list[tuple[int, int]]:
        """Board coordinates ``(x, y)`` of the four minos."""
        return [(self.x + c, self.y + r)
                for r, row in enumerate(self.matrix) for c, v in enumerate(row) if v]


@dataclass
class TetrisLogic:
    """All the rules of the game; drive it with the methods and ``update(dt)``."""

    rng: random.Random = field(default_factory=random.Random)
    cols: int = COLUMNS
    rows: int = ROWS

    def __post_init__(self) -> None:
        self.board: list[list[str | None]] = [[None] * self.cols for _ in range(self.rows)]
        self.bag: list[str] = []
        self.queue: deque[str] = deque()
        self.piece: Piece | None = None
        self.hold: str | None = None
        self.can_hold = True
        self.score = 0
        self.lines = 0
        self.level = 1
        self.game_over = False
        self.gravity_timer = 0.0
        self.lock_timer = 0.0
        self.lock_resets = 0
        self.lowest_y = -99
        self.clearing_rows: list[int] = []
        self.clear_timer = 0.0
        self.events: list[str] = []
        self._fill_queue()
        self.spawn()

    # ----------------------------------------------------------- pieces
    def _next_from_bag(self) -> str:
        if not self.bag:
            self.bag = list(SHAPES)
            self.rng.shuffle(self.bag)
        return self.bag.pop()

    def _fill_queue(self) -> None:
        while len(self.queue) < 5:
            self.queue.append(self._next_from_bag())

    def spawn(self, kind: str | None = None) -> bool:
        """Put a new piece at the top. Returns False (and ends the game) on block-out."""
        if kind is None:
            kind = self.queue.popleft()
            self._fill_queue()
        width = len(SHAPES[kind][0])
        x = (self.cols - width) // 2 if kind != "O" else self.cols // 2 - 1
        y = -1 if kind == "I" else 0
        self.piece = Piece(kind, x, y)
        self.gravity_timer = 0.0
        self.lock_timer = 0.0
        self.lock_resets = 0
        self.lowest_y = self.piece.y
        if self.collides(self.piece.matrix, x, y):
            self.game_over = True
            self.events.append("gameover")
            return False
        return True

    def collides(self, matrix: list[list[int]], x: int, y: int) -> bool:
        """True if ``matrix`` at ``(x, y)`` hits a wall, the floor or a block.

        Rows above the board (y < 0) count as empty, so pieces can rotate
        while partially above the visible field.
        """
        for r, row in enumerate(matrix):
            for c, v in enumerate(row):
                if not v:
                    continue
                bx, by = x + c, y + r
                if bx < 0 or bx >= self.cols or by >= self.rows:
                    return True
                if by >= 0 and self.board[by][bx] is not None:
                    return True
        return False

    @property
    def on_ground(self) -> bool:
        p = self.piece
        return p is not None and self.collides(p.matrix, p.x, p.y + 1)

    def _after_successful_move(self) -> None:
        if self.piece is None:
            return
        if self.piece.y > self.lowest_y:
            self.lowest_y = self.piece.y
            self.lock_resets = 0
        if self.lock_resets < MAX_LOCK_RESETS:
            self.lock_timer = 0.0
            self.lock_resets += 1

    # ---------------------------------------------------------- actions
    def move(self, dx: int) -> bool:
        p = self.piece
        if p is None or self.game_over or self.collides(p.matrix, p.x + dx, p.y):
            return False
        p.x += dx
        self._after_successful_move()
        self.events.append("move")
        return True

    def rotate(self, direction: int = 1) -> bool:
        """Rotate clockwise (``1``) or counter-clockwise (``-1``) using SRS kicks."""
        p = self.piece
        if p is None or self.game_over or p.kind == "O":
            return False
        new_rot = (p.rotation + direction) % 4
        matrix = rotated(p.kind, new_rot)
        table = _KICKS_I if p.kind == "I" else _KICKS_JLSTZ
        for dx, dy_up in table[(p.rotation, new_rot)]:
            nx, ny = p.x + dx, p.y - dy_up
            if not self.collides(matrix, nx, ny):
                p.x, p.y, p.rotation = nx, ny, new_rot
                self._after_successful_move()
                self.events.append("rotate")
                return True
        return False

    def soft_drop(self) -> bool:
        """Move down one row (+1 point)."""
        p = self.piece
        if p is None or self.game_over or self.collides(p.matrix, p.x, p.y + 1):
            return False
        p.y += 1
        self.score += 1
        self.gravity_timer = 0.0
        self._after_successful_move()
        return True

    def ghost_y(self) -> int:
        p = self.piece
        if p is None:
            return 0
        y = p.y
        while not self.collides(p.matrix, p.x, y + 1):
            y += 1
        return y

    def hard_drop(self) -> int:
        """Drop to the bottom and lock immediately (+2 points per row)."""
        p = self.piece
        if p is None or self.game_over:
            return 0
        distance = self.ghost_y() - p.y
        p.y += distance
        self.score += 2 * distance
        self.events.append("harddrop")
        self._lock()
        return distance

    def hold_piece(self) -> bool:
        """Swap the current piece with the hold slot (once per piece)."""
        if self.piece is None or not self.can_hold or self.game_over:
            return False
        current = self.piece.kind
        if self.hold is None:
            self.hold = current
            self.spawn()
        else:
            self.hold, swap = current, self.hold
            self.spawn(swap)
        self.can_hold = False
        self.events.append("hold")
        return True

    # ------------------------------------------------------------ rules
    def _lock(self) -> None:
        p = self.piece
        if p is None:
            return
        above_top = False
        for x, y in p.cells():
            if y < 0:
                above_top = True
            else:
                self.board[y][x] = p.kind
        self.piece = None
        self.can_hold = True
        self.events.append("lock")
        if above_top:  # lock-out: the piece stopped outside the field
            self.game_over = True
            self.events.append("gameover")
            return
        full = [y for y in range(self.rows) if all(self.board[y])]
        if full:
            self.clearing_rows = full
            self.clear_timer = CLEAR_ANIM_TIME
            n = len(full)
            self.score += LINE_SCORES[min(n, 4)] * self.level
            self.lines += n
            self.events.append(f"lines{n}")
            new_level = 1 + self.lines // 10
            if new_level > self.level:
                self.level = new_level
                self.events.append("levelup")
        else:
            self.spawn()

    def _finish_clear(self) -> None:
        keep = [row for y, row in enumerate(self.board) if y not in self.clearing_rows]
        empty = [[None] * self.cols for _ in self.clearing_rows]
        self.board = empty + keep
        self.clearing_rows = []
        self.spawn()

    def update(self, dt: float, soft_drop: bool = False) -> None:
        """Advance time: gravity, lock delay and line-clear animation."""
        if self.game_over:
            return
        if self.clearing_rows:
            self.clear_timer -= dt
            if self.clear_timer <= 0:
                self._finish_clear()
            return
        if self.piece is None:
            return
        interval = gravity_interval(self.level)
        if soft_drop:
            interval = min(interval, 0.035)
        self.gravity_timer += dt
        while self.gravity_timer >= interval and self.piece is not None:
            self.gravity_timer -= interval
            if self.on_ground:
                self.gravity_timer = 0.0
                break
            self.piece.y += 1
            if soft_drop:
                self.score += 1
            if self.piece.y > self.lowest_y:
                self.lowest_y = self.piece.y
                self.lock_resets = 0
                self.lock_timer = 0.0
        if self.piece is not None and self.on_ground:
            self.lock_timer += dt
            if self.lock_timer >= LOCK_DELAY:
                self._lock()
        else:
            self.lock_timer = 0.0

    def pop_events(self) -> list[str]:
        """Return and clear the events produced since the last call."""
        events, self.events = self.events, []
        return events


# ============================================================================
# Rendering helpers
# ============================================================================

_block_cache: dict[tuple, pygame.Surface] = {}


def block_surface(color: tuple[int, int, int], size: int) -> pygame.Surface:
    """A bevelled 'arcade' block, cached per color/size."""
    key = (color, size)
    surf = _block_cache.get(key)
    if surf is None:
        surf = pygame.Surface((size, size))
        light = gs.lerp_color(color, gs.WHITE, 0.45)
        dark = gs.lerp_color(color, gs.BLACK, 0.45)
        surf.fill(dark)
        pygame.draw.polygon(surf, light, [(0, 0), (size - 1, 0), (0, size - 1)])
        bevel = max(2, size // 7)
        pygame.draw.rect(surf, color, (bevel, bevel, size - 2 * bevel, size - 2 * bevel))
        hl = gs.lerp_color(color, gs.WHITE, 0.25)
        pygame.draw.line(surf, hl, (bevel, bevel), (size - bevel - 1, bevel))
        _block_cache[key] = surf
    return surf


def draw_mini_piece(screen: pygame.Surface, kind: str, center: tuple[int, int], size: int) -> None:
    """Draw a piece (spawn orientation) centered in a preview box."""
    cells = [(c, r) for r, row in enumerate(SHAPES[kind]) for c, v in enumerate(row) if v]
    min_x = min(c for c, _ in cells)
    max_x = max(c for c, _ in cells)
    min_y = min(r for _, r in cells)
    max_y = max(r for _, r in cells)
    w = (max_x - min_x + 1) * size
    h = (max_y - min_y + 1) * size
    ox = center[0] - w // 2
    oy = center[1] - h // 2
    block = block_surface(COLORS[kind], size)
    for c, r in cells:
        screen.blit(block, (ox + (c - min_x) * size, oy + (r - min_y) * size))


def _board_background() -> pygame.Surface:
    surf = pygame.Surface((BOARD_W, BOARD_H))
    surf.fill((8, 6, 20))
    for c in range(1, COLUMNS):
        pygame.draw.line(surf, (22, 18, 44), (c * CELL, 0), (c * CELL, BOARD_H))
    for r in range(1, ROWS):
        pygame.draw.line(surf, (22, 18, 44), (0, r * CELL), (BOARD_W, r * CELL))
    return surf


# ============================================================================
# Game loop
# ============================================================================

def main(load_scores: Callable[[], dict] | None = None,
         save_scores: Callable[[dict], None] | None = None) -> str:
    """
    Play Tetris.

    Args:
        load_scores / save_scores: Persistence callables (see ``scores.py``).

    Returns:
        ``"menu"`` to go back to the launcher, ``"quit"`` to close the app.
    """
    load_scores, save_scores = gs.ensure_scores(load_scores, save_scores)
    screen = gs.setup_screen("Tetris")
    clock = gs.GameClock(60)
    board_bg = _board_background()
    particles = gs.Particles()
    popups = gs.FloatingTexts()
    shake = gs.ScreenShake(6)
    label_font = gs.safe_font(15)

    def new_game() -> TetrisLogic:
        return TetrisLogic()

    game = new_game()
    best = get_best(load_scores, "tetris", 0) or 0
    held = {"left": 0.0, "right": 0.0}
    clear_snapshot: list[int] = []

    def board_xy(x: int, y: int) -> tuple[int, int]:
        return OFF_X + x * CELL, OFF_Y + y * CELL

    def handle_events() -> str | None:
        nonlocal game
        for e in pygame.event.get():
            if gs.handle_global_event(e):
                continue
            if e.type == pygame.QUIT:
                return "quit"
            if e.type != pygame.KEYDOWN:
                continue
            if e.key in (pygame.K_ESCAPE, pygame.K_p):
                choice = gs.in_game_menu(screen, "Tetris", COMMANDS)
                clock.reset()
                if choice in ("menu", "quit"):
                    return choice
                if choice == "restart":
                    game = new_game()
                    particles.clear()
                    popups.clear()
                continue
            if e.key in (pygame.K_LEFT, pygame.K_a):
                game.move(-1)
                held["left"] = DAS
                held["right"] = 0.0
            elif e.key in (pygame.K_RIGHT, pygame.K_d):
                game.move(1)
                held["right"] = DAS
                held["left"] = 0.0
            elif e.key in (pygame.K_UP, pygame.K_x, pygame.K_w):
                game.rotate(1)
            elif e.key in (pygame.K_z, pygame.K_LCTRL, pygame.K_RCTRL):
                game.rotate(-1)
            elif e.key == pygame.K_SPACE:
                game.hard_drop()
            elif e.key in (pygame.K_c, pygame.K_LSHIFT, pygame.K_RSHIFT):
                game.hold_piece()
        return None

    def auto_shift(dt: float) -> None:
        keys = pygame.key.get_pressed()
        for name, dx, codes in (("left", -1, (pygame.K_LEFT, pygame.K_a)),
                                ("right", 1, (pygame.K_RIGHT, pygame.K_d))):
            if any(keys[k] for k in codes):
                held[name] -= dt
                while held[name] <= 0:
                    if not game.move(dx):
                        held[name] = ARR
                        break
                    held[name] += ARR
            else:
                held[name] = 0.0

    def react(events: list[str]) -> None:
        nonlocal clear_snapshot
        for ev in events:
            if ev == "move":
                sfx.play("move", 0.35)
            elif ev == "rotate":
                sfx.play("rotate")
            elif ev == "hold":
                sfx.play("blip")
            elif ev == "harddrop":
                sfx.play("drop")
                shake.add(0.25)
            elif ev == "lock":
                sfx.play("drop", 0.5)
            elif ev.startswith("lines"):
                n = int(ev[5:])
                clear_snapshot = list(game.clearing_rows)
                sfx.play("tetris" if n >= 4 else "line")
                shake.add(0.15 * n)
                mid_y = OFF_Y + int(sum(clear_snapshot) / len(clear_snapshot) * CELL) + CELL // 2
                popups.add(LINE_NAMES[min(n, 4)], W // 2, mid_y,
                           gs.NEON_MAGENTA if n >= 4 else gs.NEON_YELLOW, 1.0, 3)
                for row in clear_snapshot:
                    for c in range(COLUMNS):
                        x, y = board_xy(c, row)
                        particles.burst(x + CELL // 2, y + CELL // 2,
                                        (gs.WHITE, gs.NEON_CYAN, gs.NEON_YELLOW), 3,
                                        speed=(40, 200), life=(0.3, 0.7), gravity=300)
            elif ev == "levelup":
                sfx.play("levelup")
                popups.add(f"LIVELLO {game.level}", W // 2, OFF_Y + BOARD_H // 3,
                           gs.NEON_GREEN, 1.4, 3)

    def draw() -> None:
        screen.fill(gs.BG)
        # --- board
        pygame.draw.rect(screen, gs.NEON_PURPLE, (OFF_X - 6, OFF_Y - 6, BOARD_W + 12, BOARD_H + 12),
                         3, border_radius=6)
        screen.blit(board_bg, (OFF_X, OFF_Y))
        for y in range(ROWS):
            for x in range(COLUMNS):
                kind = game.board[y][x]
                if kind:
                    screen.blit(block_surface(COLORS[kind], CELL), board_xy(x, y))
        # --- line clear animation: rows flash then shrink to the center
        if game.clearing_rows:
            progress = 1.0 - max(0.0, game.clear_timer) / CLEAR_ANIM_TIME
            for row in game.clearing_rows:
                x, y = board_xy(0, row)
                width = int(BOARD_W * (1.0 - progress))
                flash = gs.WHITE if int(progress * 8) % 2 == 0 else gs.NEON_CYAN
                pygame.draw.rect(screen, (8, 6, 20), (x, y, BOARD_W, CELL))
                pygame.draw.rect(screen, flash, (x + (BOARD_W - width) // 2, y + 2, width, CELL - 4))
        # --- ghost and active piece
        p = game.piece
        if p is not None and not game.game_over:
            gy = game.ghost_y()
            color = COLORS[p.kind]
            for cx, cy in Piece(p.kind, p.x, gy, p.rotation).cells():
                if cy >= 0:
                    x, y = board_xy(cx, cy)
                    ghost = pygame.Surface((CELL, CELL), pygame.SRCALPHA)
                    ghost.fill((*color, 45))
                    pygame.draw.rect(ghost, (*color, 200), ghost.get_rect(), 2)
                    screen.blit(ghost, (x, y))
            block = block_surface(color, CELL)
            flash_lock = game.on_ground and int(game.lock_timer * 20) % 2 == 1
            for cx, cy in p.cells():
                if cy >= 0:
                    screen.blit(block, board_xy(cx, cy))
                    if flash_lock:
                        pygame.draw.rect(screen, gs.WHITE, (*board_xy(cx, cy), CELL, CELL), 1)
        # --- left panel: stats + hold
        lx = OFF_X - 230
        stats = [("PUNTEGGIO", f"{game.score}"), ("RECORD", f"{max(best, game.score)}"),
                 ("LIVELLO", f"{game.level}"), ("LINEE", f"{game.lines}")]
        for i, (label, value) in enumerate(stats):
            y = OFF_Y + i * 62
            blit_pixel_text(screen, label, (lx, y), 2, gs.TEXT_DIM)
            blit_pixel_text(screen, value, (lx, y + 22), 3, gs.NEON_CYAN if i != 1 else gs.NEON_YELLOW)
        hold_box = pygame.Rect(lx, OFF_Y + 270, 180, 110)
        gs.draw_panel(screen, hold_box, gs.NEON_MAGENTA if game.can_hold else gs.GRAY_DARK,
                      fill_alpha=200, radius=8)
        blit_pixel_text(screen, "HOLD (C)", (hold_box.centerx, hold_box.y + 10), 2, gs.TEXT_DIM, "midtop")
        if game.hold:
            draw_mini_piece(screen, game.hold, (hold_box.centerx, hold_box.centery + 12), 20)
        # --- right panel: next queue
        rx = OFF_X + BOARD_W + 30
        next_box = pygame.Rect(rx, OFF_Y, 180, 300)
        gs.draw_panel(screen, next_box, gs.NEON_CYAN, fill_alpha=200, radius=8)
        blit_pixel_text(screen, "PROSSIMI", (next_box.centerx, next_box.y + 10), 2, gs.TEXT_DIM, "midtop")
        for i, kind in enumerate(list(game.queue)[:PREVIEW_COUNT]):
            size = 22 if i == 0 else 16
            cy = next_box.y + 75 + i * 80
            draw_mini_piece(screen, kind, (next_box.centerx, cy), size)
        help_y = OFF_Y + 330
        for k, line in enumerate(("← → muovi", "↑ X / Z ruota", "↓ soft drop", "SPAZIO hard drop",
                                  "ESC pausa")):
            gs.draw_text(screen, line, label_font, gs.TEXT_DIM, (rx, help_y + k * 22))
        particles.draw(screen)
        popups.draw(screen)
        shake.apply(screen)

    while True:
        dt = clock.tick()
        result = handle_events()
        if result:
            record_best(load_scores, save_scores, "tetris", game.score)
            return result
        if not game.game_over:
            auto_shift(dt)
            keys = pygame.key.get_pressed()
            soft = keys[pygame.K_DOWN] or keys[pygame.K_s]
            game.update(dt, soft_drop=soft)
        react(game.pop_events())
        particles.update(dt)
        popups.update(dt)
        shake.update(dt)
        draw()
        gs.present(screen)

        if game.game_over:
            pygame.time.wait(350)
            new_record = record_best(load_scores, save_scores, "tetris", game.score)
            best = max(best, game.score)
            choice = gs.end_screen(screen, "GAME OVER", [
                f"Punteggio: {game.score}   Linee: {game.lines}   Livello: {game.level}",
                f"Record: {best}",
            ], new_record=new_record)
            clock.reset()
            if choice in ("menu", "quit"):
                return choice
            game = new_game()
            particles.clear()
            popups.clear()


# Backwards-compatible name used by older launchers.
tetris_game = main


if __name__ == "__main__":
    main()
    gs.shutdown()
