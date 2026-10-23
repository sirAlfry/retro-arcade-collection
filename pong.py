# pong.py
"""
Pong - the 1972 classic.

Modes (chosen when the game starts):
    * 1 player vs CPU - easy / medium / hard
    * 2 players on the same keyboard

What changed compared to the first version:
    * the old "1P" and "VS AI" modes were the same thing: now there is one
      clear vs-CPU mode with three real difficulty levels;
    * the CPU *predicts* where the ball will arrive (bounces included), with a
      reaction delay and an aiming error that depend on the difficulty;
    * frame-rate independent physics (pixels per second), proper rectangle
      collisions, the ball can no longer get stuck in walls or paddles;
    * the ball speeds up a little on every hit and the bounce angle depends
      on where it touches the paddle;
    * a serve countdown after each point, and a working victory screen
      (the old one froze the game forever).
"""
from __future__ import annotations

import math
import random
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

import pygame

import game_shared as gs
import sfx
from pixel_font import blit_pixel_text
from scores import get_best

W, H = gs.W, gs.H
TOP, BOTTOM = 14, H - 14          # playfield walls
PADDLE_W, PADDLE_H = 12, 90
PADDLE_X_MARGIN = 34
PADDLE_SPEED = 470.0              # px/s for human players
BALL_R = 8
BALL_START_SPEED = 380.0
BALL_MAX_SPEED = 950.0
SPEEDUP = 1.06
MAX_BOUNCE_ANGLE = math.radians(60)
WIN_SCORE = 11
SERVE_DELAY = 1.0

COMMANDS = [
    "Giocatore 1: W / S   (in 1P anche le frecce)",
    "Giocatore 2: frecce ↑ / ↓   Vince chi arriva a 11",
]

MODES = ("1 GIOCATORE · FACILE", "1 GIOCATORE · MEDIO", "1 GIOCATORE · DIFFICILE", "2 GIOCATORI")


@dataclass(frozen=True)
class AIProfile:
    speed: float      # max paddle speed (px/s)
    error: float      # max aiming error (px)
    reaction: float   # seconds between two "looks" at the ball


AI_LEVELS = (
    AIProfile(speed=260.0, error=70.0, reaction=0.28),
    AIProfile(speed=390.0, error=34.0, reaction=0.12),
    AIProfile(speed=560.0, error=10.0, reaction=0.04),
)


def predict_y(x: float, y: float, vx: float, vy: float, target_x: float,
              top: float = TOP + BALL_R, bottom: float = BOTTOM - BALL_R) -> float:
    """
    Where will the ball cross ``target_x``? Wall bounces are "unfolded":
    the trajectory is a straight line in a mirrored space, folded back
    into ``[top, bottom]`` with a modulo. Returns the centre if unreachable.
    """
    if vx == 0 or (target_x - x) / vx < 0:
        return (top + bottom) / 2
    t = (target_x - x) / vx
    span = bottom - top
    py = (y + vy * t - top) % (2 * span)
    if py > span:
        py = 2 * span - py
    return top + py


class Paddle:
    def __init__(self, x: float) -> None:
        self.rect = pygame.Rect(0, 0, PADDLE_W, PADDLE_H)
        self.rect.center = (int(x), H // 2)
        self.y = float(self.rect.centery)
        self.flash = 0.0

    def move(self, dy: float) -> None:
        self.y = max(TOP + PADDLE_H / 2, min(BOTTOM - PADDLE_H / 2, self.y + dy))
        self.rect.centery = int(self.y)


class CPU:
    """Computer-controlled paddle with human-like imperfections."""

    def __init__(self, profile: AIProfile) -> None:
        self.profile = profile
        self.target = H / 2
        self.look_timer = 0.0
        self.error = 0.0

    def new_rally(self) -> None:
        self.error = random.uniform(-self.profile.error, self.profile.error)

    def update(self, dt: float, paddle: Paddle, ball: Ball) -> None:
        self.look_timer -= dt
        if self.look_timer <= 0:
            self.look_timer = self.profile.reaction
            if ball.vx > 0:
                self.target = predict_y(ball.x, ball.y, ball.vx, ball.vy, paddle.rect.left) + self.error
            else:
                self.target = H / 2  # drift back to the centre
        diff = self.target - paddle.y
        step = self.profile.speed * dt
        if abs(diff) > 4:
            paddle.move(max(-step, min(step, diff)))


class Ball:
    def __init__(self) -> None:
        self.x = W / 2
        self.y = H / 2
        self.vx = 0.0
        self.vy = 0.0
        self.speed = BALL_START_SPEED
        self.trail: deque[tuple[float, float]] = deque(maxlen=12)

    def serve(self, direction: int) -> None:
        self.x, self.y = W / 2, random.uniform(H * 0.3, H * 0.7)
        self.speed = BALL_START_SPEED
        angle = random.uniform(-0.45, 0.45)
        self.vx = direction * self.speed * math.cos(angle)
        self.vy = self.speed * math.sin(angle)
        self.trail.clear()

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x - BALL_R), int(self.y - BALL_R), BALL_R * 2, BALL_R * 2)


def _ball_sprites() -> list[pygame.Surface]:
    sprites = []
    for i in range(12):
        s = pygame.Surface((BALL_R * 2, BALL_R * 2), pygame.SRCALPHA)
        alpha = int(150 * (i + 1) / 12)
        pygame.draw.circle(s, (120, 220, 255, alpha), (BALL_R, BALL_R), max(2, BALL_R * (i + 4) // 16))
        sprites.append(s)
    return sprites


def main(load_scores: Callable[[], dict] | None = None,
         save_scores: Callable[[dict], None] | None = None) -> str:
    """
    Play Pong.

    Returns:
        ``"menu"`` or ``"quit"``.
    """
    load_scores, save_scores = gs.ensure_scores(load_scores, save_scores)
    screen = gs.setup_screen("Pong")
    clock = gs.GameClock(60)

    backdrop = pygame.Surface((W, H))
    backdrop.fill(gs.BG)
    choice = gs.select_menu(screen, "PONG", MODES, ["Scegli la modalità di gioco"], default=1,
                            backdrop=backdrop)
    if isinstance(choice, str):
        return choice
    mode = choice
    vs_cpu = mode < 3
    cpu = CPU(AI_LEVELS[mode]) if vs_cpu else None

    trail_sprites = _ball_sprites()
    particles = gs.Particles()
    shake = gs.ScreenShake(7)
    score_font_scale = 6

    def reset() -> tuple[Paddle, Paddle, Ball, list[int]]:
        b = Ball()
        b.serve(random.choice((-1, 1)))
        b.vx = b.vy = 0.0
        return Paddle(PADDLE_X_MARGIN), Paddle(W - PADDLE_X_MARGIN), b, [0, 0]

    left, right, ball, score = reset()
    serve_timer = SERVE_DELAY
    serve_dir = random.choice((-1, 1))
    if cpu:
        cpu.new_rally()

    def draw() -> None:
        screen.fill(gs.BG)
        pygame.draw.line(screen, (70, 70, 120), (0, TOP - 2), (W, TOP - 2), 4)
        pygame.draw.line(screen, (70, 70, 120), (0, BOTTOM + 2), (W, BOTTOM + 2), 4)
        for y in range(TOP + 6, BOTTOM, 26):
            pygame.draw.rect(screen, (60, 60, 105), (W // 2 - 3, y, 6, 14))
        blit_pixel_text(screen, str(score[0]), (W // 2 - 60, 30), score_font_scale, gs.NEON_CYAN, "midtop")
        blit_pixel_text(screen, str(score[1]), (W // 2 + 60, 30), score_font_scale, gs.NEON_MAGENTA, "midtop")
        left_label = "TU" if vs_cpu else "G1"
        right_label = ("CPU " + ("FACILE", "MEDIO", "DIFFICILE")[mode]) if vs_cpu else "G2"
        blit_pixel_text(screen, left_label, (W // 2 - 110, 40), 2, gs.TEXT_DIM, "topright")
        blit_pixel_text(screen, right_label, (W // 2 + 110, 40), 2, gs.TEXT_DIM, "topleft")
        for paddle, color in ((left, gs.NEON_CYAN), (right, gs.NEON_MAGENTA)):
            glow = pygame.Surface((PADDLE_W + 16, PADDLE_H + 16), pygame.SRCALPHA)
            pygame.draw.rect(glow, (*color, 50), glow.get_rect(), border_radius=8)
            screen.blit(glow, paddle.rect.inflate(16, 16))
            c = gs.WHITE if paddle.flash > 0 else color
            pygame.draw.rect(screen, c, paddle.rect, border_radius=4)
        for i, (tx, ty) in enumerate(ball.trail):
            spr = trail_sprites[min(i, len(trail_sprites) - 1)]
            screen.blit(spr, spr.get_rect(center=(int(tx), int(ty))))
        if serve_timer <= 0 or int(serve_timer * 8) % 2 == 0:
            pygame.draw.circle(screen, gs.WHITE, (int(ball.x), int(ball.y)), BALL_R)
        if serve_timer > 0:
            blit_pixel_text(screen, "PRONTI!", (W // 2, H // 2 + 60), 3, gs.NEON_YELLOW, "center")
        particles.draw(screen)
        shake.apply(screen)

    while True:
        dt = clock.tick()
        for e in pygame.event.get():
            if gs.handle_global_event(e):
                continue
            if e.type == pygame.QUIT:
                return "quit"
            if e.type == pygame.KEYDOWN and e.key in (pygame.K_ESCAPE, pygame.K_p, pygame.K_SPACE):
                choice = gs.in_game_menu(screen, "Pong", COMMANDS)
                clock.reset()
                if choice in ("menu", "quit"):
                    return choice
                if choice == "restart":
                    left, right, ball, score = reset()
                    serve_timer = SERVE_DELAY

        # --- input
        keys = pygame.key.get_pressed()
        step = PADDLE_SPEED * dt
        up1 = keys[pygame.K_w] or (vs_cpu and keys[pygame.K_UP])
        down1 = keys[pygame.K_s] or (vs_cpu and keys[pygame.K_DOWN])
        if up1:
            left.move(-step)
        if down1:
            left.move(step)
        if cpu:
            cpu.update(dt, right, ball)
        else:
            if keys[pygame.K_UP]:
                right.move(-step)
            if keys[pygame.K_DOWN]:
                right.move(step)

        # --- serve
        if serve_timer > 0:
            serve_timer -= dt
            if serve_timer <= 0:
                ball.serve(serve_dir)
                if cpu:
                    cpu.new_rally()
                sfx.play("blip")

        # --- ball physics
        if serve_timer <= 0:
            ball.trail.append((ball.x, ball.y))
            ball.x += ball.vx * dt
            ball.y += ball.vy * dt
            if ball.y - BALL_R < TOP:
                ball.y = TOP + BALL_R
                ball.vy = abs(ball.vy)
                sfx.play("wall")
            elif ball.y + BALL_R > BOTTOM:
                ball.y = BOTTOM - BALL_R
                ball.vy = -abs(ball.vy)
                sfx.play("wall")

            for paddle, direction in ((left, 1), (right, -1)):
                moving_towards = (ball.vx < 0) if direction == 1 else (ball.vx > 0)
                if moving_towards and ball.rect.colliderect(paddle.rect):
                    offset = max(-1.0, min(1.0, (ball.y - paddle.y) / (PADDLE_H / 2)))
                    angle = offset * MAX_BOUNCE_ANGLE
                    ball.speed = min(BALL_MAX_SPEED, ball.speed * SPEEDUP)
                    ball.vx = direction * ball.speed * math.cos(angle)
                    ball.vy = ball.speed * math.sin(angle)
                    ball.x = (paddle.rect.right + BALL_R) if direction == 1 else (paddle.rect.left - BALL_R)
                    paddle.flash = 0.08
                    color = gs.NEON_CYAN if direction == 1 else gs.NEON_MAGENTA
                    particles.burst(ball.x, ball.y, (color, gs.WHITE), 10,
                                    speed=(80, 260), life=(0.15, 0.4),
                                    angle=0 if direction == 1 else math.pi, spread=2.2)
                    sfx.play("hit")
                    if cpu and direction == 1:
                        cpu.new_rally()

            scorer = None
            if ball.x < -BALL_R * 2:
                scorer = 1
            elif ball.x > W + BALL_R * 2:
                scorer = 0
            if scorer is not None:
                score[scorer] += 1
                sfx.play("score")
                shake.add(0.45)
                particles.burst(W // 2 + (60 if scorer else -60), 60,
                                gs.NEON_MAGENTA if scorer else gs.NEON_CYAN, 30,
                                speed=(60, 220), life=(0.4, 0.9))
                serve_dir = -1 if scorer == 1 else 1   # serve towards who conceded
                ball.vx = ball.vy = 0.0
                ball.x, ball.y = W / 2, H / 2
                ball.trail.clear()
                serve_timer = SERVE_DELAY

        for paddle in (left, right):
            paddle.flash = max(0.0, paddle.flash - dt)
        particles.update(dt)
        shake.update(dt)
        draw()
        gs.present(screen)

        # --- victory
        if max(score) >= WIN_SCORE:
            left_won = score[0] > score[1]
            if vs_cpu:
                title = "HAI VINTO!" if left_won else "HAI PERSO!"
                if left_won:
                    wins = (get_best(load_scores, "pong_wins", 0) or 0) + 1
                    save_scores({"pong_wins": wins})
                lines = [f"Punteggio finale: {score[0]} - {score[1]}",
                         f"Vittorie contro la CPU: {get_best(load_scores, 'pong_wins', 0) or 0}"]
            else:
                title = "VINCE G1!" if left_won else "VINCE G2!"
                lines = [f"Punteggio finale: {score[0]} - {score[1]}"]
            choice = gs.end_screen(screen, title, lines, win=left_won or not vs_cpu)
            clock.reset()
            if choice in ("menu", "quit"):
                return choice
            left, right, ball, score = reset()
            serve_timer = SERVE_DELAY


if __name__ == "__main__":
    main()
    gs.shutdown()
