# pong.py
import pygame
import random
from typing import Tuple, List, Optional
from dataclasses import dataclass, field
from game_shared import safe_font, BG

W, H = 800, 600

# Max ball velocity to prevent insane speeds
MAX_BALL_SPEED = 12

COMMANDS = [
    "W/S: Player 1  |  UP/DOWN: Player 2",
    "TAB: toggle 1P/2P/VS AI  |  SPACE: pausa  |  ESC: menu"
]


@dataclass
class BallTrail:
    """Represents a ghost position in the ball trail."""
    x: float
    y: float
    life: int  # 0-10, fades out


def ai_move(paddle_y: float, ball_y: float, difficulty: int) -> float:
    """
    Calculate AI paddle movement.

    Args:
        paddle_y: Current Y position of paddle
        ball_y: Current Y position of ball
        difficulty: 1 (easy), 2 (medium), 3 (hard)

    Returns:
        Movement delta
    """
    if difficulty == 1:
        if random.random() < 0.6:
            if paddle_y + 30 < ball_y:
                return 4
            if paddle_y - 30 > ball_y:
                return -4
        return 0
    if difficulty == 2:
        if paddle_y + 10 < ball_y:
            return 5
        if paddle_y - 10 > ball_y:
            return -5
        return 0
    if paddle_y + 5 < ball_y:
        return 6
    if paddle_y - 5 > ball_y:
        return -6
    return 0


def main() -> str:
    """
    Main Pong game loop.

    Returns:
        str: "menu" or "quit" to indicate next state
    """
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Pong")
    clock = pygame.time.Clock()

    # Cache fonts at initialization
    font_large = safe_font("consolas", 28)
    font_small = safe_font("consolas", 14)

    mode = "2P"
    ai_diff = 2

    paddle_w, paddle_h = 10, 80
    left_y = H // 2
    right_y = H // 2
    ball_x = W // 2
    ball_y = H // 2
    ball_vx = 6 * random.choice((-1, 1))
    ball_vy = 4 * random.choice((-1, 1))
    score_l, score_r = 0, 0

    running = True
    paused = False
    BALL_R = 8

    # Ball trail effect
    ball_trail: List[BallTrail] = []
    TRAIL_MAX_AGE = 10

    def reset_ball() -> Tuple[float, float, float, float]:
        """Reset ball to center with random velocity."""
        return W // 2, H // 2, 6 * random.choice((-1, 1)), 4 * random.choice((-1, 1))

    def update_ball_trail() -> None:
        """Update ball trail and remove old positions."""
        nonlocal ball_trail
        # Add current position to trail
        ball_trail.append(BallTrail(ball_x, ball_y, TRAIL_MAX_AGE))
        # Age all trail points
        for trail in ball_trail:
            trail.life -= 1
        # Remove dead trail points
        ball_trail = [t for t in ball_trail if t.life > 0]

    def clamp_ball_velocity() -> None:
        """Clamp ball velocity to prevent it going crazy."""
        nonlocal ball_vx, ball_vy
        speed = (ball_vx ** 2 + ball_vy ** 2) ** 0.5
        if speed > MAX_BALL_SPEED:
            ball_vx *= MAX_BALL_SPEED / speed
            ball_vy *= MAX_BALL_SPEED / speed

    while running:
        dt = clock.tick(60)
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
                return "menu"
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    from game_shared import in_game_menu
                    choice = in_game_menu(screen, "Pong", COMMANDS, font_small, font_small)
                    if choice == "menu":
                        return "menu"
                    if choice == "quit":
                        pygame.quit()
                        return "quit"
                    if choice == "restart":
                        left_y = right_y = H // 2
                        ball_x, ball_y, ball_vx, ball_vy = reset_ball()
                        score_l = score_r = 0
                        ball_trail = []
                if e.key == pygame.K_TAB:
                    if mode == "2P":
                        mode = "1P"
                    elif mode == "1P":
                        mode = "VS AI"
                    else:
                        mode = "2P"
                if e.key == pygame.K_SPACE:
                    paused = not paused

        if not paused:
            keys = pygame.key.get_pressed()

            # Left paddle (P1) - always available
            if keys[pygame.K_w]:
                left_y -= 6
            if keys[pygame.K_s]:
                left_y += 6

            # Right paddle (P2 or AI)
            if mode == "2P":
                # Two player mode: both can control right paddle
                if keys[pygame.K_UP]:
                    right_y -= 6
                if keys[pygame.K_DOWN]:
                    right_y += 6
            elif mode == "1P":
                # One player mode: right paddle is AI (not controlled by player)
                mv = ai_move(right_y, ball_y, 1)
                right_y += mv
            else:  # VS AI
                # AI mode: right paddle is AI with difficulty
                mv = ai_move(right_y, ball_y, ai_diff)
                right_y += mv

            # Clamp paddles
            left_y = max(paddle_h // 2, min(H - paddle_h // 2, left_y))
            right_y = max(paddle_h // 2, min(H - paddle_h // 2, right_y))

            # Move ball
            ball_x += ball_vx
            ball_y += ball_vy
            update_ball_trail()

            # Ball boundary collision (top/bottom)
            if ball_y - BALL_R <= 0 or ball_y + BALL_R >= H:
                ball_vy *= -1

            # Left paddle collision
            if ball_x - BALL_R <= 40:
                if left_y - paddle_h // 2 <= ball_y <= left_y + paddle_h // 2:
                    ball_vx = abs(ball_vx)
                    offset = (ball_y - left_y) / (paddle_h / 2)
                    ball_vy += offset * 3
                    clamp_ball_velocity()

            # Right paddle collision
            if ball_x + BALL_R >= W - 40:
                if right_y - paddle_h // 2 <= ball_y <= right_y + paddle_h // 2:
                    ball_vx = -abs(ball_vx)
                    offset = (ball_y - right_y) / (paddle_h / 2)
                    ball_vy += offset * 3
                    clamp_ball_velocity()

            # Goal detection
            if ball_x < 0:
                score_r += 1
                ball_x, ball_y, ball_vx, ball_vy = reset_ball()
                ball_trail = []
            if ball_x > W:
                score_l += 1
                ball_x, ball_y, ball_vx, ball_vy = reset_ball()
                ball_trail = []

            # Check for win condition (first to 11)
            if score_l >= 11 or score_r >= 11:
                # Win screen
                winner = "LEFT" if score_l >= 11 else "RIGHT"
                screen.fill(BG)

                win_txt = font_large.render(f"PLAYER {winner} WINS!", True, (255, 200, 100))
                final_score = font_small.render(f"Final Score: {score_l} - {score_r}", True, (200, 200, 200))
                menu_txt = font_small.render("Press ESC for menu or TAB to play again", True, (150, 200, 150))

                screen.blit(win_txt, (W // 2 - win_txt.get_width() // 2, H // 2 - 60))
                screen.blit(final_score, (W // 2 - final_score.get_width() // 2, H // 2 - 10))
                screen.blit(menu_txt, (W // 2 - menu_txt.get_width() // 2, H // 2 + 40))
                pygame.display.flip()
                pygame.event.pump()
                continue

        # draw
        screen.fill(BG)

        # Draw center line
        for y in range(0, H, 24):
            pygame.draw.rect(screen, (80, 80, 100), (W // 2 - 4, y + 8, 8, 12))

        # Draw paddles
        pygame.draw.rect(screen, (240, 240, 240), (30, left_y - paddle_h // 2, paddle_w, paddle_h))
        pygame.draw.rect(screen, (240, 240, 240), (W - 30 - paddle_w, right_y - paddle_h // 2, paddle_w, paddle_h))

        # Draw ball trail
        for trail in ball_trail:
            alpha = int(80 * (trail.life / TRAIL_MAX_AGE))
            trail_surf = pygame.Surface((BALL_R * 2, BALL_R * 2))
            trail_surf.set_colorkey((0, 0, 0))
            pygame.draw.circle(trail_surf, (120, 120, 120), (BALL_R, BALL_R), BALL_R)
            trail_surf.set_alpha(alpha)
            screen.blit(trail_surf, (int(trail.x) - BALL_R, int(trail.y) - BALL_R))

        # Draw ball
        pygame.draw.circle(screen, (240, 240, 240), (int(ball_x), int(ball_y)), BALL_R)

        # Draw scores using cached font
        s1 = font_large.render(str(score_l), True, (180, 240, 180))
        s2 = font_large.render(str(score_r), True, (180, 240, 180))
        screen.blit(s1, (W // 2 - 80, 20))
        screen.blit(s2, (W // 2 + 60, 20))

        # Draw mode label using cached font
        label = font_small.render(f"Mode: {mode}", True, (220, 220, 220))
        screen.blit(label, (10, 10))
        pygame.display.flip()

    pygame.quit()
    return "menu"


if __name__ == "__main__":
    main()
