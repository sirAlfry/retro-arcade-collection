# tetris.py
"""
Tetris game with advanced features: next piece preview, ghost piece, progressive difficulty,
level system, line clear animations, and hold piece functionality.
"""
import pygame
import random
import time
from typing import Callable, Dict, List, Tuple, Optional

from game_shared import safe_font, BG

W, H = 800, 600
COLUMNS = 10
ROWS = 20
CELL = 24
BOARD_W = COLUMNS * CELL
BOARD_H = ROWS * CELL
OFF_X = (W - BOARD_W) // 2
OFF_Y = 80

PREVIEW_X = OFF_X + BOARD_W + 20
PREVIEW_Y = OFF_Y

COMMANDS = [
    "Frecce: muovi, UP: ruota, SPACE: drop",
    "C: hold | R: ricomincia | ESC: Menu"
]

SHAPES = [
    [[1, 1, 1, 1]],
    [[1, 1], [1, 1]],
    [[0, 1, 1], [1, 1, 0]],
    [[1, 1, 0], [0, 1, 1]],
    [[1, 0, 0], [1, 1, 1]],
    [[0, 0, 1], [1, 1, 1]],
    [[0, 1, 0], [1, 1, 1]]
]

COLORS = [
    (200, 40, 40), (40, 120, 220), (220, 200, 30), (60, 200, 80),
    (200, 100, 40), (160, 60, 200), (80, 180, 220)
]


def rotate(shape: List[List[int]]) -> List[List[int]]:
    """Rotate a tetromino shape 90 degrees clockwise."""
    return [list(row) for row in zip(*shape[::-1])]


def tetris_game(load_scores: Callable, save_scores: Callable) -> str:
    """
    Main Tetris game loop.

    Args:
        load_scores: Function to load high scores dictionary
        save_scores: Function to save high scores dictionary

    Returns:
        "menu" to return to main menu, "quit" to exit application
    """
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Tetris")
    clock = pygame.time.Clock()

    title_font = safe_font("consolas", 22)
    small_font = safe_font("consolas", 14)
    tiny_font = safe_font("consolas", 12)

    board: List[List[int]] = [[0] * COLUMNS for _ in range(ROWS)]

    def spawn_piece() -> Dict:
        """Create a new random tetromino piece."""
        idx = random.randrange(len(SHAPES))
        shape = SHAPES[idx]
        return {
            "shape": [row[:] for row in shape],
            "x": COLUMNS // 2 - len(shape[0]) // 2,
            "y": 0,
            "color": COLORS[idx]
        }

    def get_next_piece_preview() -> Dict:
        """Generate the next piece to be spawned (includes x/y for use as curr)."""
        idx = random.randrange(len(SHAPES))
        shape = SHAPES[idx]
        return {
            "shape": [row[:] for row in shape],
            "x": COLUMNS // 2 - len(shape[0]) // 2,
            "y": 0,
            "color": COLORS[idx]
        }

    curr = spawn_piece()
    next_piece = get_next_piece_preview()
    held_piece: Optional[Dict] = None
    can_hold = True

    fall_timer: float = 0.0
    fall_interval: float = 0.6
    score: int = 0
    lines_cleared_total: int = 0
    level: int = 1
    line_clear_timer: float = 0.0
    lines_to_flash: List[int] = []
    game_over_flag: bool = False

    def collide(shape: List[List[int]], x: int, y: int) -> bool:
        """Check if a shape at position (x, y) collides with the board or boundaries."""
        for r, row in enumerate(shape):
            for c, cell in enumerate(row):
                if not cell:
                    continue
                rr = y + r
                cc = x + c
                if rr < 0 or rr >= ROWS or cc < 0 or cc >= COLUMNS:
                    return True
                if board[rr][cc]:
                    return True
        return False

    def place(shape: List[List[int]], x: int, y: int, color: Tuple[int, int, int]) -> None:
        """Place a shape on the board at position (x, y)."""
        for r, row in enumerate(shape):
            for c, cell in enumerate(row):
                if cell:
                    board[y + r][x + c] = color

    def get_ghost_position(shape: List[List[int]], x: int, y: int) -> int:
        """Calculate the final y position where the piece will land (ghost piece)."""
        ghost_y = y
        while not collide(shape, x, ghost_y + 1):
            ghost_y += 1
        return ghost_y

    def clear_lines() -> int:
        """
        Clear completed lines and return the number of lines cleared.
        Triggers line flash animation.
        """
        nonlocal board, score, lines_cleared_total, level, line_clear_timer, lines_to_flash

        full_rows = []
        for r in range(ROWS):
            if all(v != 0 for v in board[r]):
                full_rows.append(r)

        lines_cleared = len(full_rows)
        if lines_cleared:
            lines_to_flash = full_rows[:]
            line_clear_timer = 0.2

            # Update score with bonus for multiple lines
            score += {1: 40, 2: 100, 3: 300, 4: 1200}.get(lines_cleared, lines_cleared * 50)
            lines_cleared_total += lines_cleared

            # Update level every 10 lines
            new_level = 1 + lines_cleared_total // 10
            if new_level > level:
                level = new_level
                # Increase speed with each level
                update_fall_interval()

        return lines_cleared

    def update_fall_interval() -> None:
        """Update fall interval based on score (progressive difficulty)."""
        nonlocal fall_interval
        # Every 500 points: fall_interval decreases
        score_level = score // 500
        fall_interval = max(0.1, 0.6 - (score_level * 0.05))

    running = True
    while running:
        dt = clock.tick(30) / 1000.0
        fall_timer += dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "menu"
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    from game_shared import in_game_menu
                    choice = in_game_menu(screen, "Tetris", COMMANDS, title_font, small_font)
                    if choice == "menu":
                        return "menu"
                    if choice == "quit":
                        pygame.quit()
                        return "quit"
                    if choice == "restart":
                        board = [[0] * COLUMNS for _ in range(ROWS)]
                        curr = spawn_piece()
                        next_piece = get_next_piece_preview()
                        held_piece = None
                        can_hold = True
                        score = 0
                        lines_cleared_total = 0
                        level = 1
                        fall_interval = 0.6
                        game_over_flag = False
                elif event.key == pygame.K_LEFT:
                    nx = curr["x"] - 1
                    if not collide(curr["shape"], nx, curr["y"]):
                        curr["x"] = nx
                elif event.key == pygame.K_RIGHT:
                    nx = curr["x"] + 1
                    if not collide(curr["shape"], nx, curr["y"]):
                        curr["x"] = nx
                elif event.key == pygame.K_UP:
                    ns = rotate(curr["shape"])
                    if not collide(ns, curr["x"], curr["y"]):
                        curr["shape"] = ns
                elif event.key == pygame.K_SPACE:
                    while not collide(curr["shape"], curr["x"], curr["y"] + 1):
                        curr["y"] += 1
                    place(curr["shape"], curr["x"], curr["y"], curr["color"])
                    clear_lines()
                    curr = next_piece
                    next_piece = get_next_piece_preview()
                    can_hold = True
                elif event.key == pygame.K_c:
                    if can_hold:
                        if held_piece is None:
                            held_piece = curr
                            curr = next_piece
                            next_piece = get_next_piece_preview()
                        else:
                            held_piece, curr = curr, held_piece
                            curr["x"] = COLUMNS // 2 - len(curr["shape"][0]) // 2
                            curr["y"] = 0
                        can_hold = False

        # Handle line clear animation
        if lines_to_flash and line_clear_timer > 0:
            line_clear_timer -= dt
            if line_clear_timer <= 0:
                # Remove the flashing lines
                newb = [row for row in board if any(v == 0 for v in row)]
                for _ in range(len(lines_to_flash)):
                    newb.insert(0, [0] * COLUMNS)
                board = newb
                lines_to_flash = []

        if fall_timer >= fall_interval:
            fall_timer = 0
            if not collide(curr["shape"], curr["x"], curr["y"] + 1):
                curr["y"] += 1
            else:
                if curr["y"] <= 0:
                    # Game over
                    scores = load_scores()
                    if score > scores.get("tetris", 0):
                        scores["tetris"] = score
                        save_scores(scores)

                    screen.fill(BG)
                    go = title_font.render("GAME OVER", True, (240, 200, 80))
                    scr = small_font.render(
                        f"Score: {score}  |  Level: {level}  |  R: restart  |  ESC: menu",
                        True, (220, 220, 220)
                    )
                    screen.blit(go, (W // 2 - go.get_width() // 2, H // 2 - 24))
                    screen.blit(scr, (W // 2 - scr.get_width() // 2, H // 2 + 12))
                    pygame.display.flip()

                    waiting = True
                    while waiting:
                        for e in pygame.event.get():
                            if e.type == pygame.QUIT:
                                return "menu"
                            if e.type == pygame.KEYDOWN:
                                if e.key == pygame.K_r:
                                    board = [[0] * COLUMNS for _ in range(ROWS)]
                                    curr = spawn_piece()
                                    next_piece = get_next_piece_preview()
                                    held_piece = None
                                    can_hold = True
                                    score = 0
                                    lines_cleared_total = 0
                                    level = 1
                                    fall_interval = 0.6
                                    waiting = False
                                if e.key == pygame.K_ESCAPE:
                                    return "menu"
                    continue

                place(curr["shape"], curr["x"], curr["y"], curr["color"])
                clear_lines()
                curr = next_piece
                next_piece = get_next_piece_preview()
                can_hold = True

        # Update fall interval based on score
        update_fall_interval()

        # Render
        screen.fill(BG)

        # Draw board border
        pygame.draw.rect(screen, (8, 8, 12), (OFF_X - 4, OFF_Y - 4, BOARD_W + 8, BOARD_H + 8),
                        border_radius=6)

        # Draw board cells
        for r in range(ROWS):
            for c in range(COLUMNS):
                v = board[r][c]
                if v:
                    pygame.draw.rect(screen, v, (OFF_X + c * CELL, OFF_Y + r * CELL, CELL - 1, CELL - 1))

        # Draw ghost piece (transparent preview)
        ghost_y = get_ghost_position(curr["shape"], curr["x"], curr["y"])
        for r, row in enumerate(curr["shape"]):
            for c, cell in enumerate(row):
                if cell:
                    px = OFF_X + (curr["x"] + c) * CELL
                    py = OFF_Y + (ghost_y + r) * CELL
                    # Draw semi-transparent ghost
                    ghost_color = tuple(int(v * 0.3) for v in curr["color"])
                    pygame.draw.rect(screen, ghost_color, (px, py, CELL - 1, CELL - 1))

        # Draw current piece
        for r, row in enumerate(curr["shape"]):
            for c, cell in enumerate(row):
                if cell:
                    px = OFF_X + (curr["x"] + c) * CELL
                    py = OFF_Y + (curr["y"] + r) * CELL
                    # Flash effect during line clear
                    if lines_to_flash and line_clear_timer > 0:
                        color = curr["color"] if int(line_clear_timer * 10) % 2 else (100, 100, 100)
                    else:
                        color = curr["color"]
                    pygame.draw.rect(screen, color, (px, py, CELL - 1, CELL - 1))

        # Draw HUD: Score and Level
        sc = small_font.render(f"SCORE: {score}", True, (180, 240, 180))
        screen.blit(sc, (10, 10))

        lv = small_font.render(f"LEVEL: {level}", True, (180, 240, 180))
        screen.blit(lv, (10, 40))

        ln = small_font.render(f"LINES: {lines_cleared_total}", True, (180, 240, 180))
        screen.blit(ln, (10, 70))

        # Draw next piece preview
        preview_label = small_font.render("NEXT", True, (180, 240, 180))
        screen.blit(preview_label, (PREVIEW_X, PREVIEW_Y))

        pygame.draw.rect(screen, (8, 8, 12), (PREVIEW_X - 2, PREVIEW_Y + 24, 80, 80), border_radius=4)
        for r, row in enumerate(next_piece["shape"]):
            for c, cell in enumerate(row):
                if cell:
                    px = PREVIEW_X + 6 + c * 16
                    py = PREVIEW_Y + 30 + r * 16
                    pygame.draw.rect(screen, next_piece["color"], (px, py, 14, 14))

        # Draw held piece
        hold_label = small_font.render("HOLD", True, (180, 240, 180))
        screen.blit(hold_label, (PREVIEW_X, PREVIEW_Y + 120))

        pygame.draw.rect(screen, (8, 8, 12), (PREVIEW_X - 2, PREVIEW_Y + 144, 80, 80), border_radius=4)
        if held_piece:
            for r, row in enumerate(held_piece["shape"]):
                for c, cell in enumerate(row):
                    if cell:
                        px = PREVIEW_X + 6 + c * 16
                        py = PREVIEW_Y + 150 + r * 16
                        pygame.draw.rect(screen, held_piece["color"], (px, py, 14, 14))

        pygame.display.flip()

    return "menu"
