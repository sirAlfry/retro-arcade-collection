# tris.py
"""
Tic Tac Toe - Improved version with timer-based AI thinking, winning line animation, and score tracking.
"""
import pygame
import random
from typing import Callable, Optional, List, Tuple
from game_ai import GameAI, TicTacToeState
from game_shared import safe_font, BG

W, H = 800, 600

COMMANDS = [
    "Clicca per posizionare X/O",
    "TAB: cambia modalità (1P / 2P / VS AI)",
    "R: Ricomincia | ESC: Menu"
]


def difficulty_label(d: int) -> str:
    """Get difficulty label for AI difficulty level.

    Args:
        d: Difficulty value.

    Returns:
        str: Human-readable difficulty label.
    """
    if d <= 1:
        return "FACILE"
    if d <= 3:
        return "MEDIO"
    return "DIFFICILE"


def tris_game(load_scores: Callable, save_scores: Callable) -> str:
    """Tic Tac Toe game with AI opponent and score tracking.

    Args:
        load_scores: Function to load game scores.
        save_scores: Function to save game scores.

    Returns:
        str: Game state command ("menu", "quit", etc.)
    """
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Tic Tac Toe")
    clock = pygame.time.Clock()

    title_font = safe_font("consolas", 28)
    small_font = safe_font("consolas", 18)

    mode: str = "1P"
    ai_difficulty: int = 3
    ai = GameAI("minimax", difficulty=ai_difficulty, player_id=-1)

    # Score tracking
    scores_data: dict = load_scores()
    x_wins: int = scores_data.get("tris_x", 0)
    o_wins: int = scores_data.get("tris_o", 0)
    draws: int = scores_data.get("tris_draw", 0)

    # AI thinking timer
    ai_thinking: bool = False
    ai_think_start: int = 0
    ai_think_duration: int = 800  # milliseconds

    # Winning line animation
    winning_line: Optional[List[Tuple[int, int]]] = None
    winning_line_time: int = 0

    def draw_board(board: List[List[Optional[int]]], turn: int) -> None:
        """Draw the game board and UI.

        Args:
            board: 3x3 board state.
            turn: Current player (1 for X, -1 for O).
        """
        screen.fill(BG)
        margin: int = 160
        size: int = 480
        cell: int = size // 3

        # Draw grid
        for i in range(1, 3):
            pygame.draw.line(screen, (100, 120, 160), (margin + i * cell, margin),
                           (margin + i * cell, margin + size), 6)
            pygame.draw.line(screen, (100, 120, 160), (margin, margin + i * cell),
                           (margin + size, margin + i * cell), 6)

        # Draw X and O
        f = safe_font("consolas", 56, bold=True)
        for r in range(3):
            for c in range(3):
                val = board[r][c]
                if val is None:
                    continue
                ch = "X" if val == 1 else "O"
                txt = f.render(ch, True, (230, 50, 50) if ch == "X" else (90, 140, 255))
                pos = (margin + c * cell + cell // 2 - txt.get_width() // 2,
                      margin + r * cell + cell // 2 - txt.get_height() // 2)
                screen.blit(txt, pos)

        # Draw winning line if exists
        if winning_line:
            elapsed = pygame.time.get_ticks() - winning_line_time
            if elapsed < 1500:  # Show animation for 1.5 seconds
                alpha = int(255 * (1 - elapsed / 1500.0))  # Fade out
                line_surface = pygame.Surface((W, H), pygame.SRCALPHA)
                if len(winning_line) == 2:
                    x1 = margin + winning_line[0][1] * cell + cell // 2
                    y1 = margin + winning_line[0][0] * cell + cell // 2
                    x2 = margin + winning_line[1][1] * cell + cell // 2
                    y2 = margin + winning_line[1][0] * cell + cell // 2
                    pygame.draw.line(line_surface, (255, 255, 0, alpha), (x1, y1), (x2, y2), 8)
                screen.blit(line_surface, (0, 0))

        # Draw AI thinking indicator
        if ai_thinking:
            elapsed = pygame.time.get_ticks() - ai_think_start
            if elapsed < ai_think_duration:
                dots = int((elapsed / ai_think_duration) * 3) + 1
                thinking = small_font.render("AI thinking" + "." * dots, True, (200, 150, 80))
                screen.blit(thinking, (W // 2 - thinking.get_width() // 2, 520))

        # Draw status
        status = f"Turno: {'X' if turn == 1 else 'O'}  |  Modalità: {mode}  |  AI: {difficulty_label(ai_difficulty)}"
        st = small_font.render(status, True, (220, 220, 220))
        screen.blit(st, (W // 2 - st.get_width() // 2, 40))

        # Draw score
        score_text = f"X:{x_wins}  O:{o_wins}  DRAW:{draws}"
        score = small_font.render(score_text, True, (180, 220, 180))
        screen.blit(score, (10, 10))

        pygame.display.flip()

    board: List[List[Optional[int]]] = [[None] * 3 for _ in range(3)]
    turn: int = 1
    winner: Optional[int] = None

    def reset() -> None:
        """Reset the game state."""
        nonlocal board, turn, winner, winning_line
        board = [[None] * 3 for _ in range(3)]
        turn = 1
        winner = None
        winning_line = None

    reset()

    def check_winner() -> Optional[int]:
        """Check for a winner or draw.

        Returns:
            Optional[int]: 1 for X win, -1 for O win, 0 for draw, None for ongoing.
        """
        # Check rows
        for i in range(3):
            if board[i][0] == board[i][1] == board[i][2] and board[i][0] is not None:
                nonlocal winning_line
                winning_line = [(i, 0), (i, 2)]
                return board[i][0]

        # Check columns
        for j in range(3):
            if board[0][j] == board[1][j] == board[2][j] and board[0][j] is not None:
                winning_line = [(0, j), (2, j)]
                return board[0][j]

        # Check diagonals
        if board[0][0] == board[1][1] == board[2][2] and board[0][0] is not None:
            winning_line = [(0, 0), (2, 2)]
            return board[0][0]
        if board[0][2] == board[1][1] == board[2][0] and board[0][2] is not None:
            winning_line = [(0, 2), (2, 0)]
            return board[0][2]

        # Check draw
        if all(all(cell is not None for cell in row) for row in board):
            return 0

        return None

    running: bool = True
    while running:
        clock.tick(60)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "menu"
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    from game_shared import in_game_menu
                    choice = in_game_menu(screen, "Tic Tac Toe", COMMANDS, title_font, small_font)
                    if choice == "menu":
                        return "menu"
                    elif choice == "quit":
                        pygame.quit()
                        return "quit"
                    elif choice == "restart":
                        reset()
                        continue
                if event.key == pygame.K_r:
                    reset()
                if event.key == pygame.K_TAB:
                    if mode == "1P":
                        mode = "2P"
                    elif mode == "2P":
                        mode = "VS AI"
                    else:
                        mode = "1P"
                if event.key == pygame.K_1:
                    ai_difficulty = 1
                    ai.difficulty = ai_difficulty
                if event.key == pygame.K_2:
                    ai_difficulty = 3
                    ai.difficulty = ai_difficulty
                if event.key == pygame.K_3:
                    ai_difficulty = 6
                    ai.difficulty = ai_difficulty

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if winner is not None:
                    continue
                mx, my = event.pos
                margin: int = 160
                size: int = 480
                cell: int = size // 3
                if margin <= mx <= margin + size and margin <= my <= margin + size:
                    c = (mx - margin) // cell
                    r = (my - margin) // cell
                    if board[r][c] is None:
                        if mode == "VS AI":
                            if turn == 1:
                                board[r][c] = 1
                                turn = -1
                                ai_thinking = True
                                ai_think_start = pygame.time.get_ticks()
                        else:
                            board[r][c] = turn
                            turn = -turn

        # AI move with timer instead of blocking sleep
        if winner is None and mode == "VS AI" and turn == -1:
            elapsed = pygame.time.get_ticks() - ai_think_start if ai_thinking else 0
            if ai_thinking and elapsed >= ai_think_duration:
                ai_thinking = False
                try:
                    state = TicTacToeState(board, current_player=turn)
                    ai.player_id = -1
                    best = ai.get_best_move(state)
                    if best is not None:
                        board = state.make_move(best).board
                        turn = 1
                except Exception:
                    empties = [(r, c) for r in range(3) for c in range(3) if board[r][c] is None]
                    if empties:
                        r, c = random.choice(empties)
                        board[r][c] = -1
                        turn = 1

        winner = check_winner()
        draw_board(board, turn)

        if winner is not None:
            if winner == 1:
                res = "X WIN"
                x_wins += 1
            elif winner == -1:
                res = "O WIN"
                o_wins += 1
            else:
                res = "DRAW"
                draws += 1

            # Save scores
            scores_data["tris_x"] = x_wins
            scores_data["tris_o"] = o_wins
            scores_data["tris_draw"] = draws
            save_scores(scores_data)

            pygame.time.delay(600)
            screen.fill(BG)
            tx = title_font.render(res, True, (240, 200, 80))
            screen.blit(tx, (W // 2 - tx.get_width() // 2, H // 2 - 20))
            prompt = small_font.render("R: ricomincia  |  ESC: menu", True, (220, 220, 220))
            screen.blit(prompt, (W // 2 - prompt.get_width() // 2, H // 2 + 30))
            pygame.display.flip()

            waiting: bool = True
            while waiting:
                for ev in pygame.event.get():
                    if ev.type == pygame.QUIT:
                        return "menu"
                    if ev.type == pygame.KEYDOWN:
                        if ev.key == pygame.K_r:
                            reset()
                            waiting = False
                        if ev.key == pygame.K_ESCAPE:
                            return "menu"

    return "menu"
