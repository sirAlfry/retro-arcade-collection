# puzzle15.py
"""
Puzzle 15 - the classic sliding puzzle (Sam Loyd's "Gem Puzzle").

Bug fixed: the first version used the wrong parity test, so **every**
shuffled board was mathematically unsolvable. The rule for a 4x4 board is:

    solvable  <=>  (inversions + row of the blank counted from the bottom) is odd

New features:
    * click any tile in the blank's row/column to slide the whole line at once
    * arrow keys push a tile into the gap (tile moves in the arrow direction)
    * smooth sliding animation for every tile
    * tiles glow when they sit in their final position; colours by target row
    * best moves and best time are saved
"""
from __future__ import annotations

import random
from collections.abc import Callable

import pygame

import game_shared as gs
import sfx
from pixel_font import blit_pixel_text
from scores import get_best, record_best

W, H = gs.W, gs.H
HUD_H = 44
SIZE = 4
TILE = 110
GAP = 8
BOARD_PX = SIZE * TILE + (SIZE - 1) * GAP
OFF_X = (W - BOARD_PX) // 2
OFF_Y = HUD_H + (H - HUD_H - BOARD_PX) // 2
ROW_COLORS = (gs.NEON_CYAN, gs.NEON_MAGENTA, gs.NEON_YELLOW, gs.NEON_GREEN)
SOLVED = list(range(1, SIZE * SIZE)) + [0]

COMMANDS = [
    "Clic su una tessera nella riga/colonna del buco",
    "Frecce: spingi una tessera nel buco   R: rimescola",
]


# ============================================================================
# Pure puzzle logic (unit-tested)
# ============================================================================

def inversions(tiles: list[int]) -> int:
    """Number of pairs (a, b) with a before b but a > b, ignoring the blank (0)."""
    nums = [t for t in tiles if t]
    return sum(1 for i in range(len(nums)) for j in range(i + 1, len(nums)) if nums[i] > nums[j])


def is_solvable(tiles: list[int], size: int = SIZE) -> bool:
    """
    Parity test for an N x N sliding puzzle (0 = blank).

    * odd width: solvable iff the number of inversions is even;
    * even width: solvable iff inversions + (blank row counted from the
      bottom, starting at 1) is odd.
    """
    inv = inversions(tiles)
    if size % 2 == 1:
        return inv % 2 == 0
    blank_row_from_bottom = size - tiles.index(0) // size
    return (inv + blank_row_from_bottom) % 2 == 1


def is_solved(tiles: list[int]) -> bool:
    return tiles == SOLVED if len(tiles) == SIZE * SIZE else tiles == list(range(1, len(tiles))) + [0]


def shuffled(rng: random.Random | None = None, size: int = SIZE) -> list[int]:
    """A random, solvable, not-already-solved board."""
    rng = rng or random.Random()
    tiles = list(range(1, size * size)) + [0]
    while True:
        rng.shuffle(tiles)
        if is_solvable(tiles, size) and not is_solved(tiles):
            return tiles[:]


def slide(tiles: list[int], index: int, size: int = SIZE) -> int:
    """
    Slide the tile at ``index`` (and the ones between it and the blank) into
    the blank, if they share a row or a column. Modifies ``tiles`` in place.

    Returns:
        How many tiles moved (0 if the move is not possible).
    """
    blank = tiles.index(0)
    br, bc = divmod(blank, size)
    r, c = divmod(index, size)
    if index == blank or (r != br and c != bc):
        return 0
    step = (1 if c > bc else -1) if r == br else (size if r > br else -size)
    moved = 0
    pos = blank
    while pos != index:
        nxt = pos + step
        tiles[pos], tiles[nxt] = tiles[nxt], tiles[pos]
        pos = nxt
        moved += 1
    return moved


def push(tiles: list[int], dx: int, dy: int, size: int = SIZE) -> int:
    """Arrow-key move: the tile next to the blank moves in direction (dx, dy)."""
    blank = tiles.index(0)
    br, bc = divmod(blank, size)
    r, c = br - dy, bc - dx  # the tile that will move into the blank
    if 0 <= r < size and 0 <= c < size:
        return slide(tiles, r * size + c, size)
    return 0


# ============================================================================
# Game
# ============================================================================

def tile_pos(index: int) -> tuple[float, float]:
    r, c = divmod(index, SIZE)
    return (OFF_X + c * (TILE + GAP), OFF_Y + r * (TILE + GAP))


def main(load_scores: Callable[[], dict] | None = None,
         save_scores: Callable[[dict], None] | None = None) -> str:
    """
    Play Puzzle 15.

    Returns:
        ``"menu"`` or ``"quit"``.
    """
    load_scores, save_scores = gs.ensure_scores(load_scores, save_scores)
    screen = gs.setup_screen("Puzzle 15")
    clock = gs.GameClock(60)
    particles = gs.Particles()

    class Round:
        def __init__(self) -> None:
            self.tiles = shuffled()
            self.moves = 0
            self.timer = gs.Stopwatch()
            self.timer.running = False
            self.visual = {v: list(tile_pos(i)) for i, v in enumerate(self.tiles) if v}
            self.best_moves = get_best(load_scores, "puzzle15_moves")
            self.best_time = get_best(load_scores, "puzzle15_time")

        def apply(self, moved: int) -> None:
            if moved:
                self.moves += moved
                self.timer.running = True
                sfx.play("slide")

    rnd = Round()

    def draw() -> None:
        screen.fill(gs.BG)
        frame = pygame.Rect(OFF_X - 14, OFF_Y - 14, BOARD_PX + 28, BOARD_PX + 28)
        pygame.draw.rect(screen, (10, 8, 26), frame, border_radius=14)
        pygame.draw.rect(screen, gs.NEON_YELLOW, frame, 3, border_radius=14)
        for i in range(SIZE * SIZE):
            x, y = tile_pos(i)
            pygame.draw.rect(screen, (18, 16, 40), (x, y, TILE, TILE), border_radius=10)
        in_place = 0
        for i, v in enumerate(rnd.tiles):
            if not v:
                continue
            x, y = rnd.visual[v]
            rect = pygame.Rect(int(x), int(y), TILE, TILE)
            home_row = (v - 1) // SIZE
            color = ROW_COLORS[home_row]
            correct = i == v - 1
            in_place += correct
            base = gs.lerp_color((26, 22, 56), color, 0.28 if correct else 0.12)
            pygame.draw.rect(screen, (4, 2, 12), rect.move(4, 5), border_radius=10)
            pygame.draw.rect(screen, base, rect, border_radius=10)
            pygame.draw.rect(screen, color if correct else gs.lerp_color(color, gs.BG, 0.55), rect,
                             3, border_radius=10)
            pygame.draw.line(screen, gs.lerp_color(base, gs.WHITE, 0.25),
                             (rect.x + 10, rect.y + 6), (rect.right - 10, rect.y + 6), 2)
            blit_pixel_text(screen, str(v), rect.center, 6, gs.WHITE if correct else color, "center",
                            shadow=(0, 0, 0))
        particles.draw(screen)
        blit_pixel_text(screen, f"MOSSE {rnd.moves}", (14, HUD_H // 2), 2, gs.NEON_CYAN, "midleft")
        blit_pixel_text(screen, f"TEMPO {rnd.timer}", (190, HUD_H // 2), 2, gs.NEON_GREEN, "midleft")
        blit_pixel_text(screen, f"AL POSTO {in_place}/15", (370, HUD_H // 2), 2, gs.NEON_MAGENTA, "midleft")
        best = (f"{rnd.best_moves} · {gs.format_time(rnd.best_time or 0)}" if rnd.best_moves else "--")
        blit_pixel_text(screen, f"RECORD {best}", (W - 14, HUD_H // 2), 2, gs.NEON_YELLOW, "midright")

    arrows = {pygame.K_UP: (0, -1), pygame.K_w: (0, -1), pygame.K_DOWN: (0, 1), pygame.K_s: (0, 1),
              pygame.K_LEFT: (-1, 0), pygame.K_a: (-1, 0), pygame.K_RIGHT: (1, 0), pygame.K_d: (1, 0)}

    while True:
        dt = clock.tick()
        for e in pygame.event.get():
            if gs.handle_global_event(e):
                continue
            if e.type == pygame.QUIT:
                return "quit"
            if e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_ESCAPE, pygame.K_p):
                    choice = gs.in_game_menu(screen, "Puzzle 15", COMMANDS)
                    clock.reset()
                    if choice in ("menu", "quit"):
                        return choice
                    if choice == "restart":
                        rnd = Round()
                elif e.key == pygame.K_r:
                    rnd = Round()
                    sfx.play("select")
                elif e.key in arrows:
                    rnd.apply(push(rnd.tiles, *arrows[e.key]))
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                for i in range(SIZE * SIZE):
                    x, y = tile_pos(i)
                    if pygame.Rect(x, y, TILE, TILE).collidepoint(e.pos):
                        moved = slide(rnd.tiles, i)
                        if moved:
                            rnd.apply(moved)
                        else:
                            sfx.play("error", 0.4)
                        break

        # ease every tile towards its slot
        follow = min(1.0, dt * 18)
        for i, v in enumerate(rnd.tiles):
            if v:
                tx, ty = tile_pos(i)
                vis = rnd.visual[v]
                vis[0] += (tx - vis[0]) * follow
                vis[1] += (ty - vis[1]) * follow
        rnd.timer.update(dt)
        particles.update(dt)
        draw()
        gs.present(screen)

        if is_solved(rnd.tiles) and rnd.moves > 0:
            rnd.timer.stop()
            for i in range(15):
                x, y = tile_pos(i)
                particles.burst(x + TILE // 2, y + TILE // 2, ROW_COLORS[i // SIZE], 8,
                                speed=(60, 240), life=(0.4, 1.0))
            for _ in range(45):
                dt = clock.tick()
                for i, v in enumerate(rnd.tiles):
                    if v:
                        rnd.visual[v] = list(tile_pos(i))
                particles.update(dt)
                draw()
                gs.present(screen)
                pygame.event.pump()
            seconds = round(rnd.timer.elapsed, 1)
            rec_moves = record_best(load_scores, save_scores, "puzzle15_moves", rnd.moves,
                                    lower_is_better=True)
            rec_time = record_best(load_scores, save_scores, "puzzle15_time", seconds,
                                   lower_is_better=True)
            best_moves = get_best(load_scores, "puzzle15_moves", rnd.moves)
            best_time = get_best(load_scores, "puzzle15_time", seconds)
            choice = gs.end_screen(screen, "COMPLETATO!", [
                f"Mosse: {rnd.moves}   Tempo: {gs.format_time(seconds)}",
                f"Record: {best_moves} mosse · {gs.format_time(best_time)}",
            ], new_record=rec_moves or rec_time, win=True)
            clock.reset()
            if choice in ("menu", "quit"):
                return choice
            rnd = Round()


class PuzzleGame:
    """Backwards-compatible wrapper around :func:`main`."""

    def run(self) -> str:
        return main()


if __name__ == "__main__":
    main()
    gs.shutdown()
