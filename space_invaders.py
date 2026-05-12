# space_invaders.py
"""
Space Invaders - Improved version with enemy bullets, lives, and level progression.
"""
import pygame
import random
from typing import List, Dict, Tuple
from game_shared import safe_font, BG

W, H = 800, 600

COMMANDS = [
    "Frecce: muovi | SPAZIO: spara",
    "ESC: menu"
]


def main() -> str:
    """Main game loop for Space Invaders.

    Returns:
        str: Game state command ("menu", "quit", etc.)
    """
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Space Invaders")
    clock = pygame.time.Clock()
    font = safe_font("consolas", 18)

    # Game state
    ship_x: float = W // 2
    ship_y: float = H - 60
    bullets: List[Dict[str, float]] = []
    enemy_bullets: List[Dict[str, float]] = []
    enemies: List[Dict[str, float]] = []
    SHIP_R: int = 12

    # Game progression
    score: int = 0
    lives: int = 3
    level: int = 1
    enemy_rows: int = 4

    def spawn_enemies() -> List[Dict[str, float]]:
        """Spawn a new wave of enemies.

        Returns:
            List[Dict]: List of enemy dictionaries with x, y coordinates.
        """
        new_enemies: List[Dict[str, float]] = []
        for r in range(enemy_rows):
            for c in range(8):
                new_enemies.append({"x": 80 + c * 64, "y": 50 + r * 48})
        return new_enemies

    enemies = spawn_enemies()
    enemy_dir: int = 1
    enemy_timer: float = 0.0
    enemy_shoot_timer: float = 0.0

    running: bool = True
    while running:
        dt: float = clock.tick(60) / 1000.0
        enemy_timer += dt
        enemy_shoot_timer += dt

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return "menu"
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    from game_shared import in_game_menu
                    choice = in_game_menu(screen, "Space Invaders", COMMANDS, font, font)
                    if choice == "menu":
                        return "menu"
                    if choice == "quit":
                        pygame.quit()
                        return "quit"
                    if choice == "restart":
                        return main()
                if e.key == pygame.K_SPACE:
                    bullets.append({"x": ship_x, "y": ship_y - 20})

        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT]:
            ship_x -= 6
        if keys[pygame.K_RIGHT]:
            ship_x += 6
        ship_x = max(20, min(W - 20, ship_x))

        # Enemy movement
        if enemy_timer > 0.6:
            enemy_timer = 0
            shift: bool = False
            for en in enemies:
                en["x"] += enemy_dir * 12
                if en["x"] < 20 or en["x"] > W - 20:
                    shift = True
            if shift:
                enemy_dir *= -1
                for en in enemies:
                    en["y"] += 18

        # Enemy shooting
        if enemy_shoot_timer > 0.4 and enemies:
            enemy_shoot_timer = 0
            shooter = random.choice(enemies)
            enemy_bullets.append({"x": shooter["x"], "y": shooter["y"] + 16})

        # Move player bullets
        for b in bullets[:]:
            b["y"] -= 10
            if b["y"] < 0:
                try:
                    bullets.remove(b)
                except ValueError:
                    pass
                continue

            # Check collision with enemies
            for en in enemies[:]:
                if abs(b["x"] - en["x"]) < 20 and abs(b["y"] - en["y"]) < 16:
                    try:
                        enemies.remove(en)
                    except ValueError:
                        pass
                    try:
                        bullets.remove(b)
                    except ValueError:
                        pass
                    score += 10
                    break

        # Move enemy bullets
        for eb in enemy_bullets[:]:
            eb["y"] += 8
            if eb["y"] > H:
                try:
                    enemy_bullets.remove(eb)
                except ValueError:
                    pass
                continue

            # Check collision with player
            if abs(eb["x"] - ship_x) < 20 and abs(eb["y"] - ship_y) < 16:
                try:
                    enemy_bullets.remove(eb)
                except ValueError:
                    pass
                lives -= 1
                if lives <= 0:
                    from game_shared import open_exit_menu
                    res = open_exit_menu(
                        screen,
                        "Hai perso!",
                        COMMANDS,
                        font,
                        font
                    )
                    if res == "restart":
                        return main()
                    return res

        # Check if enemies reached player
        for en in enemies:
            if en["y"] >= ship_y - 10:
                from game_shared import open_exit_menu
                res = open_exit_menu(
                    screen,
                    "Hai perso!",
                    COMMANDS,
                    font,
                    font
                )
                if res == "restart":
                    return main()
                return res

        # Level progression - all enemies cleared
        if not enemies:
            level += 1
            enemy_rows += 1
            enemies = spawn_enemies()
            enemy_dir = 1
            enemy_timer = 0.0
            enemy_shoot_timer = 0.0

        # Draw everything
        screen.fill(BG)

        # Draw player ship
        pygame.draw.polygon(screen, (200, 200, 255),
                          [(ship_x, ship_y - 16), (ship_x - 16, ship_y + 16), (ship_x + 16, ship_y + 16)])

        # Draw enemies
        for en in enemies:
            pygame.draw.rect(screen, (200, 80, 80), (en["x"] - 12, en["y"] - 8, 24, 16))

        # Draw player bullets
        for b in bullets:
            pygame.draw.rect(screen, (255, 255, 120), (b["x"] - 2, b["y"], 4, 8))

        # Draw enemy bullets
        for eb in enemy_bullets:
            pygame.draw.rect(screen, (255, 100, 100), (eb["x"] - 2, eb["y"], 4, 8))

        # Draw UI
        scr = font.render(f"SCORE: {score}  LEVEL: {level}  LIVES: {lives}", True, (180, 240, 180))
        screen.blit(scr, (10, 10))
        pygame.display.flip()

    pygame.quit()
    return "menu"


if __name__ == "__main__":
    main()
