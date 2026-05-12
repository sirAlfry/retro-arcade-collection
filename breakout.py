# breakout.py
"""
Breakout game with advanced features: lives system, progressive ball speed,
brick hit points, win condition, and improved rendering.
"""
import pygame
import random
from typing import List, Tuple, Optional

from game_shared import safe_font, BG

W, H = 800, 600
BALL_R = 8

COMMANDS = [
    "Muovi il paddle col mouse o con A/D",
    "ESC: Menu"
]


def main_loop() -> str:
    """
    Main Breakout game loop with lives system, progressive difficulty, and brick durability.

    Returns:
        "menu" to return to main menu, "quit" to exit application
    """
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Breakout")
    clock = pygame.time.Clock()

    # Cache fonts to avoid creating them every frame
    title_font = safe_font("consolas", 22)
    hud_font = safe_font("consolas", 16)

    paddle_w, paddle_h = 100, 12
    paddle_x = W // 2 - paddle_w // 2
    paddle_y = H - 40
    ball_x, ball_y = W // 2, H // 2
    ball_vx, ball_vy = 4.0, -5.0
    ball_speed_cap = 8.0
    speed_increase_time = 15.0  # Increase speed every 15 seconds

    cols = 10
    rows = 5
    brick_w = (W - 120) // cols
    bricks: List[dict] = []
    colors = [(255, 80, 80), (255, 170, 0), (255, 230, 60), (100, 220, 120), (80, 180, 255)]

    # Create bricks with hit points (top rows take 2 hits, bottom rows take 1)
    for r in range(rows):
        for c in range(cols):
            bx = 60 + c * brick_w
            by = 80 + r * 22
            # Top 2 rows have 2 hit points, bottom 3 rows have 1 hit point
            hit_points = 2 if r < 2 else 1
            bricks.append({
                "rect": pygame.Rect(bx, by, brick_w - 4, 18),
                "hits": hit_points,
                "max_hits": hit_points
            })

    score: int = 0
    lives: int = 3
    time_elapsed: float = 0.0
    game_running = True

    def reset_game_state() -> None:
        """Reset game state for a fresh game."""
        nonlocal ball_x, ball_y, ball_vx, ball_vy, paddle_x, score, lives, time_elapsed
        nonlocal bricks
        ball_x, ball_y = W // 2, H // 2
        ball_vx, ball_vy = 4.0, -5.0
        paddle_x = W // 2 - paddle_w // 2
        score = 0
        lives = 3
        time_elapsed = 0.0

        bricks = []
        for r in range(rows):
            for c in range(cols):
                bx = 60 + c * brick_w
                by = 80 + r * 22
                hit_points = 2 if r < 2 else 1
                bricks.append({
                    "rect": pygame.Rect(bx, by, brick_w - 4, 18),
                    "hits": hit_points,
                    "max_hits": hit_points
                })

    def show_game_over_menu(message: str) -> str:
        """
        Display game over or win screen with menu options.

        Args:
            message: The message to display (e.g., "Hai perso!", "Hai vinto!")

        Returns:
            "restart" to restart, "menu" to return to menu, "quit" to exit
        """
        from game_shared import open_exit_menu
        res = open_exit_menu(
            screen,
            message,
            COMMANDS,
            title_font,
            hud_font
        )
        return res

    def update_ball_speed() -> None:
        """Increase ball speed over time, with a cap."""
        nonlocal ball_vx, ball_vy
        speed = (ball_vx ** 2 + ball_vy ** 2) ** 0.5
        if speed < ball_speed_cap and time_elapsed % speed_increase_time < 0.016:  # Update roughly every 15 seconds
            scale = min(speed + 0.3, ball_speed_cap) / speed
            ball_vx *= scale
            ball_vy *= scale

    while game_running:
        dt = clock.tick(60) / 1000.0
        time_elapsed += dt

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                result = show_game_over_menu("Hai perso!")
                if result == "restart":
                    reset_game_state()
                    continue
                elif result == "menu":
                    return "menu"
                else:
                    return result
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                from game_shared import in_game_menu
                choice = in_game_menu(screen, "Breakout", COMMANDS, title_font, hud_font)
                if choice == "menu":
                    result = show_game_over_menu("Hai perso!")
                    if result == "restart":
                        reset_game_state()
                        continue
                    else:
                        return result
                elif choice == "quit":
                    pygame.quit()
                    return "quit"
                elif choice == "restart":
                    reset_game_state()
                    continue

        # Paddle movement
        keys = pygame.key.get_pressed()
        if keys[pygame.K_a]:
            paddle_x -= 7
        if keys[pygame.K_d]:
            paddle_x += 7
        mx, my = pygame.mouse.get_pos()
        if pygame.mouse.get_focused():
            paddle_x = mx - paddle_w // 2

        paddle_x = max(0, min(W - paddle_w, paddle_x))

        # Ball movement
        ball_x += ball_vx
        ball_y += ball_vy

        # Wall collisions
        if ball_x - BALL_R <= 0 or ball_x + BALL_R >= W:
            ball_vx *= -1
        if ball_y - BALL_R <= 0:
            ball_vy *= -1

        # Paddle collision (consider ball radius)
        if (paddle_x <= ball_x <= paddle_x + paddle_w and
                paddle_y <= ball_y + BALL_R <= paddle_y + paddle_h):
            ball_vy = -abs(ball_vy)
            offset = (ball_x - (paddle_x + paddle_w / 2)) / (paddle_w / 2)
            ball_vx += int(offset * 3)

        # Brick collisions with durability
        bremove = None
        for i, brick in enumerate(bricks):
            if brick["rect"].collidepoint(int(ball_x), int(ball_y)):
                bremove = i
                ball_vy *= -1
                break

        if bremove is not None:
            bricks[bremove]["hits"] -= 1
            if bricks[bremove]["hits"] <= 0:
                bricks.pop(bremove)
                score += 10
            else:
                score += 5  # Partial score for damaging multi-hit bricks

        # Check win condition
        if not bricks:
            result = show_game_over_menu("Hai vinto!")
            if result == "restart":
                reset_game_state()
                continue
            elif result == "menu":
                return "menu"
            else:
                return result

        # Ball out of bounds - lose a life
        if ball_y - BALL_R > H:
            lives -= 1
            if lives <= 0:
                result = show_game_over_menu("Hai perso!")
                if result == "restart":
                    reset_game_state()
                    continue
                elif result == "menu":
                    return "menu"
                else:
                    return result
            else:
                # Reset ball position for next life
                ball_x, ball_y = W // 2, H // 2
                ball_vx, ball_vy = 4.0, -5.0

        # Progressive speed increase
        update_ball_speed()

        # Render
        screen.fill(BG)

        # Draw bricks
        for brick in bricks:
            color_idx = min(brick["rect"].y // 22, len(colors) - 1)
            brick_color = colors[color_idx]

            # Darken color if brick has multiple hits and is damaged
            if brick["max_hits"] > 1 and brick["hits"] < brick["max_hits"]:
                # Show partial damage with color darkening
                damage_factor = 1.0 - (1.0 - brick["hits"] / brick["max_hits"]) * 0.5
                brick_color = tuple(int(c * damage_factor) for c in brick_color)

            pygame.draw.rect(screen, brick_color, brick["rect"])

        # Draw paddle
        pygame.draw.rect(screen, (220, 220, 220), (paddle_x, paddle_y, paddle_w, paddle_h))

        # Draw ball
        pygame.draw.circle(screen, (255, 255, 255), (int(ball_x), int(ball_y)), BALL_R)

        # Draw HUD
        sc = hud_font.render(f"SCORE: {score}", True, (180, 240, 180))
        screen.blit(sc, (10, 10))

        # Draw lives as hearts/display
        lives_text = hud_font.render(f"LIVES: {lives}", True, (255, 100, 100))
        screen.blit(lives_text, (W - 200, 10))

        pygame.display.flip()

    pygame.quit()
    return "menu"


if __name__ == "__main__":
    main_loop()
