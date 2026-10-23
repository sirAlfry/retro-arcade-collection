# snake.py
"""
Snake - eat, grow, don't bite yourself.

Rules:
    * Red apple: +2 points, always on the field.
    * Blue fruit: +5 points, appears for a few seconds (it blinks before
      vanishing), then comes back after a cooldown.
    * Speed grows with the score: 8 steps/s + 1 every 5 points (max 20).
    * Walls and your own body are deadly.

Improvements over the first version:
    * logic on a cell grid (no pixel arithmetic), separate from the drawing;
    * input buffer: quick "up then left" turns are no longer lost;
    * the game waits for the first key press instead of starting instantly;
    * particle effects now use real trigonometry (cos/sin of the angle);
    * the field no longer overlaps the HUD; best score is saved persistently.
"""
from __future__ import annotations

import math
import random
from collections import deque
from collections.abc import Callable

import pygame

import game_shared as gs
import sfx
from pixel_font import blit_pixel_text
from scores import get_best, record_best

W, H = gs.W, gs.H
GRID = 20
HUD_H = 40
COLS = W // GRID
ROWS = (H - HUD_H) // GRID
BASE_SPEED = 8
MAX_SPEED = 20
BONUS_LIFETIME = 7.0
BONUS_COOLDOWN = (4.0, 8.0)
RED_POINTS = 2
BLUE_POINTS = 5

COMMANDS = [
    "Frecce o WASD: cambia direzione",
    "Mela rossa +2   Frutto blu +5 (scade!)",
]

Cell = tuple[int, int]
DIRECTIONS = {
    pygame.K_UP: (0, -1), pygame.K_w: (0, -1),
    pygame.K_DOWN: (0, 1), pygame.K_s: (0, 1),
    pygame.K_LEFT: (-1, 0), pygame.K_a: (-1, 0),
    pygame.K_RIGHT: (1, 0), pygame.K_d: (1, 0),
}


class SnakeLogic:
    """Pure game state and rules (no drawing)."""

    def __init__(self, rng: random.Random | None = None,
                 cols: int = COLS, rows: int = ROWS) -> None:
        self.rng = rng or random.Random()
        self.cols, self.rows = cols, rows
        cx, cy = cols // 2, rows // 2
        self.body: list[Cell] = [(cx, cy), (cx - 1, cy), (cx - 2, cy)]
        self.direction: Cell = (1, 0)
        self.queue: deque[Cell] = deque(maxlen=3)
        self.alive = True
        self.started = False
        self.score = 0
        self.red: Cell = self.free_cell()
        self.blue: Cell | None = None
        self.blue_timer = 0.0                  # time left while visible
        self.blue_cooldown = self.rng.uniform(*BONUS_COOLDOWN)
        self.step_timer = 0.0
        self.events: list[tuple[str, Cell]] = []

    # ------------------------------------------------------------ helpers
    def free_cell(self) -> Cell:
        """A random cell not occupied by the snake or by other food."""
        occupied = set(self.body)
        if getattr(self, "red", None):
            occupied.add(self.red)
        if getattr(self, "blue", None):
            occupied.add(self.blue)  # type: ignore[arg-type]
        free = [(x, y) for x in range(self.cols) for y in range(self.rows) if (x, y) not in occupied]
        return self.rng.choice(free) if free else self.body[-1]

    @property
    def speed(self) -> float:
        """Steps per second."""
        return min(BASE_SPEED + self.score // 5, MAX_SPEED)

    def turn(self, d: Cell) -> None:
        """Queue a direction change (180° turns are ignored)."""
        last = self.queue[-1] if self.queue else self.direction
        if d != last and d != (-last[0], -last[1]):
            self.queue.append(d)
        self.started = True

    # -------------------------------------------------------------- rules
    def step(self) -> None:
        """Advance the snake by one cell."""
        while self.queue:
            d = self.queue.popleft()
            if d != (-self.direction[0], -self.direction[1]):
                self.direction = d
                break
        hx, hy = self.body[0]
        head = (hx + self.direction[0], hy + self.direction[1])
        will_grow = head == self.red or head == self.blue
        body_to_check = self.body if will_grow else self.body[:-1]
        if not (0 <= head[0] < self.cols and 0 <= head[1] < self.rows) or head in body_to_check:
            self.alive = False
            self.events.append(("die", self.body[0]))
            return
        self.body.insert(0, head)
        if head == self.red:
            self.score += RED_POINTS
            self.events.append(("eat", head))
            self.red = self.free_cell()
        elif head == self.blue:
            self.score += BLUE_POINTS
            self.events.append(("bonus", head))
            self.blue = None
            self.blue_cooldown = self.rng.uniform(*BONUS_COOLDOWN)
        else:
            self.body.pop()

    def update(self, dt: float) -> None:
        if not self.alive or not self.started:
            return
        # bonus fruit timers
        if self.blue is not None:
            self.blue_timer -= dt
            if self.blue_timer <= 0:
                self.blue = None
                self.blue_cooldown = self.rng.uniform(*BONUS_COOLDOWN)
        else:
            self.blue_cooldown -= dt
            if self.blue_cooldown <= 0:
                self.blue = self.free_cell()
                self.blue_timer = BONUS_LIFETIME
        # movement at a speed that depends on the score
        self.step_timer += dt
        interval = 1.0 / self.speed
        while self.step_timer >= interval and self.alive:
            self.step_timer -= interval
            self.step()

    def pop_events(self) -> list[tuple[str, Cell]]:
        events, self.events = self.events, []
        return events


# ============================================================================
# Drawing
# ============================================================================

def _field_background() -> pygame.Surface:
    surf = pygame.Surface((COLS * GRID, ROWS * GRID))
    for y in range(ROWS):
        for x in range(COLS):
            c = (16, 18, 36) if (x + y) % 2 == 0 else (20, 22, 42)
            surf.fill(c, (x * GRID, y * GRID, GRID, GRID))
    return surf


def cell_rect(cell: Cell) -> pygame.Rect:
    return pygame.Rect(cell[0] * GRID, HUD_H + cell[1] * GRID, GRID, GRID)


def draw_snake(screen: pygame.Surface, game: SnakeLogic, flash: bool = False) -> None:
    """Draw a continuous, gradient-colored snake with eyes on the head."""
    n = len(game.body)
    for i in range(n - 1, -1, -1):
        seg = game.body[i]
        if flash:
            color = gs.WHITE if (i // 2) % 2 == 0 else gs.NEON_RED
        else:
            color = gs.lerp_color((120, 255, 140), (20, 120, 60), i / max(1, n - 1))
        rect = cell_rect(seg)
        if i < n - 1:  # bridge towards the previous segment -> continuous body
            bridge = rect.inflate(-6, -6).union(cell_rect(game.body[i + 1]).inflate(-6, -6))
            pygame.draw.rect(screen, color, bridge)
        size = -2 if i < n - 1 else -6
        pygame.draw.rect(screen, color, rect.inflate(size, size), border_radius=7)
        if i % 3 == 1 and not flash:  # subtle scale pattern
            pygame.draw.circle(screen, gs.lerp_color(color, gs.WHITE, 0.25), rect.center, 2)
    # eyes looking where the snake goes
    head = cell_rect(game.body[0])
    dx, dy = game.direction
    cx, cy = head.center
    for side in (-1, 1):
        ex = cx + dx * 4 + (-dy) * side * 5
        ey = cy + dy * 4 + dx * side * 5
        pygame.draw.circle(screen, gs.WHITE, (ex, ey), 3)
        pygame.draw.circle(screen, gs.BLACK, (ex + dx, ey + dy), 1)


def draw_food(screen: pygame.Surface, cell: Cell, color: gs.Color, t: float,
              visible: bool = True) -> None:
    if not visible:
        return
    rect = cell_rect(cell)
    r = GRID // 2 - 2 + int(1.5 * math.sin(t * 6))
    glow = pygame.Surface((GRID * 2, GRID * 2), pygame.SRCALPHA)
    pygame.draw.circle(glow, (*color, 60), (GRID, GRID), GRID - 2)
    screen.blit(glow, glow.get_rect(center=rect.center))
    pygame.draw.circle(screen, color, rect.center, r)
    pygame.draw.circle(screen, gs.lerp_color(color, gs.WHITE, 0.6),
                       (rect.centerx - 3, rect.centery - 3), 2)
    pygame.draw.line(screen, (90, 200, 90), (rect.centerx, rect.top + 2),
                     (rect.centerx + 3, rect.top - 2), 2)


# ============================================================================
# Game loop
# ============================================================================

def main(load_scores: Callable[[], dict] | None = None,
         save_scores: Callable[[dict], None] | None = None) -> str:
    """
    Play Snake.

    Returns:
        ``"menu"`` or ``"quit"``.
    """
    load_scores, save_scores = gs.ensure_scores(load_scores, save_scores)
    screen = gs.setup_screen("Snake")
    clock = gs.GameClock(60)
    field_bg = _field_background()
    particles = gs.Particles()
    popups = gs.FloatingTexts()
    shake = gs.ScreenShake(8)
    best = get_best(load_scores, "snake", 0) or 0
    game = SnakeLogic()
    t = 0.0

    def draw(flash: bool = False) -> None:
        screen.fill(gs.BG)
        screen.blit(field_bg, (0, HUD_H))
        pygame.draw.rect(screen, gs.NEON_GREEN, (0, HUD_H - 2, W, H - HUD_H + 2), 2)
        draw_food(screen, game.red, gs.NEON_RED, t)
        if game.blue is not None:
            blinking = game.blue_timer < 2.0 and int(t * 8) % 2 == 0
            draw_food(screen, game.blue, gs.NEON_BLUE, t, visible=not blinking)
        draw_snake(screen, game, flash)
        particles.draw(screen)
        popups.draw(screen)
        # HUD
        blit_pixel_text(screen, f"PUNTEGGIO {game.score}", (12, HUD_H // 2), 2, gs.NEON_CYAN, "midleft")
        blit_pixel_text(screen, f"RECORD {max(best, game.score)}", (W // 2, HUD_H // 2), 2,
                        gs.NEON_YELLOW, "center")
        blit_pixel_text(screen, f"LUNGHEZZA {len(game.body)}", (W - 12, HUD_H // 2), 2,
                        gs.NEON_GREEN, "midright")
        if game.blue is not None:
            bar = int(120 * max(0.0, game.blue_timer) / BONUS_LIFETIME)
            pygame.draw.rect(screen, gs.NEON_BLUE, (W // 2 - 60, HUD_H - 7, bar, 3))
        if not game.started:
            box = pygame.Rect(0, 0, 460, 70)
            box.center = (W // 2, H // 2 + 60)
            gs.draw_panel(screen, box, gs.NEON_GREEN, fill_alpha=200)
            blit_pixel_text(screen, "PREMI UNA FRECCIA", (W // 2, box.centery - 10), 3,
                            gs.WHITE, "center")
            blit_pixel_text(screen, "PER INIZIARE", (W // 2, box.centery + 18), 2, gs.TEXT_DIM, "center")
        shake.apply(screen)

    while True:
        dt = clock.tick()
        t += dt
        for e in pygame.event.get():
            if gs.handle_global_event(e):
                continue
            if e.type == pygame.QUIT:
                record_best(load_scores, save_scores, "snake", game.score)
                return "quit"
            if e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_ESCAPE, pygame.K_p):
                    choice = gs.in_game_menu(screen, "Snake", COMMANDS)
                    clock.reset()
                    if choice in ("menu", "quit"):
                        record_best(load_scores, save_scores, "snake", game.score)
                        return choice
                    if choice == "restart":
                        game = SnakeLogic()
                        particles.clear()
                elif e.key in DIRECTIONS:
                    game.turn(DIRECTIONS[e.key])

        game.update(dt)
        for kind, cell in game.pop_events():
            cx, cy = cell_rect(cell).center
            if kind == "eat":
                sfx.play("eat")
                particles.burst(cx, cy, (gs.NEON_RED, gs.NEON_ORANGE, gs.NEON_YELLOW), 14,
                                speed=(60, 200), life=(0.25, 0.6))
                popups.add(f"+{RED_POINTS}", cx, cy - 10, gs.NEON_YELLOW)
            elif kind == "bonus":
                sfx.play("bonus")
                particles.burst(cx, cy, (gs.NEON_BLUE, gs.NEON_CYAN, gs.WHITE), 24,
                                speed=(80, 260), life=(0.3, 0.8))
                popups.add(f"+{BLUE_POINTS}", cx, cy - 10, gs.NEON_CYAN, 1.0, 3)
            elif kind == "die":
                sfx.play("hurt")
                shake.add(0.7)
                for seg in game.body[::2]:
                    sx, sy = cell_rect(seg).center
                    particles.burst(sx, sy, (gs.NEON_GREEN, gs.WHITE), 5,
                                    speed=(40, 180), life=(0.4, 0.9))
        particles.update(dt)
        popups.update(dt)
        shake.update(dt)
        draw()
        gs.present(screen)

        if not game.alive:
            # short death animation before the results screen
            for i in range(45):
                dt = clock.tick()
                t += dt
                particles.update(dt)
                shake.update(dt)
                draw(flash=(i // 6) % 2 == 0)
                gs.present(screen)
                pygame.event.pump()
            new_record = record_best(load_scores, save_scores, "snake", game.score)
            best = max(best, game.score)
            choice = gs.end_screen(screen, "GAME OVER", [
                f"Punteggio: {game.score}   Lunghezza: {len(game.body)}",
                f"Record: {best}",
            ], new_record=new_record)
            clock.reset()
            if choice in ("menu", "quit"):
                return choice
            game = SnakeLogic()
            particles.clear()
            popups.clear()


def snake_game(load_scores: Callable[[], dict], save_scores: Callable[[dict], None]) -> str:
    """Backwards-compatible entry point (old launcher signature)."""
    return main(load_scores, save_scores)


if __name__ == "__main__":
    main()
    gs.shutdown()
