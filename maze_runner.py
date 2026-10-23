# maze_runner.py
"""
Maze Runner - find the exit of a procedurally generated labyrinth.

* Mazes are "perfect" (exactly one path between any two cells), carved with
  an iterative depth-first search (recursive backtracker).
* Four difficulties, including a **dark** mode where you only see what your
  torch lights up.
* Press **H** for a hint: a breadth-first search (BFS) shows the shortest way
  out for a few seconds, at the cost of +10 seconds.
* Smooth movement, hold an arrow to run, breadcrumbs of where you've been,
  best time saved for each difficulty.
"""
from __future__ import annotations

import math
import random
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

import pygame

import game_shared as gs
import sfx
from pixel_font import blit_pixel_text
from scores import get_best, record_best

W, H = gs.W, gs.H
HUD_H = 44
REPEAT_DELAY = 0.17
REPEAT_RATE = 0.075
HINT_PENALTY = 10.0
HINT_TIME = 3.0

COMMANDS = [
    "Frecce o WASD: muovi (tieni premuto per correre)",
    "H: suggerimento con BFS (+10 secondi)",
]

Cell = tuple[int, int]
Grid = list[list[int]]  # 1 = wall, 0 = floor


@dataclass(frozen=True)
class Difficulty:
    label: str
    key: str
    cols: int
    rows: int
    dark: bool = False


DIFFICULTIES = (
    Difficulty("PICCOLO  21 X 15", "small", 21, 15),
    Difficulty("MEDIO  31 X 21", "medium", 31, 21),
    Difficulty("GRANDE  41 X 29", "large", 41, 29),
    Difficulty("AL BUIO  31 X 21", "dark", 31, 21, dark=True),
)


def generate_maze(cols: int, rows: int, rng: random.Random | None = None) -> Grid:
    """
    Carve a perfect maze with an iterative depth-first search.

    Cells with even coordinates are rooms, the others are walls that get
    knocked down between neighbouring rooms. ``cols`` and ``rows`` are forced
    to be odd so the border is always solid.
    """
    rng = rng or random.Random()
    cols = cols if cols % 2 else cols + 1
    rows = rows if rows % 2 else rows + 1
    grid = [[1] * cols for _ in range(rows)]
    stack: list[Cell] = [(0, 0)]
    grid[0][0] = 0
    while stack:
        x, y = stack[-1]
        neighbours = [(x + dx, y + dy) for dx, dy in ((2, 0), (-2, 0), (0, 2), (0, -2))
                      if 0 <= x + dx < cols and 0 <= y + dy < rows and grid[y + dy][x + dx] == 1]
        if neighbours:
            nx, ny = rng.choice(neighbours)
            grid[(y + ny) // 2][(x + nx) // 2] = 0
            grid[ny][nx] = 0
            stack.append((nx, ny))
        else:
            stack.pop()
    return grid


def shortest_path(grid: Grid, start: Cell, goal: Cell) -> list[Cell]:
    """Breadth-first search; returns the cells from ``start`` to ``goal`` (inclusive)."""
    rows, cols = len(grid), len(grid[0])
    came_from: dict[Cell, Cell | None] = {start: None}
    queue: deque[Cell] = deque([start])
    while queue:
        cur = queue.popleft()
        if cur == goal:
            break
        x, y = cur
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < cols and 0 <= ny < rows and grid[ny][nx] == 0 and (nx, ny) not in came_from:
                came_from[(nx, ny)] = cur
                queue.append((nx, ny))
    if goal not in came_from:
        return []
    path = [goal]
    while path[-1] != start:
        prev = came_from[path[-1]]
        assert prev is not None
        path.append(prev)
    return path[::-1]


def get_difficulty_params(difficulty: str) -> tuple[int, int]:
    """Backwards-compatible helper: maze size for ``small/medium/large``."""
    for d in DIFFICULTIES:
        if d.key == difficulty:
            return (d.cols, d.rows)
    return (DIFFICULTIES[1].cols, DIFFICULTIES[1].rows)


def _light_mask(radius: int) -> pygame.Surface:
    """Radial alpha gradient used to cut a 'torch' hole in the darkness."""
    size = radius * 2
    mask = pygame.Surface((size, size), pygame.SRCALPHA)
    mask.fill((0, 0, 0, 255))
    for r in range(radius, 0, -2):
        alpha = int(255 * (r / radius) ** 2.2)
        pygame.draw.circle(mask, (0, 0, 0, alpha), (radius, radius), r)
    return mask


def main(load_scores: Callable[[], dict] | None = None,
         save_scores: Callable[[dict], None] | None = None,
         difficulty: str | None = None) -> str:
    """
    Play Maze Runner.

    Args:
        load_scores / save_scores: Persistence callables.
        difficulty: Optional ``small``/``medium``/``large``/``dark`` to skip
            the difficulty menu.

    Returns:
        ``"menu"`` or ``"quit"``.
    """
    load_scores, save_scores = gs.ensure_scores(load_scores, save_scores)
    screen = gs.setup_screen("Maze Runner")
    clock = gs.GameClock(60)

    if difficulty is None:
        choice = gs.select_menu(screen, "MAZE RUNNER", [d.label for d in DIFFICULTIES],
                                ["Scegli la dimensione del labirinto"], default=1)
        if isinstance(choice, str):
            return choice
        diff = DIFFICULTIES[choice]
    else:
        diff = next((d for d in DIFFICULTIES if d.key == difficulty), DIFFICULTIES[1])

    record_key = f"maze_time_{diff.key}"
    light = _light_mask(120)
    darkness = pygame.Surface((W, H), pygame.SRCALPHA)
    particles = gs.Particles()

    class Run:
        def __init__(self) -> None:
            self.grid = generate_maze(diff.cols, diff.rows)
            self.rows, self.cols = len(self.grid), len(self.grid[0])
            self.cell = min((W - 24) // self.cols, (H - HUD_H - 16) // self.rows)
            self.ox = (W - self.cols * self.cell) // 2
            self.oy = HUD_H + (H - HUD_H - self.rows * self.cell) // 2
            self.goal: Cell = (self.cols - 1, self.rows - 1)
            self.pos: Cell = (0, 0)
            self.vis_x, self.vis_y = 0.0, 0.0
            self.moves = 0
            self.hints = 0
            self.hint_path: list[Cell] = []
            self.hint_timer = 0.0
            self.visited: set[Cell] = {(0, 0)}
            self.timer = gs.Stopwatch()
            self.timer.running = False
            self.repeat = 0.0
            self.surface = self.render_walls()

        def render_walls(self) -> pygame.Surface:
            c = self.cell
            surf = pygame.Surface((self.cols * c, self.rows * c))
            surf.fill((10, 10, 26))
            wall, top = (40, 90, 210), (90, 150, 255)
            for y, row in enumerate(self.grid):
                for x, v in enumerate(row):
                    if v:
                        surf.fill(wall, (x * c, y * c, c, c))
                        surf.fill(top, (x * c, y * c, c, max(2, c // 6)))
            pygame.draw.rect(surf, gs.NEON_CYAN, surf.get_rect(), 2)
            return surf

        def center(self, cell: Cell) -> tuple[int, int]:
            return (self.ox + cell[0] * self.cell + self.cell // 2,
                    self.oy + cell[1] * self.cell + self.cell // 2)

        def try_move(self, dx: int, dy: int) -> bool:
            x, y = self.pos[0] + dx, self.pos[1] + dy
            if 0 <= x < self.cols and 0 <= y < self.rows and self.grid[y][x] == 0:
                self.pos = (x, y)
                self.moves += 1
                self.visited.add(self.pos)
                self.timer.running = True
                sfx.play("move", 0.25)
                return True
            return False

    run = Run()
    best_time = get_best(load_scores, record_key)
    t = 0.0
    key_dirs = {pygame.K_UP: (0, -1), pygame.K_w: (0, -1), pygame.K_DOWN: (0, 1), pygame.K_s: (0, 1),
                pygame.K_LEFT: (-1, 0), pygame.K_a: (-1, 0), pygame.K_RIGHT: (1, 0), pygame.K_d: (1, 0)}

    def draw() -> None:
        screen.fill(gs.BG)
        screen.blit(run.surface, (run.ox, run.oy))
        c = run.cell
        for vx, vy in run.visited:
            px, py = run.center((vx, vy))
            screen.fill((90, 80, 150), (px - 1, py - 1, 3, 3))
        gx, gy = run.center(run.goal)
        pulse = 0.5 + 0.5 * math.sin(t * 5)
        pygame.draw.rect(screen, gs.lerp_color((20, 120, 60), gs.NEON_GREEN, pulse),
                         (gx - c // 2 + 1, gy - c // 2 + 1, c - 2, c - 2), border_radius=3)
        px = int(run.ox + run.vis_x * c + c // 2)
        py = int(run.oy + run.vis_y * c + c // 2)
        if diff.dark:
            darkness.fill((0, 0, 0, 252))
            darkness.blit(light, light.get_rect(center=(px, py)), special_flags=pygame.BLEND_RGBA_MIN)
            screen.blit(darkness, (0, 0))
            beacon = int(80 + 80 * pulse)
            glow = pygame.Surface((c * 3, c * 3), pygame.SRCALPHA)
            pygame.draw.circle(glow, (*gs.NEON_GREEN, beacon), (c * 3 // 2, c * 3 // 2), c)
            screen.blit(glow, glow.get_rect(center=(gx, gy)))
        if run.hint_timer > 0:  # drawn after the darkness, so hints work in dark mode too
            for i, cell in enumerate(run.hint_path):
                if (i + int(t * 12)) % 3 == 0:
                    hx, hy = run.center(cell)
                    pygame.draw.circle(screen, gs.NEON_YELLOW, (hx, hy), max(2, c // 5))
        pygame.draw.circle(screen, gs.NEON_YELLOW, (px, py), max(3, c // 2 - 2))
        pygame.draw.circle(screen, gs.WHITE, (px - 2, py - 2), max(1, c // 7))
        particles.draw(screen)
        # HUD
        blit_pixel_text(screen, f"TEMPO {gs.format_time(run.timer.elapsed)}", (14, HUD_H // 2), 2,
                        gs.NEON_CYAN, "midleft")
        blit_pixel_text(screen, f"MOSSE {run.moves}", (230, HUD_H // 2), 2, gs.NEON_GREEN, "midleft")
        rec = gs.format_time(best_time) if best_time else "--:--"
        blit_pixel_text(screen, f"RECORD {rec}", (400, HUD_H // 2), 2, gs.NEON_YELLOW, "midleft")
        blit_pixel_text(screen, "H AIUTO", (W - 14, HUD_H // 2), 2, gs.TEXT_DIM, "midright")
        if not run.timer.running and run.moves == 0:
            blit_pixel_text(screen, "RAGGIUNGI L'USCITA VERDE!", (W // 2, H - 14), 2, gs.WHITE, "center")

    while True:
        dt = clock.tick()
        t += dt
        for e in pygame.event.get():
            if gs.handle_global_event(e):
                continue
            if e.type == pygame.QUIT:
                return "quit"
            if e.type != pygame.KEYDOWN:
                continue
            if e.key in (pygame.K_ESCAPE, pygame.K_p):
                choice = gs.in_game_menu(screen, "Maze Runner", COMMANDS)
                clock.reset()
                if choice in ("menu", "quit"):
                    return choice
                if choice == "restart":
                    run = Run()
            elif e.key in key_dirs:
                run.try_move(*key_dirs[e.key])
                run.repeat = REPEAT_DELAY
            elif e.key == pygame.K_h:
                run.hint_path = shortest_path(run.grid, run.pos, run.goal)
                run.hint_timer = HINT_TIME
                run.hints += 1
                run.timer.elapsed += HINT_PENALTY
                sfx.play("powerup")
                gs.notify(f"+{HINT_PENALTY:.0f} SECONDI")

        # hold an arrow to keep running
        keys = pygame.key.get_pressed()
        held = [d for k, d in key_dirs.items() if keys[k]]
        if held:
            run.repeat -= dt
            if run.repeat <= 0:
                run.repeat += REPEAT_RATE
                run.try_move(*held[0])
        # smooth visual movement towards the logical cell
        follow = min(1.0, dt * 22)
        run.vis_x += (run.pos[0] - run.vis_x) * follow
        run.vis_y += (run.pos[1] - run.vis_y) * follow
        run.timer.update(dt)
        run.hint_timer = max(0.0, run.hint_timer - dt)
        particles.update(dt)
        draw()
        gs.present(screen)

        if run.pos == run.goal:
            run.timer.stop()
            gx, gy = run.center(run.goal)
            particles.burst(gx, gy, (gs.NEON_GREEN, gs.NEON_YELLOW, gs.WHITE), 60,
                            speed=(80, 320), life=(0.5, 1.2))
            for _ in range(40):
                dt = clock.tick()
                t += dt
                particles.update(dt)
                draw()
                gs.present(screen)
                pygame.event.pump()
            elapsed = round(run.timer.elapsed, 1)
            new_record = record_best(load_scores, save_scores, record_key, elapsed, lower_is_better=True)
            best_time = get_best(load_scores, record_key, elapsed)
            choice = gs.end_screen(screen, "USCITA TROVATA!", [
                f"Tempo: {gs.format_time(elapsed)}   Mosse: {run.moves}   Aiuti: {run.hints}",
                f"Record ({diff.label.split()[0].lower()}): {gs.format_time(best_time)}",
            ], new_record=new_record, win=True)
            clock.reset()
            if choice in ("menu", "quit"):
                return choice
            run = Run()
            particles.clear()


if __name__ == "__main__":
    main()
    gs.shutdown()
