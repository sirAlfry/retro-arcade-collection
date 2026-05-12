# snake.py
import pygame
import random
import time
from typing import Callable, List, Tuple, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
from game_shared import safe_font, BG, W as SHARED_W, H as SHARED_H

# we'll use local W,H same as shared
W, H = 800, 600
GRID = 20

# Max speed cap to prevent insane acceleration
MAX_SPEED = 20

COMMANDS = [
    "Muovi: Frecce o WASD",
    "R: Ricomincia | M: Torna al menu | Q: Chiudi app | ESC: Menu in-game"
]


@dataclass
class SnakeState:
    """Represents the complete game state for Snake."""
    snake: List[Tuple[int, int]]
    direction: Tuple[int, int]
    next_direction: Tuple[int, int]
    alive: bool
    score: int
    high_score: int
    speed: float
    red_food: Tuple[int, int]
    blue_food: Tuple[int, int]
    blue_visible: bool
    blue_cooldown_until: float
    particles: List[Dict[str, Any]] = field(default_factory=list)

    def update_particles(self) -> None:
        """Update particle life and remove expired ones."""
        for p in self.particles[:]:
            p['life'] -= 1
            if p['life'] <= 0:
                self.particles.remove(p)


def snake_game(load_scores: Callable, save_scores: Callable) -> str:
    """
    Main Snake game loop.

    Args:
        load_scores: Callable to load high scores dictionary
        save_scores: Callable to save high scores dictionary

    Returns:
        str: "menu" or "quit" to indicate next state
    """
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Snake")
    clock = pygame.time.Clock()

    title_font = safe_font("consolas", 24)
    small_font = safe_font("consolas", 16)

    def align(v: int) -> int:
        """Align position to grid."""
        return (v // GRID) * GRID + GRID // 2

    def spawn_food(occupied_cells: List[Tuple[int, int]]) -> Tuple[int, int]:
        """
        Spawn food at a random unoccupied grid cell.

        Args:
            occupied_cells: List of occupied (grid_x, grid_y) positions

        Returns:
            Tuple of (pixel_x, pixel_y) for food position
        """
        occ = set(occupied_cells)
        attempts = 0
        while True:
            gx = random.randrange(0, W // GRID)
            gy = random.randrange(0, H // GRID)
            cell = (gx, gy)
            if cell not in occ:
                return (gx * GRID + GRID // 2, gy * GRID + GRID // 2)
            attempts += 1
            if attempts > 1000:
                # fallback: search linearly
                for gy2 in range(0, H // GRID):
                    for gx2 in range(0, W // GRID):
                        if (gx2, gy2) not in occ:
                            return (gx2 * GRID + GRID // 2, gy2 * GRID + GRID // 2)

    def reset() -> SnakeState:
        """Reset game to initial state."""
        headx = align(W // 2)
        heady = align(H // 2)
        snake = [(headx, heady), (headx - GRID, heady), (headx - 2 * GRID, heady)]
        red = spawn_food([(x // GRID, y // GRID) for (x, y) in snake])
        blue = spawn_food([(x // GRID, y // GRID) for (x, y) in snake] + [(red[0] // GRID, red[1] // GRID)])

        # Load high score
        try:
            scores = load_scores()
            high_score = scores.get("snake", 0)
        except Exception:
            high_score = 0

        return SnakeState(
            snake=snake,
            direction=(GRID, 0),
            next_direction=(GRID, 0),
            alive=True,
            score=0,
            high_score=high_score,
            speed=8,
            red_food=red,
            blue_food=blue,
            blue_visible=True,
            blue_cooldown_until=0,
            particles=[]
        )

    def save_if_high(score: int) -> None:
        """Save score if it's a new high score."""
        try:
            scores = load_scores()
            if score > scores.get("snake", 0):
                scores["snake"] = score
                save_scores(scores)
        except Exception:
            pass

    def add_particle(x: int, y: int) -> None:
        """Add a particle effect at given coordinates."""
        for _ in range(8):
            angle = random.uniform(0, 6.28)
            speed = random.uniform(1, 3)
            state.particles.append({
                'x': x,
                'y': y,
                'vx': speed * (angle ** 0.5),
                'vy': speed * (1 - angle ** 0.5),
                'life': 20,
                'color': (random.randint(100, 255), random.randint(100, 255), 50)
            })

    def draw_grid_background() -> None:
        """Draw subtle grid pattern background."""
        for x in range(0, W, GRID):
            pygame.draw.line(screen, (40, 40, 50), (x, 0), (x, H), 1)
        for y in range(0, H, GRID):
            pygame.draw.line(screen, (40, 40, 50), (0, y), (W, y), 1)

    def get_snake_color(segment_index: int, total_segments: int) -> Tuple[int, int, int]:
        """
        Get gradient color for snake body segment.
        Head is bright, tail is darker.
        """
        if segment_index == 0:  # head
            return (100, 255, 100)
        else:
            # Gradient from middle to tail
            ratio = segment_index / max(1, total_segments - 1)
            brightness = int(160 * (1 - ratio * 0.6))
            return (20, brightness, 30)

    state = reset()
    running = True

    while running:
        # Cap speed to prevent insane acceleration
        capped_speed = min(state.speed + state.score // 5, MAX_SPEED)
        dt = clock.tick(capped_speed)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                return "menu"
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE,):
                    from game_shared import in_game_menu
                    choice = in_game_menu(screen, "Snake", COMMANDS, title_font, small_font)
                    if choice == "menu":
                        save_if_high(state.score)
                        return "menu"
                    elif choice == "quit":
                        save_if_high(state.score)
                        pygame.quit()
                        return "quit"
                    elif choice == "restart":
                        state = reset()
                        continue
                if event.key == pygame.K_r:
                    state = reset()
                if event.key == pygame.K_m:
                    save_if_high(state.score)
                    return "menu"
                if event.key == pygame.K_q:
                    save_if_high(state.score)
                    pygame.quit()
                    return "quit"
                if event.key in (pygame.K_LEFT, pygame.K_a):
                    if state.direction != (GRID, 0):
                        state.next_direction = (-GRID, 0)
                if event.key in (pygame.K_RIGHT, pygame.K_d):
                    if state.direction != (-GRID, 0):
                        state.next_direction = (GRID, 0)
                if event.key in (pygame.K_UP, pygame.K_w):
                    if state.direction != (0, GRID):
                        state.next_direction = (0, -GRID)
                if event.key in (pygame.K_DOWN, pygame.K_s):
                    if state.direction != (0, -GRID):
                        state.next_direction = (0, GRID)

        if not state.alive:
            screen.fill(BG)
            draw_grid_background()
            txt = title_font.render("GAME OVER", True, (240, 200, 80))
            scr = small_font.render(f"Score: {state.score}  |  High Score: {state.high_score}", True, (220, 220, 220))
            stats = small_font.render(f"Length: {len(state.snake)}  |  R: restart  |  M: menu", True, (180, 200, 180))
            screen.blit(txt, (W // 2 - txt.get_width() // 2, H // 2 - 50))
            screen.blit(scr, (W // 2 - scr.get_width() // 2, H // 2 - 10))
            screen.blit(stats, (W // 2 - stats.get_width() // 2, H // 2 + 20))
            pygame.display.flip()
            pygame.event.pump()
            continue

        state.direction = state.next_direction
        head_x, head_y = state.snake[0]
        dx, dy = state.direction
        new_head = (head_x + dx, head_y + dy)

        hx, hy = new_head
        if hx - GRID // 2 < 0 or hy - GRID // 2 < 0 or hx + GRID // 2 > W or hy + GRID // 2 > H:
            state.alive = False
            save_if_high(state.score)
            continue

        if new_head in state.snake:
            state.alive = False
            save_if_high(state.score)
            continue

        state.snake.insert(0, new_head)

        # eat red food (grid aligned)
        if (abs(new_head[0] - state.red_food[0]) < GRID and
                abs(new_head[1] - state.red_food[1]) < GRID):
            state.score += 2
            add_particle(state.red_food[0], state.red_food[1])
            occ = [(x // GRID, y // GRID) for (x, y) in state.snake]
            state.red_food = spawn_food(occ + [(state.blue_food[0] // GRID, state.blue_food[1] // GRID)])
        elif state.blue_visible and (abs(new_head[0] - state.blue_food[0]) < GRID and
                                      abs(new_head[1] - state.blue_food[1]) < GRID):
            state.score += 5
            add_particle(state.blue_food[0], state.blue_food[1])
            state.blue_visible = False
            state.blue_cooldown_until = pygame.time.get_ticks() + 5000
            # grow: don't pop tail
        else:
            state.snake.pop()

        if (not state.blue_visible) and pygame.time.get_ticks() >= state.blue_cooldown_until:
            occ = [(x // GRID, y // GRID) for (x, y) in state.snake]
            state.blue_food = spawn_food(occ + [(state.red_food[0] // GRID, state.red_food[1] // GRID)])
            state.blue_visible = True

        # Update particles
        state.update_particles()

        # draw
        screen.fill(BG)
        draw_grid_background()

        # Draw food
        pygame.draw.circle(screen, (200, 30, 30), state.red_food, GRID // 2 - 2)
        if state.blue_visible:
            pygame.draw.circle(screen, (50, 140, 220), state.blue_food, GRID // 2 - 2)

        # Draw snake with gradient
        for i, seg in enumerate(state.snake):
            col = get_snake_color(i, len(state.snake))
            pygame.draw.rect(screen, col, pygame.Rect(seg[0] - GRID // 2, seg[1] - GRID // 2, GRID, GRID))

        # Draw particles
        for p in state.particles:
            p['x'] += p['vx']
            p['y'] += p['vy']
            alpha = max(0, int(255 * (p['life'] / 20)))
            surf = pygame.Surface((4, 4))
            surf.fill(p['color'])
            surf.set_alpha(alpha)
            screen.blit(surf, (int(p['x']), int(p['y'])))

        # Draw HUD
        score_s = small_font.render(f"SCORE: {state.score}", True, (180, 240, 180))
        high_s = small_font.render(f"HIGH: {state.high_score}", True, (200, 200, 150))
        screen.blit(score_s, (10, 10))
        screen.blit(high_s, (10, 30))
        pygame.display.flip()

    pygame.quit()
    return "menu"


# small helper if executed directly
if __name__ == "__main__":
    def _load_scores():
        return {}
    def _save_scores(s):
        pass
    snake_game(_load_scores, _save_scores)
