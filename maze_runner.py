# maze_runner.py
"""
Maze Runner - Improved version with difficulty levels, move counter, timer, and breadcrumbs.
"""
import pygame
import random
from typing import List, Tuple, Set
from game_shared import safe_font, BG, in_game_menu

W, H = 800, 600

COMMANDS = [
    "Muovi con frecce o WASD",
    "Trova l'uscita",
    "ESC: menu"
]


def generate_maze(cols: int, rows: int) -> List[List[int]]:
    """Generate a solvable maze using depth-first search.

    Args:
        cols: Number of columns in the maze.
        rows: Number of rows in the maze.

    Returns:
        List[List[int]]: Grid where 0 is passable, 1 is wall.
    """
    grid = [[1] * cols for _ in range(rows)]
    stack = []
    cx, cy = 0, 0
    grid[cy][cx] = 0
    stack.append((cx, cy))
    while stack:
        x, y = stack[-1]
        neighbors = []
        for dx, dy in [(2, 0), (-2, 0), (0, 2), (0, -2)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < cols and 0 <= ny < rows and grid[ny][nx] == 1:
                neighbors.append((nx, ny))
        if neighbors:
            nx, ny = random.choice(neighbors)
            grid[(y + ny) // 2][(x + nx) // 2] = 0
            grid[ny][nx] = 0
            stack.append((nx, ny))
        else:
            stack.pop()
    return grid


def is_on_goal(p: Tuple[int, int], goal: Tuple[int, int]) -> bool:
    """Check if player is on the goal cell.

    Args:
        p: Player position (x, y).
        goal: Goal position (x, y).

    Returns:
        bool: True if player is on goal.
    """
    return p == goal


def get_difficulty_params(difficulty: str) -> Tuple[int, int]:
    """Get maze dimensions based on difficulty level.

    Args:
        difficulty: "small", "medium", or "large".

    Returns:
        Tuple[int, int]: (cols, rows) for the maze.
    """
    if difficulty == "small":
        return (21, 15)
    elif difficulty == "medium":
        return (31, 21)
    else:  # large
        return (39, 29)


def main(difficulty: str = "medium") -> str:
    """Main game loop for Maze Runner.

    Args:
        difficulty: Maze difficulty level ("small", "medium", "large").

    Returns:
        str: Game state command ("menu", "quit", etc.)
    """
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Maze Runner")
    clock = pygame.time.Clock()
    font = safe_font("consolas", 18)

    cols, rows = get_difficulty_params(difficulty)
    grid = generate_maze(cols, rows)
    cell_w = W // cols
    cell_h = (H - 120) // rows

    start: Tuple[int, int] = (0, 0)
    # Goal must be on even coordinates (DFS only carves even-coordinate cells)
    goal_x = cols - 1 if (cols - 1) % 2 == 0 else cols - 2
    goal_y = rows - 1 if (rows - 1) % 2 == 0 else rows - 2
    goal: Tuple[int, int] = (goal_x, goal_y)

    # Force goal and its neighbors passable so the player can reach it
    grid[goal_y][goal_x] = 0
    if goal_y > 0 and grid[goal_y - 1][goal_x] == 1:
        grid[goal_y - 1][goal_x] = 0
    if goal_x > 0 and grid[goal_y][goal_x - 1] == 1:
        grid[goal_y][goal_x - 1] = 0
    px, py = start

    # Game state
    move_counter: int = 0
    start_time: int = pygame.time.get_ticks()
    visited_cells: Set[Tuple[int, int]] = {(px, py)}

    running: bool = True
    while running:
        dt: float = clock.tick(30)

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return "menu"
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    choice = in_game_menu(screen, "Maze Runner", COMMANDS, font, font)
                    if choice == "menu":
                        return "menu"
                    if choice == "quit":
                        pygame.quit()
                        return "quit"
                    if choice == "restart":
                        return main(difficulty)

                # Movement
                moved: bool = False
                if e.key in (pygame.K_w, pygame.K_UP) and py - 1 >= 0 and grid[py - 1][px] == 0:
                    py -= 1
                    moved = True
                if e.key in (pygame.K_s, pygame.K_DOWN) and py + 1 < rows and grid[py + 1][px] == 0:
                    py += 1
                    moved = True
                if e.key in (pygame.K_a, pygame.K_LEFT) and px - 1 >= 0 and grid[py][px - 1] == 0:
                    px -= 1
                    moved = True
                if e.key in (pygame.K_d, pygame.K_RIGHT) and px + 1 < cols and grid[py][px + 1] == 0:
                    px += 1
                    moved = True

                if moved:
                    move_counter += 1
                    visited_cells.add((px, py))

                # Check win - player walks onto goal
                if is_on_goal((px, py), goal):
                    elapsed_time = (pygame.time.get_ticks() - start_time) // 1000
                    choice = in_game_menu(
                        screen,
                        f"Completo! Mosse: {move_counter} Tempo: {elapsed_time}s",
                        ["Restart", "Menu"],
                        font,
                        font
                    )
                    if choice == "restart":
                        return main(difficulty)
                    return "menu"

        # Draw
        screen.fill(BG)
        offset_y = 80
        for y in range(rows):
            for x in range(cols):
                color = (40, 40, 60) if grid[y][x] else (20, 20, 40)
                pygame.draw.rect(screen, color, (x * cell_w, offset_y + y * cell_h, cell_w, cell_h))

        # Draw visited cells (breadcrumbs)
        for vx, vy in visited_cells:
            if (vx, vy) != (px, py):  # Don't draw on player
                pygame.draw.rect(screen, (50, 50, 70),
                               (vx * cell_w + 2, offset_y + vy * cell_h + 2, cell_w - 4, cell_h - 4))

        # Draw player
        pygame.draw.rect(screen, (240, 200, 80), (px * cell_w + 2, offset_y + py * cell_h + 2, cell_w - 4, cell_h - 4))

        # Draw goal
        gx, gy = goal
        pygame.draw.rect(screen, (80, 220, 120), (gx * cell_w + 2, offset_y + gy * cell_h + 2, cell_w - 4, cell_h - 4))

        # Draw UI
        elapsed_time = (pygame.time.get_ticks() - start_time) // 1000
        info = font.render(f"Moves: {move_counter}  Time: {elapsed_time}s  Difficulty: {difficulty.upper()}",
                          True, (220, 220, 100))
        screen.blit(info, (10, 40))

        hint = font.render("Find the exit (walk onto the green cell)", True, (220, 220, 220))
        screen.blit(hint, (10, 10))
        pygame.display.flip()

    pygame.quit()
    return "menu"


if __name__ == "__main__":
    main()
