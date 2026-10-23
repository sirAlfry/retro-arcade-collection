# breakout.py
"""
Breakout - smash every brick without dropping the ball.

Features:
    * 5 hand-made levels (then they loop, faster), bricks with 1-3 hit points
    * sub-stepped, axis-separated collisions: the ball can't tunnel through
      bricks and bounces off the correct side (the old version only checked
      the ball centre and always flipped the vertical speed)
    * bounce angle controlled by where the ball hits the paddle
    * power-ups: L = longer paddle, M = multi-ball, S = slow ball, ♥ = +1 life
    * the ball waits on the paddle until you launch it (SPACE / click)
    * mouse OR keyboard (the mouse only takes over when you actually move it)
"""
from __future__ import annotations

import math
import random
from collections.abc import Callable
from dataclasses import dataclass, field

import pygame

import game_shared as gs
import sfx
from pixel_font import blit_pixel_text
from scores import get_best, record_best

W, H = gs.W, gs.H
HUD_H = 44
FIELD = pygame.Rect(16, HUD_H + 4, W - 32, H - HUD_H - 4)
PADDLE_W, PADDLE_W_WIDE, PADDLE_H = 104, 156, 14
PADDLE_Y = H - 48
PADDLE_SPEED = 620.0
BALL_R = 7
BALL_SPEED = 340.0
BALL_SPEED_MAX = 640.0
MAX_ANGLE = math.radians(65)
START_LIVES = 3
MAX_LIVES = 5
POWERUP_CHANCE = 0.12
POWERUP_SPEED = 150.0
MAX_BALLS = 8

BRICK_COLS = 10
BRICK_W, BRICK_H, BRICK_GAP = 68, 22, 4
BRICKS_X = (W - (BRICK_COLS * BRICK_W - BRICK_GAP)) // 2
BRICKS_Y = HUD_H + 40

ROW_COLORS = (gs.NEON_RED, gs.NEON_ORANGE, gs.NEON_YELLOW, gs.NEON_GREEN,
              gs.NEON_CYAN, gs.NEON_BLUE, gs.NEON_PURPLE)

# '.' = empty, digits = hit points
LEVELS: tuple[tuple[str, ...], ...] = (
    ("2222222222", "2222222222", "1111111111", "1111111111", "1111111111"),
    ("...1111...", "..122221..", ".12333321.", "..122221..", "...1111..."),
    ("1.1.1.1.1.", ".2.2.2.2.2", "3.3.3.3.3.", ".2.2.2.2.2", "1.1.1.1.1."),
    ("3333333333", "1........1", "1.222222.1", "1.2.33.2.1", "1.222222.1", "1........1"),
    ("1........1", "21......12", "321....123", "2321..1232", "1232112321", "3333333333"),
)

COMMANDS = [
    "Mouse o frecce / A-D: muovi   SPAZIO o clic: lancia",
    "Power-up: L larga  M multi-palla  S lenta  ♥ vita",
]

POWERUPS = {
    "L": gs.NEON_GREEN,
    "M": gs.NEON_CYAN,
    "S": gs.NEON_YELLOW,
    "♥": gs.NEON_RED,
}


@dataclass
class Brick:
    rect: pygame.Rect
    hp: int
    max_hp: int
    color: gs.Color


@dataclass
class Ball:
    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    stuck: bool = True

    @property
    def speed(self) -> float:
        return math.hypot(self.vx, self.vy)

    def set_speed(self, speed: float) -> None:
        current = self.speed
        if current > 0:
            self.vx *= speed / current
            self.vy *= speed / current


@dataclass
class PowerUp:
    kind: str
    x: float
    y: float


@dataclass
class State:
    level: int = 1
    score: int = 0
    lives: int = START_LIVES
    paddle_x: float = W / 2
    balls: list[Ball] = field(default_factory=list)
    bricks: list[Brick] = field(default_factory=list)
    powerups: list[PowerUp] = field(default_factory=list)
    wide_timer: float = 0.0
    slow_timer: float = 0.0
    banner_timer: float = 1.4

    @property
    def paddle_w(self) -> int:
        return PADDLE_W_WIDE if self.wide_timer > 0 else PADDLE_W

    @property
    def paddle_rect(self) -> pygame.Rect:
        r = pygame.Rect(0, 0, self.paddle_w, PADDLE_H)
        r.center = (int(self.paddle_x), PADDLE_Y)
        return r

    @property
    def base_speed(self) -> float:
        loop = (self.level - 1) // len(LEVELS)
        return min(BALL_SPEED_MAX, BALL_SPEED * (1 + 0.06 * (self.level - 1) + 0.15 * loop))


def build_bricks(level: int) -> list[Brick]:
    """Create the bricks of ``level`` (1-based, layouts loop)."""
    layout = LEVELS[(level - 1) % len(LEVELS)]
    bricks = []
    for row, line in enumerate(layout):
        for col, ch in enumerate(line[:BRICK_COLS]):
            if ch.isdigit() and ch != "0":
                hp = int(ch)
                rect = pygame.Rect(BRICKS_X + col * BRICK_W, BRICKS_Y + row * (BRICK_H + BRICK_GAP),
                                   BRICK_W - BRICK_GAP, BRICK_H)
                bricks.append(Brick(rect, hp, hp, ROW_COLORS[row % len(ROW_COLORS)]))
    return bricks


def circle_hits_rect(x: float, y: float, r: float, rect: pygame.Rect) -> bool:
    """True if the circle (x, y, r) overlaps ``rect``."""
    cx = max(rect.left, min(x, rect.right))
    cy = max(rect.top, min(y, rect.bottom))
    return (x - cx) ** 2 + (y - cy) ** 2 < r * r


def main(load_scores: Callable[[], dict] | None = None,
         save_scores: Callable[[dict], None] | None = None) -> str:
    """
    Play Breakout.

    Returns:
        ``"menu"`` or ``"quit"``.
    """
    load_scores, save_scores = gs.ensure_scores(load_scores, save_scores)
    screen = gs.setup_screen("Breakout")
    clock = gs.GameClock(60)
    particles = gs.Particles()
    popups = gs.FloatingTexts()
    shake = gs.ScreenShake(8)
    best = get_best(load_scores, "breakout", 0) or 0
    mouse_mode = False

    def new_state(level: int = 1, keep: State | None = None) -> State:
        st = State(level=level)
        if keep is not None:
            st.score, st.lives = keep.score, keep.lives
        st.bricks = build_bricks(level)
        st.balls = [Ball(st.paddle_x, PADDLE_Y - PADDLE_H // 2 - BALL_R)]
        return st

    s = new_state()

    def launch(ball: Ball) -> None:
        angle = random.uniform(-0.35, 0.35)
        speed = s.base_speed
        ball.vx = speed * math.sin(angle)
        ball.vy = -speed * math.cos(angle)
        ball.stuck = False
        sfx.play("blip")

    def damage(brick: Brick) -> None:
        brick.hp -= 1
        s.score += 5
        cx, cy = brick.rect.center
        if brick.hp <= 0:
            s.bricks.remove(brick)
            s.score += 10 * brick.max_hp
            sfx.play("brick")
            particles.burst(cx, cy, (brick.color, gs.WHITE), 16, speed=(60, 240),
                            life=(0.3, 0.7), gravity=420)
            popups.add(f"+{5 + 10 * brick.max_hp}", cx, cy, brick.color, 0.6)
            if random.random() < POWERUP_CHANCE:
                s.powerups.append(PowerUp(random.choice(list(POWERUPS)), cx, cy))
        else:
            sfx.play("hit", 0.7)
            particles.burst(cx, cy, gs.WHITE, 5, speed=(40, 120), life=(0.15, 0.3))

    def collide_bricks(ball: Ball) -> bool:
        for brick in s.bricks:
            if circle_hits_rect(ball.x, ball.y, BALL_R, brick.rect):
                damage(brick)
                return True
        return False

    def step_ball(ball: Ball, dt: float) -> None:
        if ball.stuck:
            ball.x = s.paddle_x + 18
            ball.y = PADDLE_Y - PADDLE_H // 2 - BALL_R
            return
        speed = ball.speed * (0.7 if s.slow_timer > 0 else 1.0)
        steps = max(1, math.ceil(speed * dt / (BALL_R * 0.7)))
        factor = (0.7 if s.slow_timer > 0 else 1.0) * dt / steps
        for _ in range(steps):
            # --- X axis
            ball.x += ball.vx * factor
            if ball.x - BALL_R < FIELD.left:
                ball.x = FIELD.left + BALL_R
                ball.vx = abs(ball.vx)
                sfx.play("wall", 0.6)
            elif ball.x + BALL_R > FIELD.right:
                ball.x = FIELD.right - BALL_R
                ball.vx = -abs(ball.vx)
                sfx.play("wall", 0.6)
            elif collide_bricks(ball):
                ball.x -= ball.vx * factor
                ball.vx = -ball.vx
            # --- Y axis
            ball.y += ball.vy * factor
            if ball.y - BALL_R < FIELD.top:
                ball.y = FIELD.top + BALL_R
                ball.vy = abs(ball.vy)
                sfx.play("wall", 0.6)
            elif collide_bricks(ball):
                ball.y -= ball.vy * factor
                ball.vy = -ball.vy
            # --- paddle
            pr = s.paddle_rect
            if ball.vy > 0 and circle_hits_rect(ball.x, ball.y, BALL_R, pr) and ball.y < pr.centery:
                offset = max(-1.0, min(1.0, (ball.x - pr.centerx) / (pr.w / 2)))
                angle = offset * MAX_ANGLE
                new_speed = min(BALL_SPEED_MAX, ball.speed * 1.015)
                ball.vx = new_speed * math.sin(angle)
                ball.vy = -new_speed * math.cos(angle)
                ball.y = pr.top - BALL_R
                sfx.play("hit")
                particles.burst(ball.x, pr.top, gs.NEON_CYAN, 6, speed=(40, 140),
                                life=(0.15, 0.3), angle=-math.pi / 2, spread=2.0)

    def apply_powerup(kind: str) -> None:
        sfx.play("powerup")
        px = s.paddle_x
        if kind == "L":
            s.wide_timer = 12.0
            popups.add("PADDLE LARGO!", px, PADDLE_Y - 30, gs.NEON_GREEN, 1.0)
        elif kind == "S":
            s.slow_timer = 9.0
            popups.add("RALLENTATORE!", px, PADDLE_Y - 30, gs.NEON_YELLOW, 1.0)
        elif kind == "♥":
            s.lives = min(MAX_LIVES, s.lives + 1)
            popups.add("+1 VITA!", px, PADDLE_Y - 30, gs.NEON_RED, 1.0)
        elif kind == "M":
            extra = []
            for b in s.balls:
                if b.stuck:
                    continue
                for da in (-0.45, 0.45):
                    nb = Ball(b.x, b.y, stuck=False)
                    ang = math.atan2(b.vx, -b.vy) + da
                    nb.vx = b.speed * math.sin(ang)
                    nb.vy = -abs(b.speed * math.cos(ang))
                    extra.append(nb)
            s.balls.extend(extra[:max(0, MAX_BALLS - len(s.balls))])
            popups.add("MULTI-PALLA!", px, PADDLE_Y - 30, gs.NEON_CYAN, 1.0)

    def draw() -> None:
        screen.fill(gs.BG)
        pygame.draw.rect(screen, gs.NEON_ORANGE, FIELD.inflate(6, 6), 3, border_radius=4)
        for b in s.bricks:
            damage_ratio = b.hp / b.max_hp
            base = gs.lerp_color(gs.BLACK, b.color, 0.45 + 0.55 * damage_ratio)
            pygame.draw.rect(screen, base, b.rect, border_radius=3)
            pygame.draw.line(screen, gs.lerp_color(base, gs.WHITE, 0.5),
                             (b.rect.x + 3, b.rect.y + 2), (b.rect.right - 4, b.rect.y + 2), 2)
            if b.max_hp > 1:
                for k in range(b.hp):
                    pygame.draw.rect(screen, gs.WHITE, (b.rect.x + 6 + k * 7, b.rect.bottom - 7, 4, 3))
            if b.max_hp >= 3 and b.hp == b.max_hp:
                pygame.draw.rect(screen, gs.WHITE, b.rect, 1, border_radius=3)
        for p in s.powerups:
            cap = pygame.Rect(0, 0, 34, 16)
            cap.center = (int(p.x), int(p.y))
            pygame.draw.rect(screen, POWERUPS[p.kind], cap, border_radius=8)
            pygame.draw.rect(screen, gs.WHITE, cap, 1, border_radius=8)
            blit_pixel_text(screen, p.kind, cap.center, 2, gs.BLACK, "center")
        pr = s.paddle_rect
        glow = pygame.Surface((pr.w + 20, pr.h + 20), pygame.SRCALPHA)
        pygame.draw.rect(glow, (*gs.NEON_CYAN, 45), glow.get_rect(), border_radius=12)
        screen.blit(glow, pr.inflate(20, 20))
        pygame.draw.rect(screen, gs.NEON_CYAN, pr, border_radius=7)
        pygame.draw.rect(screen, gs.WHITE, pr.inflate(-pr.w // 2, -8), border_radius=3)
        for ball in s.balls:
            color = gs.NEON_YELLOW if s.slow_timer > 0 else gs.WHITE
            pygame.draw.circle(screen, color, (int(ball.x), int(ball.y)), BALL_R)
        particles.draw(screen)
        popups.draw(screen)
        # HUD
        blit_pixel_text(screen, f"PUNTI {s.score}", (16, HUD_H // 2), 2, gs.NEON_CYAN, "midleft")
        blit_pixel_text(screen, f"RECORD {max(best, s.score)}", (290, HUD_H // 2), 2,
                        gs.NEON_YELLOW, "midleft")
        blit_pixel_text(screen, f"LIVELLO {s.level}", (540, HUD_H // 2), 2, gs.NEON_GREEN, "midleft")
        gs.draw_hearts(screen, s.lives, (W - 16, HUD_H // 2 - 7))
        timers = []
        if s.wide_timer > 0:
            timers.append(("L", s.wide_timer, gs.NEON_GREEN))
        if s.slow_timer > 0:
            timers.append(("S", s.slow_timer, gs.NEON_YELLOW))
        for k, (label, value, color) in enumerate(timers):
            blit_pixel_text(screen, f"{label} {value:0.0f}", (FIELD.right - 8, FIELD.bottom - 20 - k * 18),
                            2, color, "bottomright")
        if s.banner_timer > 0:
            blit_pixel_text(screen, f"LIVELLO {s.level}", (W // 2, H // 2 + 20), 5, gs.NEON_ORANGE,
                            "center", glow=True)
        if any(b.stuck for b in s.balls) and s.banner_timer <= 0:
            blit_pixel_text(screen, "SPAZIO O CLIC PER LANCIARE", (W // 2, PADDLE_Y - 60), 2,
                            gs.TEXT_DIM, "center")
        shake.apply(screen)

    while True:
        dt = clock.tick()
        for e in pygame.event.get():
            if gs.handle_global_event(e):
                continue
            if e.type == pygame.QUIT:
                record_best(load_scores, save_scores, "breakout", s.score)
                return "quit"
            if e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_ESCAPE, pygame.K_p):
                    choice = gs.in_game_menu(screen, "Breakout", COMMANDS)
                    clock.reset()
                    if choice in ("menu", "quit"):
                        record_best(load_scores, save_scores, "breakout", s.score)
                        return choice
                    if choice == "restart":
                        s = new_state()
                        particles.clear()
                elif e.key in (pygame.K_SPACE, pygame.K_UP, pygame.K_w):
                    for ball in s.balls:
                        if ball.stuck:
                            launch(ball)
                elif e.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_a, pygame.K_d):
                    mouse_mode = False
            elif e.type == pygame.MOUSEMOTION:
                mouse_mode = True
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                for ball in s.balls:
                    if ball.stuck:
                        launch(ball)

        # --- paddle
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            s.paddle_x -= PADDLE_SPEED * dt
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            s.paddle_x += PADDLE_SPEED * dt
        if mouse_mode and pygame.mouse.get_focused():
            s.paddle_x = pygame.mouse.get_pos()[0]
        half = s.paddle_w / 2
        s.paddle_x = max(FIELD.left + half, min(FIELD.right - half, s.paddle_x))

        # --- timers
        s.banner_timer = max(0.0, s.banner_timer - dt)
        s.wide_timer = max(0.0, s.wide_timer - dt)
        s.slow_timer = max(0.0, s.slow_timer - dt)

        # --- balls
        for ball in list(s.balls):
            step_ball(ball, dt)
            if ball.y - BALL_R > H:
                s.balls.remove(ball)
        if not s.balls:
            s.lives -= 1
            sfx.play("hurt")
            shake.add(0.6)
            s.wide_timer = s.slow_timer = 0.0
            s.powerups.clear()
            if s.lives > 0:
                s.balls = [Ball(s.paddle_x, PADDLE_Y)]

        # --- power-ups falling
        pr = s.paddle_rect
        for p in list(s.powerups):
            p.y += POWERUP_SPEED * dt
            if pr.inflate(10, 6).collidepoint(int(p.x), int(p.y)):
                s.powerups.remove(p)
                apply_powerup(p.kind)
            elif p.y > H:
                s.powerups.remove(p)

        particles.update(dt)
        popups.update(dt)
        shake.update(dt)
        draw()
        gs.present(screen)

        # --- level cleared / game over
        if not s.bricks:
            bonus = 250 * s.level
            s.score += bonus
            sfx.play("win")
            popups.add(f"LIVELLO COMPLETATO! +{bonus}", W // 2, H // 2, gs.NEON_GREEN, 1.6, 3)
            for _ in range(70):
                dt = clock.tick()
                popups.update(dt)
                particles.update(dt)
                draw()
                gs.present(screen)
                pygame.event.pump()
            s = new_state(s.level + 1, keep=s)
            clock.reset()
        elif s.lives <= 0:
            new_record = record_best(load_scores, save_scores, "breakout", s.score)
            best = max(best, s.score)
            choice = gs.end_screen(screen, "GAME OVER", [
                f"Punteggio: {s.score}   Livello raggiunto: {s.level}",
                f"Record: {best}",
            ], new_record=new_record)
            clock.reset()
            if choice in ("menu", "quit"):
                return choice
            s = new_state()
            particles.clear()
            popups.clear()


# Backwards-compatible name used by older launchers.
main_loop = main


if __name__ == "__main__":
    main()
    gs.shutdown()
