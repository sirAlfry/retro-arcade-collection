# space_invaders.py
"""
Space Invaders - defend the Earth from the marching aliens.

Features:
    * classic 11 x 5 formation with three animated pixel-art alien types
      (30 / 20 / 10 points), drawn from bitmaps - no image files
    * the march speeds up as the aliens die, with the iconic 4-note bass line
    * four destructible bunkers that erode bullet by bullet
    * the mystery UFO (50-300 points), shootable enemy bullets
    * lives with temporary invulnerability, waves that start lower and faster
    * persistent high score
"""
from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass

import pygame

import game_shared as gs
import sfx
from pixel_font import blit_pixel_text
from scores import get_best, record_best

W, H = gs.W, gs.H
HUD_H = 40
GROUND_Y = H - 26
SCALE = 3

PLAYER_Y = GROUND_Y - 34
PLAYER_SPEED = 300.0
PLAYER_BULLET_SPEED = 640.0
MAX_PLAYER_BULLETS = 2
FIRE_COOLDOWN = 0.28
INVULNERABLE_TIME = 1.6
START_LIVES = 3

COLS, ROWS = 11, 5
SPACING_X, SPACING_Y = 46, 36
STEP_X, STEP_DOWN = 10, 18
ENEMY_BULLET_SPEED = 250.0

BUNKER_CELL = 4
BUNKER_Y = PLAYER_Y - 90

COMMANDS = [
    "Frecce o A/D: muovi   SPAZIO: spara",
    "Gli scudi si consumano!  UFO: 50-300 punti",
]

SPRITES: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "squid": (
        ("...##...", "..####..", ".######.", "##.##.##", "########", "..#..#..", ".#.##.#.", "#.#..#.#"),
        ("...##...", "..####..", ".######.", "##.##.##", "########", ".#.##.#.", "#......#", ".#....#."),
    ),
    "crab": (
        ("..#.....#..", "...#...#...", "..#######..", ".##.###.##.", "###########",
         "#.#######.#", "#.#.....#.#", "...##.##..."),
        ("..#.....#..", "#..#...#..#", "#.#######.#", "###.###.###", "###########",
         ".#########.", "..#.....#..", ".#.......#."),
    ),
    "octopus": (
        ("....####....", ".##########.", "############", "###..##..###", "############",
         "...##..##...", "..##.##.##..", "##........##"),
        ("....####....", ".##########.", "############", "###..##..###", "############",
         "..###..###..", ".##..##..##.", "..##....##.."),
    ),
}
PLAYER_ART = ("......#......", ".....###.....", ".....###.....", ".###########.",
              "#############", "#############", "#############", "#############")
UFO_ART = (".....######.....", "...##########...", "..############..", ".##.##.##.##.##.",
           "################", "..###..##..###..", "...#........#...")
EXPLOSION_ART = ("#...#...#", ".#..#..#.", "..#...#..", "##.....##", "..#...#..",
                 ".#..#..#.", "#...#...#")
BUNKER_ART = ("....############....", "...##############...", "..################..",
              ".##################.", "####################", "####################",
              "####################", "####################", "####################",
              "######........######", "#####..........#####", "####............####",
              "####............####")

ROW_TYPES = ("squid", "crab", "crab", "octopus", "octopus")
TYPE_POINTS = {"squid": 30, "crab": 20, "octopus": 10}
TYPE_COLORS = {"squid": gs.NEON_MAGENTA, "crab": gs.NEON_CYAN, "octopus": gs.NEON_GREEN}


def bitmap_surface(art: tuple[str, ...], color: gs.Color, scale: int = SCALE) -> pygame.Surface:
    """Turn a list of '#'/'.' strings into a transparent sprite."""
    surf = pygame.Surface((len(art[0]) * scale, len(art) * scale), pygame.SRCALPHA)
    for y, row in enumerate(art):
        for x, ch in enumerate(row):
            if ch == "#":
                surf.fill(color, (x * scale, y * scale, scale, scale))
    return surf


@dataclass
class Alien:
    col: int
    row: int
    kind: str
    alive: bool = True

    def rect(self, fx: float, fy: float) -> pygame.Rect:
        w = len(SPRITES[self.kind][0][0]) * SCALE
        h = 8 * SCALE
        cx = int(fx + self.col * SPACING_X + SPACING_X // 2)
        return pygame.Rect(cx - w // 2, int(fy + self.row * SPACING_Y), w, h)


@dataclass
class Bullet:
    x: float
    y: float
    vy: float
    zigzag: bool = False

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x) - 2, int(self.y) - 6, 4, 12)


class Bunker:
    """A destructible shield made of small square cells."""

    def __init__(self, x: int, y: int) -> None:
        self.x, self.y = x, y
        self.cells = {(cx, cy) for cy, row in enumerate(BUNKER_ART)
                      for cx, ch in enumerate(row) if ch == "#"}

    def cell_rect(self, cx: int, cy: int) -> pygame.Rect:
        return pygame.Rect(self.x + cx * BUNKER_CELL, self.y + cy * BUNKER_CELL, BUNKER_CELL, BUNKER_CELL)

    @property
    def bounds(self) -> pygame.Rect:
        return pygame.Rect(self.x, self.y, len(BUNKER_ART[0]) * BUNKER_CELL, len(BUNKER_ART) * BUNKER_CELL)

    def hit(self, rect: pygame.Rect, splash: int = 2) -> bool:
        """Erode the cells touched by ``rect``. Returns True if something was hit."""
        if not self.cells or not rect.colliderect(self.bounds):
            return False
        touched = [c for c in self.cells if self.cell_rect(*c).colliderect(rect)]
        if not touched:
            return False
        for cx, cy in touched:
            for dx in range(-splash, splash + 1):
                for dy in range(-splash, splash + 1):
                    if abs(dx) + abs(dy) <= splash and random.random() < 0.65:
                        self.cells.discard((cx + dx, cy + dy))
            self.cells.discard((cx, cy))
        return True

    def draw(self, screen: pygame.Surface) -> None:
        for cx, cy in self.cells:
            screen.fill(gs.NEON_GREEN, self.cell_rect(cx, cy))


def main(load_scores: Callable[[], dict] | None = None,
         save_scores: Callable[[dict], None] | None = None) -> str:
    """
    Play Space Invaders.

    Returns:
        ``"menu"`` or ``"quit"``.
    """
    load_scores, save_scores = gs.ensure_scores(load_scores, save_scores)
    screen = gs.setup_screen("Space Invaders")
    clock = gs.GameClock(60)
    particles = gs.Particles()
    popups = gs.FloatingTexts()
    shake = gs.ScreenShake(9)
    best = get_best(load_scores, "space_invaders", 0) or 0

    alien_sprites = {k: (bitmap_surface(a, TYPE_COLORS[k]), bitmap_surface(b, TYPE_COLORS[k]))
                     for k, (a, b) in SPRITES.items()}
    player_sprite = bitmap_surface(PLAYER_ART, gs.NEON_CYAN)
    ufo_sprite = bitmap_surface(UFO_ART, gs.NEON_RED)
    boom_sprite = bitmap_surface(EXPLOSION_ART, gs.WHITE)
    stars = [(random.randrange(W), random.randrange(HUD_H, GROUND_Y), random.choice((1, 1, 2)))
             for _ in range(70)]

    class Wave:
        """All the mutable state of one game (recreated on restart)."""

        def __init__(self) -> None:
            self.score = 0
            self.lives = START_LIVES
            self.level = 0
            self.player_x = W / 2.0
            self.invulnerable = 0.0
            self.bunkers = [Bunker(int(W * (i + 1) / 5 - 40), BUNKER_Y) for i in range(4)]
            self.next_wave()

        def next_wave(self) -> None:
            self.level += 1
            self.aliens = [Alien(c, r, ROW_TYPES[r]) for r in range(ROWS) for c in range(COLS)]
            self.fx = (W - COLS * SPACING_X) / 2
            self.fy = HUD_H + 56 + min(6, self.level - 1) * 12
            self.direction = 1
            self.step_timer = 0.0
            self.frame = 0
            self.march = 0
            self.shoot_timer = 1.5
            self.bullets: list[Bullet] = []
            self.enemy_bullets: list[Bullet] = []
            self.fire_cooldown = 0.0
            self.ufo_x: float | None = None
            self.ufo_dir = 1
            self.ufo_timer = random.uniform(15, 25)
            self.ufo_sound = 0.0
            self.explosions: list[list] = []  # [x, y, time_left]
            self.banner = 1.6

        @property
        def alive(self) -> list[Alien]:
            return [a for a in self.aliens if a.alive]

        def step_interval(self) -> float:
            ratio = len(self.alive) / (COLS * ROWS)
            return max(0.035, 0.05 + 0.65 * ratio) / (1 + 0.12 * (self.level - 1))

    g = Wave()

    def player_rect() -> pygame.Rect:
        return player_sprite.get_rect(midtop=(int(g.player_x), PLAYER_Y))

    def kill_player() -> None:
        g.lives -= 1
        g.invulnerable = INVULNERABLE_TIME
        g.enemy_bullets.clear()
        pr = player_rect()
        sfx.play("explosion")
        shake.add(0.8)
        particles.burst(pr.centerx, pr.centery, (gs.NEON_CYAN, gs.WHITE, gs.NEON_YELLOW), 40,
                        speed=(60, 300), life=(0.4, 1.0), gravity=200)

    def update(dt: float) -> str | None:
        """Advance the simulation. Returns ``"lost"`` when the game is over."""
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            g.player_x -= PLAYER_SPEED * dt
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            g.player_x += PLAYER_SPEED * dt
        g.player_x = max(30.0, min(W - 30.0, g.player_x))
        g.fire_cooldown = max(0.0, g.fire_cooldown - dt)
        g.invulnerable = max(0.0, g.invulnerable - dt)

        # --- formation march
        g.step_timer += dt
        if g.step_timer >= g.step_interval():
            g.step_timer = 0.0
            g.frame ^= 1
            sfx.play(("step", "step2", "step3", "step4")[g.march % 4], 0.6)
            g.march += 1
            rects = [a.rect(g.fx, g.fy) for a in g.alive]
            if rects:
                left = min(r.left for r in rects)
                right = max(r.right for r in rects)
                if (g.direction > 0 and right + STEP_X > W - 16) or (g.direction < 0 and left - STEP_X < 16):
                    g.fy += STEP_DOWN
                    g.direction *= -1
                else:
                    g.fx += STEP_X * g.direction

        alive = g.alive
        # aliens erase bunkers they walk through / reach the player = game over
        for a in alive:
            r = a.rect(g.fx, g.fy)
            for b in g.bunkers:
                b.hit(r, splash=0)
            if r.bottom >= PLAYER_Y:
                return "lost"

        # --- alien fire: a random column's lowest alien shoots
        g.shoot_timer -= dt
        max_enemy_bullets = 2 + g.level // 2
        if g.shoot_timer <= 0 and alive:
            g.shoot_timer = random.uniform(0.5, 1.3) / (1 + 0.15 * (g.level - 1))
            if len(g.enemy_bullets) < max_enemy_bullets:
                bottoms: dict[int, Alien] = {}
                for a in alive:
                    if a.col not in bottoms or a.row > bottoms[a.col].row:
                        bottoms[a.col] = a
                shooter = random.choice(list(bottoms.values()))
                r = shooter.rect(g.fx, g.fy)
                g.enemy_bullets.append(Bullet(r.centerx, r.bottom, ENEMY_BULLET_SPEED, random.random() < 0.5))
                sfx.play("enemy_shoot", 0.5)

        # --- UFO
        if g.ufo_x is None:
            g.ufo_timer -= dt
            if g.ufo_timer <= 0:
                g.ufo_dir = random.choice((-1, 1))
                g.ufo_x = -40.0 if g.ufo_dir > 0 else W + 40.0
        else:
            g.ufo_x += 140 * g.ufo_dir * dt
            g.ufo_sound -= dt
            if g.ufo_sound <= 0:
                g.ufo_sound = 0.42
                sfx.play("ufo", 0.5)
            if g.ufo_x < -60 or g.ufo_x > W + 60:
                g.ufo_x = None
                g.ufo_timer = random.uniform(18, 30)
        ufo_rect = ufo_sprite.get_rect(center=(int(g.ufo_x), HUD_H + 22)) if g.ufo_x is not None else None

        # --- player bullets
        for b in list(g.bullets):
            b.y -= PLAYER_BULLET_SPEED * dt
            br = b.rect
            removed = False
            if b.y < HUD_H or any(bk.hit(br) for bk in g.bunkers):
                removed = True
            elif ufo_rect and br.colliderect(ufo_rect):
                pts = random.choice((50, 100, 150, 300))
                g.score += pts
                popups.add(str(pts), ufo_rect.centerx, ufo_rect.centery, gs.NEON_RED, 1.2, 3)
                particles.burst(ufo_rect.centerx, ufo_rect.centery, (gs.NEON_RED, gs.WHITE), 30,
                                speed=(60, 260), life=(0.3, 0.9))
                sfx.play("explosion")
                g.ufo_x = None
                g.ufo_timer = random.uniform(18, 30)
                removed = True
            else:
                for eb in g.enemy_bullets:
                    if br.colliderect(eb.rect.inflate(4, 0)):
                        g.enemy_bullets.remove(eb)
                        particles.burst(b.x, b.y, gs.WHITE, 6, speed=(40, 120), life=(0.1, 0.3))
                        removed = True
                        break
                if not removed:
                    for a in alive:
                        r = a.rect(g.fx, g.fy)
                        if br.colliderect(r):
                            a.alive = False
                            pts = TYPE_POINTS[a.kind]
                            g.score += pts
                            g.explosions.append([r.centerx, r.centery, 0.18])
                            particles.burst(r.centerx, r.centery, (TYPE_COLORS[a.kind], gs.WHITE), 12,
                                            speed=(50, 200), life=(0.2, 0.5))
                            popups.add(f"+{pts}", r.centerx, r.top, TYPE_COLORS[a.kind], 0.5)
                            sfx.play("small_explosion")
                            removed = True
                            break
            if removed:
                g.bullets.remove(b)

        # --- enemy bullets
        pr = player_rect().inflate(-6, -4)
        for eb in list(g.enemy_bullets):
            eb.y += eb.vy * dt
            er = eb.rect
            if eb.y > GROUND_Y:
                g.enemy_bullets.remove(eb)
                particles.burst(eb.x, GROUND_Y, gs.NEON_GREEN, 4, speed=(20, 80), life=(0.1, 0.3))
            elif any(bk.hit(er) for bk in g.bunkers):
                g.enemy_bullets.remove(eb)
            elif er.colliderect(pr) and g.invulnerable <= 0:
                kill_player()  # also clears every enemy bullet
                if g.lives <= 0:
                    return "lost"
                break

        for ex in g.explosions:
            ex[2] -= dt
        g.explosions = [e for e in g.explosions if e[2] > 0]

        if not g.alive:
            g.score += 100 * g.level
            sfx.play("levelup")
            popups.add(f"ONDATA SUPERATA! +{100 * g.level}", W // 2, H // 2, gs.NEON_GREEN, 1.4, 3)
            g.next_wave()
        return None

    def draw() -> None:
        screen.fill((8, 6, 20))
        for x, y, s in stars:
            screen.fill((90, 90, 140), (x, y, s, s))
        pygame.draw.line(screen, gs.NEON_GREEN, (0, GROUND_Y), (W, GROUND_Y), 2)
        for b in g.bunkers:
            b.draw(screen)
        for a in g.alive:
            r = a.rect(g.fx, g.fy)
            screen.blit(alien_sprites[a.kind][g.frame], r)
        for x, y, _t in g.explosions:
            screen.blit(boom_sprite, boom_sprite.get_rect(center=(int(x), int(y))))
        if g.ufo_x is not None:
            screen.blit(ufo_sprite, ufo_sprite.get_rect(center=(int(g.ufo_x), HUD_H + 22)))
        for b in g.bullets:
            pygame.draw.rect(screen, gs.NEON_YELLOW, b.rect)
        for eb in g.enemy_bullets:
            if eb.zigzag:
                off = 3 if int(eb.y / 8) % 2 else -3
                pts = [(eb.x, eb.y - 6), (eb.x + off, eb.y - 2), (eb.x - off, eb.y + 2), (eb.x, eb.y + 6)]
                pygame.draw.lines(screen, gs.NEON_RED, False, pts, 2)
            else:
                pygame.draw.rect(screen, gs.NEON_ORANGE, eb.rect.inflate(-1, 0))
        if g.lives > 0 and (g.invulnerable <= 0 or int(g.invulnerable * 10) % 2 == 0):
            screen.blit(player_sprite, player_rect())
        particles.draw(screen)
        popups.draw(screen)
        # HUD
        blit_pixel_text(screen, f"PUNTI {g.score}", (14, HUD_H // 2), 2, gs.NEON_CYAN, "midleft")
        blit_pixel_text(screen, f"RECORD {max(best, g.score)}", (W // 2 - 40, HUD_H // 2), 2,
                        gs.NEON_YELLOW, "center")
        blit_pixel_text(screen, f"ONDATA {g.level}", (W - 130, HUD_H // 2), 2, gs.NEON_GREEN, "midright")
        gs.draw_hearts(screen, g.lives, (W - 14, HUD_H // 2 - 7))
        if g.banner > 0:
            blit_pixel_text(screen, f"ONDATA {g.level}", (W // 2, H // 2 + 30), 5, gs.NEON_GREEN,
                            "center", glow=True)
        shake.apply(screen, (8, 6, 20))

    while True:
        dt = clock.tick()
        for e in pygame.event.get():
            if gs.handle_global_event(e):
                continue
            if e.type == pygame.QUIT:
                record_best(load_scores, save_scores, "space_invaders", g.score)
                return "quit"
            if e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_ESCAPE, pygame.K_p):
                    choice = gs.in_game_menu(screen, "Space Invaders", COMMANDS)
                    clock.reset()
                    if choice in ("menu", "quit"):
                        record_best(load_scores, save_scores, "space_invaders", g.score)
                        return choice
                    if choice == "restart":
                        g = Wave()
                        particles.clear()
                elif e.key in (pygame.K_SPACE, pygame.K_UP, pygame.K_w):
                    if g.fire_cooldown <= 0 and len(g.bullets) < MAX_PLAYER_BULLETS and g.lives > 0:
                        g.bullets.append(Bullet(g.player_x, PLAYER_Y - 4, -PLAYER_BULLET_SPEED))
                        g.fire_cooldown = FIRE_COOLDOWN
                        sfx.play("shoot")

        g.banner = max(0.0, g.banner - dt)
        outcome = update(dt) if g.banner <= 0.8 else None
        particles.update(dt)
        popups.update(dt)
        shake.update(dt)
        draw()
        gs.present(screen)

        if outcome == "lost":
            if g.lives > 0:  # invaded: the planet falls even with lives left
                kill_player()
            for _ in range(50):
                dt = clock.tick()
                particles.update(dt)
                shake.update(dt)
                draw()
                gs.present(screen)
                pygame.event.pump()
            new_record = record_best(load_scores, save_scores, "space_invaders", g.score)
            best = max(best, g.score)
            choice = gs.end_screen(screen, "GAME OVER", [
                f"Punteggio: {g.score}   Ondata: {g.level}",
                f"Record: {best}",
            ], new_record=new_record)
            clock.reset()
            if choice in ("menu", "quit"):
                return choice
            g = Wave()
            particles.clear()
            popups.clear()


if __name__ == "__main__":
    main()
    gs.shutdown()
