# tris.py
"""
Tic Tac Toe (Tris) - against a friend or against the computer.

* Modes: vs CPU (easy / medium / impossible) or 2 players.
  The old "1P" mode was identical to "2P"; it has been removed.
* The "impossible" CPU uses full-depth minimax with a transposition table
  (see ``game_ai.py``): it never loses - an exhaustive test proves it.
* Who starts alternates every round, so the CPU also gets to open.
* Neon marks drawn with an animated stroke, animated winning line,
  hover preview, keyboard cursor (arrows + ENTER).
* Wins/draws are saved (``tris_x``, ``tris_o``, ``tris_draw``).
"""
from __future__ import annotations

import math
from collections.abc import Callable

import pygame

import game_shared as gs
import sfx
from game_ai import GameAI, TicTacToeState
from pixel_font import blit_pixel_text

W, H = gs.W, gs.H
CELL = 150
BOARD = CELL * 3
OFF_X = (W - BOARD) // 2
OFF_Y = 52
CPU_DELAY = 0.45
STROKE_TIME = 0.18

COMMANDS = [
    "Clic o frecce + INVIO: piazza il segno",
    "TAB: CPU / 2 giocatori   1-2-3: difficoltà CPU",
]

LEVELS = ("easy", "medium", "hard")
LEVEL_NAMES = {"easy": "FACILE", "medium": "MEDIO", "hard": "IMPOSSIBILE"}
MODES = ("VS CPU · FACILE", "VS CPU · MEDIO", "VS CPU · IMPOSSIBILE", "2 GIOCATORI")

def winning_line(board: list[list[int | None]]) -> list[tuple[int, int]] | None:
    """Return the three (row, col) cells of a winning line, if any."""
    lines = [[(r, 0), (r, 1), (r, 2)] for r in range(3)]
    lines += [[(0, c), (1, c), (2, c)] for c in range(3)]
    lines += [[(0, 0), (1, 1), (2, 2)], [(0, 2), (1, 1), (2, 0)]]
    for line in lines:
        a, b, c = (board[r][col] for r, col in line)
        if a is not None and a == b == c:
            return line
    return None


def difficulty_label(d: int) -> str:
    """Backwards-compatible helper used by older code."""
    return "FACILE" if d <= 1 else ("MEDIO" if d <= 3 else "DIFFICILE")


def cell_rect(r: int, c: int) -> pygame.Rect:
    return pygame.Rect(OFF_X + c * CELL, OFF_Y + r * CELL, CELL, CELL)


def draw_mark(screen: pygame.Surface, mark: int, rect: pygame.Rect, progress: float,
              alpha: int = 255) -> None:
    """Draw an X (1) or an O (-1) with an animated neon stroke."""
    progress = max(0.0, min(1.0, progress))
    layer = pygame.Surface(rect.size, pygame.SRCALPHA)
    inner = layer.get_rect().inflate(-int(CELL * 0.42), -int(CELL * 0.42))
    if mark == 1:
        color = gs.NEON_RED
        segments = [(inner.topleft, inner.bottomright), (inner.topright, inner.bottomleft)]
        for k, (a, b) in enumerate(segments):
            p = max(0.0, min(1.0, progress * 2 - k))
            if p <= 0:
                continue
            end = (a[0] + (b[0] - a[0]) * p, a[1] + (b[1] - a[1]) * p)
            pygame.draw.line(layer, (*color, alpha // 4), a, end, 22)
            pygame.draw.line(layer, (*color, alpha), a, end, 10)
    else:
        color = gs.NEON_BLUE
        radius = inner.w // 2 + 4
        center = layer.get_rect().center
        if progress >= 1:
            pygame.draw.circle(layer, (*color, alpha // 4), center, radius + 6, 20)
            pygame.draw.circle(layer, (*color, alpha), center, radius, 10)
        else:
            box = pygame.Rect(0, 0, radius * 2, radius * 2)
            box.center = center
            start = math.pi / 2
            pygame.draw.arc(layer, (*color, alpha // 4), box.inflate(12, 12), start,
                            start + progress * math.tau, 20)
            pygame.draw.arc(layer, (*color, alpha), box, start, start + progress * math.tau, 10)
    screen.blit(layer, rect)


def main(load_scores: Callable[[], dict] | None = None,
         save_scores: Callable[[dict], None] | None = None) -> str:
    """
    Play Tic Tac Toe.

    Returns:
        ``"menu"`` or ``"quit"``.
    """
    load_scores, save_scores = gs.ensure_scores(load_scores, save_scores)
    screen = gs.setup_screen("Tic Tac Toe")
    clock = gs.GameClock(60)
    choice = gs.select_menu(screen, "TIC TAC TOE", MODES, ["X sei tu, O è la CPU o il tuo amico"],
                            default=1)
    if isinstance(choice, str):
        return choice
    vs_cpu = choice < 3
    level = LEVELS[min(choice, 2)] if vs_cpu else "medium"
    ai = GameAI.for_level(level, player_id=-1)

    data = load_scores()
    tally = {"x": int(data.get("tris_x", 0)), "o": int(data.get("tris_o", 0)),
             "draw": int(data.get("tris_draw", 0))}
    particles = gs.Particles()
    state = {
        "board": [[None] * 3 for _ in range(3)],
        "turn": 1, "starter": 1, "winner": None, "line": None, "over": False,
        "cpu_timer": 0.0, "placed": {}, "line_t": 0.0, "cursor": (1, 1), "hover": None,
    }
    t = 0.0

    def new_round(alternate: bool = True) -> None:
        if alternate:
            state["starter"] = -state["starter"]
        state.update(board=[[None] * 3 for _ in range(3)], turn=state["starter"], winner=None,
                     line=None, over=False, cpu_timer=CPU_DELAY, placed={}, line_t=0.0)

    def place(r: int, c: int) -> bool:
        board = state["board"]
        if state["over"] or board[r][c] is not None:
            return False
        mark = state["turn"]
        board[r][c] = mark
        state["placed"][(r, c)] = t
        sfx.play("place_x" if mark == 1 else "place_o")
        line = winning_line(board)
        if line:
            state.update(winner=mark, line=line, over=True, line_t=t)
        elif all(v is not None for row in board for v in row):
            state.update(winner=0, over=True, line_t=t)
        else:
            state["turn"] = -mark
            state["cpu_timer"] = CPU_DELAY
            return True
        # round finished: update and persist the tally
        key = {1: "x", -1: "o", 0: "draw"}[state["winner"]]
        tally[key] += 1
        save_scores({"tris_x": tally["x"], "tris_o": tally["o"], "tris_draw": tally["draw"]})
        if state["winner"] == 0:
            sfx.play("blip")
        elif vs_cpu and state["winner"] == -1:
            sfx.play("lose")
        else:
            sfx.play("win")
            for rr, cc in line or []:
                rect = cell_rect(rr, cc)
                particles.burst(rect.centerx, rect.centery,
                                (gs.NEON_RED if mark == 1 else gs.NEON_BLUE, gs.WHITE), 20,
                                speed=(60, 260), life=(0.4, 1.0))
        return True

    def human_turn() -> bool:
        return not state["over"] and (not vs_cpu or state["turn"] == 1)

    def draw() -> None:
        screen.fill(gs.BG)
        # scoreboard
        left = "X (TU)" if vs_cpu else "X (G1)"
        right = f"O (CPU {LEVEL_NAMES[level]})" if vs_cpu else "O (G2)"
        blit_pixel_text(screen, f"{left}  {tally['x']}", (16, 22), 2, gs.NEON_RED, "midleft")
        blit_pixel_text(screen, f"PARI {tally['draw']}", (W // 2, 22), 2, gs.TEXT_DIM, "center")
        blit_pixel_text(screen, f"{tally['o']}  {right}", (W - 16, 22), 2, gs.NEON_BLUE, "midright")
        # grid
        for i in (1, 2):
            x = OFF_X + i * CELL
            y = OFF_Y + i * CELL
            for color, width in (((40, 60, 120), 14), (gs.NEON_PURPLE, 5)):
                pygame.draw.line(screen, color, (x, OFF_Y + 8), (x, OFF_Y + BOARD - 8), width)
                pygame.draw.line(screen, color, (OFF_X + 8, y), (OFF_X + BOARD - 8, y), width)
        board = state["board"]
        winning = set(state["line"] or [])
        for r in range(3):
            for c in range(3):
                mark = board[r][c]
                rect = cell_rect(r, c)
                if mark is None:
                    continue
                if (r, c) in winning:
                    pulse = 0.5 + 0.5 * math.sin(t * 8)
                    glow = pygame.Surface(rect.size, pygame.SRCALPHA)
                    pygame.draw.rect(glow, (255, 230, 60, int(40 + 50 * pulse)),
                                     glow.get_rect().inflate(-10, -10), border_radius=16)
                    screen.blit(glow, rect)
                progress = (t - state["placed"].get((r, c), -1)) / STROKE_TIME
                draw_mark(screen, mark, rect, progress)
        # hover preview / keyboard cursor
        if human_turn():
            target = state["hover"] or state["cursor"]
            r, c = target
            if board[r][c] is None:
                draw_mark(screen, state["turn"], cell_rect(r, c), 1.0, alpha=70)
            pygame.draw.rect(screen, gs.NEON_YELLOW, cell_rect(*state["cursor"]).inflate(-14, -14), 2,
                             border_radius=12)
        # winning line
        if state["line"]:
            a = cell_rect(*state["line"][0]).center
            b = cell_rect(*state["line"][2]).center
            p = min(1.0, (t - state["line_t"]) / 0.35)
            end = (a[0] + (b[0] - a[0]) * p, a[1] + (b[1] - a[1]) * p)
            pygame.draw.line(screen, (255, 230, 60), a, end, 18)
            pygame.draw.line(screen, gs.WHITE, a, end, 6)
        particles.draw(screen)
        # status line
        if state["over"]:
            winner = state["winner"]
            if winner == 0:
                text, color = "PAREGGIO!", gs.NEON_YELLOW
            elif vs_cpu and winner == 1:
                text, color = "HAI VINTO!", gs.NEON_GREEN
            elif vs_cpu:
                text, color = "VINCE LA CPU!", gs.NEON_MAGENTA
            else:
                text, color = ("VINCE X!", gs.NEON_RED) if winner == 1 else ("VINCE O!", gs.NEON_BLUE)
            box = pygame.Rect(0, 0, 520, 64)
            box.midbottom = (W // 2, H - 6)
            gs.draw_panel(screen, box, color, fill_alpha=230)
            blit_pixel_text(screen, text, (W // 2, box.y + 20), 3, color, "center")
            blit_pixel_text(screen, "INVIO / CLIC: NUOVA PARTITA   ESC: PAUSA", (W // 2, box.y + 46), 1,
                            gs.TEXT_DIM, "center")
        else:
            if vs_cpu and state["turn"] == -1:
                dots = "." * (1 + int(t * 4) % 3)
                msg, color = f"LA CPU STA PENSANDO{dots}", gs.NEON_BLUE
            else:
                who = "X" if state["turn"] == 1 else "O"
                msg = f"TOCCA A {who}" if not vs_cpu else "TOCCA A TE (X)"
                color = gs.NEON_RED if state["turn"] == 1 else gs.NEON_BLUE
            blit_pixel_text(screen, msg, (W // 2, H - 22), 2, color, "center")

    new_round(alternate=False)
    while True:
        dt = clock.tick()
        t += dt
        for e in pygame.event.get():
            if gs.handle_global_event(e):
                continue
            if e.type == pygame.QUIT:
                return "quit"
            if e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_ESCAPE, pygame.K_p):
                    choice = gs.in_game_menu(screen, "Tic Tac Toe", COMMANDS)
                    clock.reset()
                    if choice in ("menu", "quit"):
                        return choice
                    if choice == "restart":
                        new_round(alternate=False)
                elif e.key == pygame.K_r:
                    new_round(alternate=False)
                elif e.key == pygame.K_TAB:
                    vs_cpu = not vs_cpu
                    gs.notify("MODALITÀ: VS CPU" if vs_cpu else "MODALITÀ: 2 GIOCATORI")
                    new_round(alternate=False)
                elif e.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                    level = LEVELS[e.key - pygame.K_1]
                    ai = GameAI.for_level(level, player_id=-1)
                    gs.notify(f"CPU: {LEVEL_NAMES[level]}")
                elif state["over"] and e.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
                    new_round()
                elif e.key in (pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT,
                               pygame.K_w, pygame.K_s, pygame.K_a, pygame.K_d):
                    dr = {pygame.K_UP: -1, pygame.K_w: -1, pygame.K_DOWN: 1, pygame.K_s: 1}.get(e.key, 0)
                    dc = {pygame.K_LEFT: -1, pygame.K_a: -1, pygame.K_RIGHT: 1, pygame.K_d: 1}.get(e.key, 0)
                    r, c = state["cursor"]
                    state["cursor"] = ((r + dr) % 3, (c + dc) % 3)
                    state["hover"] = None
                elif e.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER) and human_turn():
                    place(*state["cursor"])
            elif e.type == pygame.MOUSEMOTION:
                state["hover"] = None
                for r in range(3):
                    for c in range(3):
                        if cell_rect(r, c).collidepoint(e.pos):
                            state["hover"] = (r, c)
                            state["cursor"] = (r, c)
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                if state["over"]:
                    new_round()
                    continue
                if not human_turn():
                    continue
                for r in range(3):
                    for c in range(3):
                        if cell_rect(r, c).collidepoint(e.pos):
                            place(r, c)

        # CPU move after a short, non-blocking "thinking" pause
        if vs_cpu and not state["over"] and state["turn"] == -1:
            state["cpu_timer"] -= dt
            if state["cpu_timer"] <= 0:
                move = ai.get_best_move(TicTacToeState(state["board"], current_player=-1))
                if move is not None:
                    place(*move)
                clock.reset()

        particles.update(dt)
        draw()
        gs.present(screen)


def tris_game(load_scores: Callable[[], dict], save_scores: Callable[[dict], None]) -> str:
    """Backwards-compatible entry point (old launcher signature)."""
    return main(load_scores, save_scores)


if __name__ == "__main__":
    main()
    gs.shutdown()
