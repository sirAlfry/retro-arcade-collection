# puzzle15.py
"""
Puzzle 15 - Improved version with move counter, timer, tile animation, and congratulations screen.
"""
import pygame
import random
from typing import List, Tuple, Optional
from game_shared import safe_font, BG

W, H = 800, 600

COMMANDS = [
    "Clicca su una tessera adiacente per muoverla",
    "Usa frecce per muovere il buco",
    "ESC: menu"
]


class PuzzleGame:
    """Puzzle 15 game class with animations and statistics."""

    def __init__(self) -> None:
        """Initialize the puzzle game."""
        pygame.init()
        self.screen = pygame.display.set_mode((W, H))
        pygame.display.set_caption("Puzzle 15")
        self.clock = pygame.time.Clock()
        self.title_font = safe_font("consolas", 18)
        self.large_font = safe_font("consolas", 30)
        self.small_font = safe_font("consolas", 14)

        self.SIZE: int = 100
        self.GAP: int = 10
        self.OFFSET_X: int = (W - self.SIZE * 4 - self.GAP * 3) // 2
        self.OFFSET_Y: int = 90

        # Animation tracking
        self.animating: bool = False
        self.anim_start_time: float = 0.0
        self.anim_duration: float = 0.3
        self.anim_from_pos: Tuple[int, int] = (0, 0)
        self.anim_to_pos: Tuple[int, int] = (0, 0)
        self.anim_tile_value: Optional[int] = None

    def shuffle_board(self) -> List[List[Optional[int]]]:
        """Generate a shuffled but solvable puzzle board.

        Returns:
            List[List[Optional[int]]]: 4x4 board with numbers 1-15 and one None.
        """
        vals = list(range(1, 16)) + [None]
        while True:
            random.shuffle(vals)
            inv = sum(1 for i in range(16) for j in range(i + 1, 16)
                      if vals[i] and vals[j] and vals[i] > vals[j])
            empty_row_from_top = vals.index(None) // 4
            empty_row_from_bottom = 4 - empty_row_from_top
            if (inv + empty_row_from_bottom) % 2 == 0:
                break
        board = [vals[i * 4:(i + 1) * 4] for i in range(4)]
        return board

    def draw(self, board: List[List[Optional[int]]], move_counter: int, elapsed_time: int) -> None:
        """Draw the puzzle board and UI.

        Args:
            board: The 4x4 puzzle board.
            move_counter: Number of moves made.
            elapsed_time: Elapsed time in seconds.
        """
        self.screen.fill(BG)
        size = self.SIZE
        gap = self.GAP
        offset_x = self.OFFSET_X
        offset_y = self.OFFSET_Y

        for r in range(4):
            for c in range(4):
                val = board[r][c]
                x = offset_x + c * (size + gap)
                y = offset_y + r * (size + gap)
                rect = pygame.Rect(x, y, size, size)

                if val is None:
                    pygame.draw.rect(self.screen, (12, 12, 18), rect)
                else:
                    # Check if this tile is being animated
                    if (self.animating and self.anim_tile_value == val and
                        (r * 4 + c) == self._get_board_index(val, board)):
                        # Draw animation
                        progress = min(1.0,
                                      (pygame.time.get_ticks() - self.anim_start_time) / (self.anim_duration * 1000))
                        anim_x = self.anim_from_pos[0] + (self.anim_to_pos[0] - self.anim_from_pos[0]) * progress
                        anim_y = self.anim_from_pos[1] + (self.anim_to_pos[1] - self.anim_from_pos[1]) * progress
                        tile_rect = pygame.Rect(int(anim_x), int(anim_y), size, size)
                    else:
                        tile_rect = rect

                    pygame.draw.rect(self.screen, (80, 80, 80), tile_rect)
                    txt = self.large_font.render(str(val), True, (240, 240, 240))
                    self.screen.blit(txt,
                                   (int(tile_rect.x + size // 2 - txt.get_width() // 2),
                                    int(tile_rect.y + size // 2 - txt.get_height() // 2)))

        # Draw UI
        info = self.title_font.render(f"Moves: {move_counter}  Time: {elapsed_time}s",
                                     True, (200, 200, 200))
        self.screen.blit(info, (10, 10))

        instructions = self.small_font.render("Click tiles or use arrow keys to move",
                                            True, (150, 150, 150))
        self.screen.blit(instructions, (10, 35))

        pygame.display.flip()

    def _get_board_index(self, val: int, board: List[List[Optional[int]]]) -> int:
        """Get the board index (0-15) of a tile value.

        Args:
            val: Tile value to find.
            board: The puzzle board.

        Returns:
            int: Index on the board (0-15).
        """
        for r in range(4):
            for c in range(4):
                if board[r][c] == val:
                    return r * 4 + c
        return -1

    def run(self) -> str:
        """Run the puzzle game loop.

        Returns:
            str: Game state command ("menu", "quit", etc.)
        """
        board = self.shuffle_board()
        move_counter: int = 0
        start_time: int = pygame.time.get_ticks()

        running: bool = True
        while running:
            self.clock.tick(60)
            elapsed_time: int = (pygame.time.get_ticks() - start_time) // 1000

            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    return "menu"
                if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                    from game_shared import open_exit_menu
                    res = open_exit_menu(
                        self.screen,
                        "Puzzle 15",
                        COMMANDS,
                        self.title_font,
                        self.title_font
                    )
                    if res == "restart":
                        board = self.shuffle_board()
                        move_counter = 0
                        start_time = pygame.time.get_ticks()
                    else:
                        return res

                # Arrow key controls
                if e.type == pygame.KEYDOWN:
                    er, ec = -1, -1
                    for i in range(4):
                        for j in range(4):
                            if board[i][j] is None:
                                er, ec = i, j
                                break

                    if e.key == pygame.K_UP and er + 1 < 4:
                        board[er][ec], board[er + 1][ec] = board[er + 1][ec], board[er][ec]
                        move_counter += 1
                    elif e.key == pygame.K_DOWN and er - 1 >= 0:
                        board[er][ec], board[er - 1][ec] = board[er - 1][ec], board[er][ec]
                        move_counter += 1
                    elif e.key == pygame.K_LEFT and ec + 1 < 4:
                        board[er][ec], board[er][ec + 1] = board[er][ec + 1], board[er][ec]
                        move_counter += 1
                    elif e.key == pygame.K_RIGHT and ec - 1 >= 0:
                        board[er][ec], board[er][ec - 1] = board[er][ec - 1], board[er][ec]
                        move_counter += 1

                # Click controls
                if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                    mx, my = e.pos
                    size = self.SIZE
                    gap = self.GAP
                    offset_x = self.OFFSET_X
                    offset_y = self.OFFSET_Y

                    # Find empty position
                    er, ec = -1, -1
                    for i in range(4):
                        for j in range(4):
                            if board[i][j] is None:
                                er, ec = i, j
                                break

                    # Check which tile was clicked
                    for r in range(4):
                        for c in range(4):
                            x = offset_x + c * (size + gap)
                            y = offset_y + r * (size + gap)
                            rect = pygame.Rect(x, y, size, size)
                            if rect.collidepoint(mx, my):
                                # Only allow adjacent tiles to swap
                                if abs(er - r) + abs(ec - c) == 1:
                                    self.animating = True
                                    self.anim_start_time = pygame.time.get_ticks()
                                    self.anim_from_pos = (x, y)
                                    self.anim_to_pos = (offset_x + ec * (size + gap),
                                                       offset_y + er * (size + gap))
                                    self.anim_tile_value = board[r][c]

                                    board[er][ec], board[r][c] = board[r][c], board[er][ec]
                                    move_counter += 1

            # Check if animation has finished
            if self.animating:
                if pygame.time.get_ticks() - self.anim_start_time > self.anim_duration * 1000:
                    self.animating = False

            self.draw(board, move_counter, elapsed_time)

            # Check win condition
            flat = [cell for row in board for cell in row]
            if flat[:-1] == list(range(1, 16)):
                pygame.time.delay(500)

                # Show congratulations screen
                self.screen.fill(BG)
                title = self.large_font.render("Puzzle Completato!", True, (240, 200, 80))
                moves_txt = self.title_font.render(f"Mosse: {move_counter}", True, (180, 240, 180))
                time_txt = self.title_font.render(f"Tempo: {elapsed_time}s", True, (180, 240, 180))
                prompt = self.title_font.render("R: ricomincia  |  ESC: menu", True, (220, 220, 220))

                self.screen.blit(title, (W // 2 - title.get_width() // 2, H // 2 - 80))
                self.screen.blit(moves_txt, (W // 2 - moves_txt.get_width() // 2, H // 2 - 20))
                self.screen.blit(time_txt, (W // 2 - time_txt.get_width() // 2, H // 2 + 20))
                self.screen.blit(prompt, (W // 2 - prompt.get_width() // 2, H // 2 + 80))
                pygame.display.flip()

                waiting: bool = True
                while waiting:
                    for ev in pygame.event.get():
                        if ev.type == pygame.QUIT:
                            return "menu"
                        if ev.type == pygame.KEYDOWN:
                            if ev.key == pygame.K_r:
                                board = self.shuffle_board()
                                move_counter = 0
                                start_time = pygame.time.get_ticks()
                                waiting = False
                            if ev.key == pygame.K_ESCAPE:
                                return "menu"

        return "menu"


def main() -> str:
    """Entry point wrapper for Puzzle 15 (used by the game launcher)."""
    return PuzzleGame().run()


if __name__ == "__main__":
    main()
