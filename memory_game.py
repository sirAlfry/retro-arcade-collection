# memory_game.py
"""
Memory Game - Improved version with emoji symbols, move counter, and flip animation.
"""
import pygame
import random
from typing import List, Tuple, Dict, Any
from game_shared import safe_font, BG

W, H = 800, 600

COMMANDS = [
    "Clicca per girare le tessere",
    "ESC: menu"
]

# Card symbols and colors - each pair has a unique letter + color
SYMBOLS = ["A", "B", "C", "D", "E", "F", "G", "H", "J"]
SYMBOL_COLORS = {
    "A": (220, 50, 50),    # Rosso
    "B": (50, 150, 220),   # Blu
    "C": (50, 200, 80),    # Verde
    "D": (220, 180, 40),   # Giallo
    "E": (180, 60, 200),   # Viola
    "F": (240, 130, 40),   # Arancione
    "G": (60, 220, 200),   # Ciano
    "H": (220, 80, 160),   # Rosa
    "J": (160, 200, 60),   # Lime
}


def main() -> str:
    """Main game loop for Memory Game.

    Returns:
        str: Game state command ("menu", "quit", etc.)
    """
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Memory Game")
    clock = pygame.time.Clock()
    font = safe_font("consolas", 18)
    small_font = safe_font("consolas", 24)

    # Game state
    cols: int = 6
    rows: int = 3
    total: int = cols * rows
    if total % 2 != 0:
        cols += 1
        total = cols * rows

    # Create card pairs using symbols
    num_pairs: int = total // 2
    pairs = SYMBOLS[:num_pairs] * 2
    random.shuffle(pairs)

    size: int = min((W - 120) // cols, (H - 180) // rows)
    start_x: int = (W - (size * cols + (cols - 1) * 8)) // 2
    start_y: int = 100

    # Initialize cards
    cards: List[List[Dict[str, Any]]] = []
    for r in range(rows):
        row = []
        for c in range(cols):
            idx = r * cols + c
            rect = pygame.Rect(start_x + c * (size + 8), start_y + r * (size + 8), size, size)
            row.append({
                "rect": rect,
                "symbol": pairs[idx],
                "flipped": False,
                "matched": False,
                "flip_progress": 0.0  # 0.0 to 1.0 for animation
            })
        cards.append(row)

    flipped: List[Dict[str, Any]] = []
    score: int = 0
    move_counter: int = 0
    mismatch_until: int = 0
    lock_input: bool = False

    running: bool = True
    while running:
        dt: float = clock.tick(30) / 1000.0

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return "menu"
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                from game_shared import in_game_menu
                choice = in_game_menu(screen, "Memory Game", COMMANDS, font, font)
                if choice == "menu":
                    return "menu"
                if choice == "quit":
                    pygame.quit()
                    return "quit"
                if choice == "restart":
                    return main()

            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                if lock_input:
                    continue  # Ignore clicks during mismatch pause
                mx, my = e.pos
                for r in range(rows):
                    for c in range(cols):
                        card = cards[r][c]
                        if (card["rect"].collidepoint(mx, my) and
                            not card["flipped"] and not card["matched"]):
                            card["flipped"] = True
                            card["flip_progress"] = 0.0
                            flipped.append(card)
                            move_counter += 1

        # Animate flip progress
        for r in range(rows):
            for c in range(cols):
                card = cards[r][c]
                if card["flipped"] and card["flip_progress"] < 1.0:
                    card["flip_progress"] += dt * 4  # Animation speed
                    card["flip_progress"] = min(card["flip_progress"], 1.0)

        # Check if two cards are flipped
        if len(flipped) == 2 and not lock_input:
            if flipped[0]["symbol"] == flipped[1]["symbol"]:
                flipped[0]["matched"] = flipped[1]["matched"] = True
                score += 10
                flipped = []
            else:
                lock_input = True
                mismatch_until = pygame.time.get_ticks() + 600

        # Reset mismatched cards after delay
        if lock_input and pygame.time.get_ticks() >= mismatch_until:
            for card in flipped:
                card["flipped"] = False
                card["flip_progress"] = 0.0
            flipped.clear()
            mismatch_until = 0
            lock_input = False

        # Check win condition
        all_matched = all(card["matched"] for row in cards for card in row)
        if all_matched:
            pygame.time.delay(400)
            from game_shared import open_exit_menu
            res = open_exit_menu(
                screen,
                f"Hai vinto! Mosse: {move_counter}",
                COMMANDS,
                font,
                font
            )
            if res == "restart":
                return main()
            return res

        # Draw
        screen.fill(BG)
        for r in range(rows):
            for c in range(cols):
                card = cards[r][c]
                rect = card["rect"]

                # Simple scale animation effect
                if card["flipped"] or card["matched"]:
                    progress = card["flip_progress"]
                    scale = 1.0 - (progress * 0.2)  # Slight shrink on flip
                    w = int(rect.width * scale)
                    h = int(rect.height * scale)
                    x = rect.x + (rect.width - w) // 2
                    y = rect.y + (rect.height - h) // 2
                    scaled_rect = pygame.Rect(x, y, w, h)

                    pygame.draw.rect(screen, (200, 200, 200), scaled_rect)
                    sym_color = SYMBOL_COLORS.get(card["symbol"], (40, 40, 40))
                    txt = small_font.render(card["symbol"], True, sym_color)
                    screen.blit(txt, (x + w // 2 - txt.get_width() // 2,
                                     y + h // 2 - txt.get_height() // 2))
                else:
                    pygame.draw.rect(screen, (60, 60, 80), rect)
                    pygame.draw.rect(screen, (100, 100, 120), rect, 3)

        # Draw UI
        sc = font.render(f"SCORE: {score}  MOVES: {move_counter}", True, (180, 240, 180))
        screen.blit(sc, (10, 10))
        pygame.display.flip()

    pygame.quit()
    return "menu"


if __name__ == "__main__":
    main()
