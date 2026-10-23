# memory_game.py
"""
Memory Game - find all the pairs with as few moves as possible.

* Three board sizes: 4x3 (6 pairs), 6x3 (9 pairs), 6x4 (12 pairs)
* 12 hand-drawn pixel-art icons (no more plain letters), each with its colour
* a real "card flip" animation (the card turns on its vertical axis)
* playable with the mouse *or* the keyboard (arrows + ENTER)
* a move = one attempt (two cards); best result saved for each board size
"""
from __future__ import annotations

import math
import random
from collections.abc import Callable
from dataclasses import dataclass

import pygame

import game_shared as gs
import sfx
from pixel_font import blit_pixel_text
from scores import get_best, record_best

W, H = gs.W, gs.H
HUD_H = 44
GAP = 12
FLIP_SPEED = 5.0       # flips per second
MISMATCH_DELAY = 0.75  # seconds both wrong cards stay visible

COMMANDS = [
    "Clic su una carta per girarla",
    "Oppure frecce + INVIO / SPAZIO",
]


@dataclass(frozen=True)
class BoardSize:
    label: str
    key: str
    cols: int
    rows: int


SIZES = (
    BoardSize("FACILE  4 X 3", "easy", 4, 3),
    BoardSize("NORMALE  6 X 3", "normal", 6, 3),
    BoardSize("DIFFICILE  6 X 4", "hard", 6, 4),
)

# 7x7 pixel-art icons, each with its own colour.
ICONS: dict[str, tuple[tuple[str, ...], gs.Color]] = {
    "heart": ((".##.##.", "#######", "#######", "#######", ".#####.", "..###..", "...#..."), gs.NEON_RED),
    "star": (("...#...", "...#...", "#######", ".#####.", "..###..", ".##.##.", "##...##"), gs.NEON_YELLOW),
    "diamond": (("...#...", "..###..", ".#####.", "#######", ".#####.", "..###..", "...#..."), gs.NEON_CYAN),
    "club": (("..###..", "..###..", "##.#.##", "#######", "##.#.##", "...#...", "..###.."), gs.NEON_GREEN),
    "spade": (("...#...", "..###..", ".#####.", "#######", "#######", "...#...", "..###.."), gs.NEON_PURPLE),
    "moon": (("..###..", ".##....", "##.....", "##.....", "##.....", ".##....", "..###.."), (180, 200, 255)),
    "note": (("...###.", "...#.##", "...#...", "...#...", ".###...", "####...", ".##...."), gs.NEON_MAGENTA),
    "bolt": (("...###.", "..###..", ".###...", "#######", "...###.", "..###..", ".##...."), gs.NEON_ORANGE),
    "smile": ((".#####.", "#######", "##.#.##", "#######", "#.###.#", "##...##", ".#####."), (200, 255, 60)),
    "mushroom": (("..###..", ".#.#.#.", "#######", "#.###.#", "..#.#..", "..#.#..", "..###.."),
                 (255, 120, 170)),
    "crown": (("#..#..#", "##.#.##", "#######", "#######", "#######", ".......", "#######"), (255, 200, 40)),
    "ghost": (("..###..", ".#####.", "##.#.##", "#######", "#######", "#######", "#.#.#.#"), gs.NEON_BLUE),
}


@dataclass
class Card:
    icon: str
    rect: pygame.Rect
    face_up: bool = False
    matched: bool = False
    flip: float = 0.0       # 0 = back, 1 = face (animated)
    glow: float = 0.0       # match / mismatch highlight timer
    wrong: bool = False


_icon_cache: dict[tuple[str, int], pygame.Surface] = {}


def icon_surface(name: str, scale: int) -> pygame.Surface:
    key = (name, scale)
    if key not in _icon_cache:
        art, color = ICONS[name]
        surf = pygame.Surface((7 * scale, 7 * scale), pygame.SRCALPHA)
        shade = gs.lerp_color(color, gs.BLACK, 0.55)
        depth = max(1, scale // 4)  # drop-shadow offset
        for y, row in enumerate(art):
            for x, ch in enumerate(row):
                if ch == "#":
                    surf.fill(shade, (x * scale + depth, y * scale + depth, scale, scale))
        for y, row in enumerate(art):
            for x, ch in enumerate(row):
                if ch == "#":
                    surf.fill(color, (x * scale, y * scale, scale, scale))
        _icon_cache[key] = surf
    return _icon_cache[key]


def deal(size: BoardSize, rng: random.Random | None = None) -> list[Card]:
    """Shuffle the icons and lay the cards out in a centred grid."""
    rng = rng or random.Random()
    pairs = (size.cols * size.rows) // 2
    names = rng.sample(list(ICONS), pairs) * 2
    rng.shuffle(names)
    card = min((W - 80) // size.cols - GAP, (H - HUD_H - 70) // size.rows - GAP, 130)
    total_w = size.cols * card + (size.cols - 1) * GAP
    total_h = size.rows * card + (size.rows - 1) * GAP
    ox = (W - total_w) // 2
    oy = HUD_H + (H - HUD_H - total_h) // 2
    return [Card(names[r * size.cols + c],
                 pygame.Rect(ox + c * (card + GAP), oy + r * (card + GAP), card, card))
            for r in range(size.rows) for c in range(size.cols)]


def main(load_scores: Callable[[], dict] | None = None,
         save_scores: Callable[[dict], None] | None = None) -> str:
    """
    Play Memory.

    Returns:
        ``"menu"`` or ``"quit"``.
    """
    load_scores, save_scores = gs.ensure_scores(load_scores, save_scores)
    screen = gs.setup_screen("Memory Game")
    clock = gs.GameClock(60)
    choice = gs.select_menu(screen, "MEMORY", [s.label for s in SIZES],
                            ["Scegli la dimensione della griglia"], default=1)
    if isinstance(choice, str):
        return choice
    size = SIZES[choice]
    record_key = f"memory_moves_{size.key}"
    particles = gs.Particles()
    popups = gs.FloatingTexts()

    class Round:
        def __init__(self) -> None:
            self.cards = deal(size)
            self.selected: list[Card] = []
            self.moves = 0
            self.streak = 0
            self.mismatch_timer = 0.0
            self.cursor = 0
            self.timer = gs.Stopwatch()
            self.timer.running = False
            self.best = get_best(load_scores, record_key)

    rnd = Round()
    t = 0.0

    def flip_card(index: int) -> None:
        if rnd.mismatch_timer > 0 or len(rnd.selected) >= 2:
            return
        card = rnd.cards[index]
        if card.face_up or card.matched:
            return
        card.face_up = True
        rnd.selected.append(card)
        rnd.timer.running = True
        sfx.play("flip")
        if len(rnd.selected) == 2:
            rnd.moves += 1
            a, b = rnd.selected
            if a.icon == b.icon:
                a.matched = b.matched = True
                a.glow = b.glow = 0.6
                rnd.selected.clear()
                rnd.streak += 1
                sfx.play("match")
                for c in (a, b):
                    particles.burst(c.rect.centerx, c.rect.centery, (ICONS[c.icon][1], gs.WHITE), 16,
                                    speed=(60, 220), life=(0.3, 0.7))
                if rnd.streak >= 2:
                    popups.add(f"COMBO X{rnd.streak}!", b.rect.centerx, b.rect.top, gs.NEON_YELLOW, 0.9)
            else:
                rnd.mismatch_timer = MISMATCH_DELAY
                a.wrong = b.wrong = True
                rnd.streak = 0

    def draw_card(card: Card, highlighted: bool) -> None:
        r = card.rect
        width = max(2, int(r.w * abs(math.cos(card.flip * math.pi))))
        face = card.flip > 0.5
        body = pygame.Rect(0, 0, width, r.h)
        body.center = r.center
        shadow = body.move(4, 5)
        pygame.draw.rect(screen, (4, 2, 12), shadow, border_radius=10)
        if face:
            border = gs.NEON_GREEN if card.matched else (gs.NEON_RED if card.wrong else (90, 90, 130))
            pygame.draw.rect(screen, (232, 232, 244), body, border_radius=10)
            pygame.draw.rect(screen, border, body, 3, border_radius=10)
            scale = max(2, r.w // 11)
            icon = icon_surface(card.icon, scale)
            if width < icon.get_width():
                icon = pygame.transform.scale(icon, (max(1, width - 4), icon.get_height()))
            screen.blit(icon, icon.get_rect(center=r.center))
            if card.matched:
                veil = pygame.Surface(body.size, pygame.SRCALPHA)
                pygame.draw.rect(veil, (10, 40, 20, 70), veil.get_rect(), border_radius=10)
                screen.blit(veil, body)
        else:
            pygame.draw.rect(screen, (60, 30, 110), body, border_radius=10)
            inner = body.inflate(-12, -12)
            if inner.w > 4:
                previous_clip = screen.get_clip()
                screen.set_clip(inner)  # keep the stripes inside the card
                for k in range(-r.h, r.w, 12):
                    pygame.draw.line(screen, (85, 45, 150), (inner.x + k, inner.y),
                                     (inner.x + k + inner.h, inner.bottom), 3)
                screen.set_clip(previous_clip)
                pygame.draw.rect(screen, (60, 30, 110), inner.inflate(-int(r.w / 2.2), -int(r.h / 2.2)),
                                 border_radius=6)
                if inner.w > r.w // 2:
                    blit_pixel_text(screen, "?", r.center, max(2, r.w // 28), gs.NEON_MAGENTA, "center")
            pygame.draw.rect(screen, gs.NEON_MAGENTA, body, 2, border_radius=10)
        if card.glow > 0:
            g = pygame.Surface((r.w + 24, r.h + 24), pygame.SRCALPHA)
            pygame.draw.rect(g, (*gs.NEON_GREEN, int(160 * card.glow)), g.get_rect(), 4, border_radius=14)
            screen.blit(g, r.inflate(24, 24))
        if highlighted:
            pulse = 0.5 + 0.5 * math.sin(t * 6)
            pygame.draw.rect(screen, gs.lerp_color(gs.NEON_YELLOW, gs.WHITE, pulse), r.inflate(10, 10), 3,
                             border_radius=13)

    def draw() -> None:
        screen.fill(gs.BG)
        for i, card in enumerate(rnd.cards):
            draw_card(card, i == rnd.cursor)
        particles.draw(screen)
        popups.draw(screen)
        pairs_left = sum(1 for c in rnd.cards if not c.matched) // 2
        blit_pixel_text(screen, f"MOSSE {rnd.moves}", (14, HUD_H // 2), 2, gs.NEON_CYAN, "midleft")
        blit_pixel_text(screen, f"TEMPO {rnd.timer}", (200, HUD_H // 2), 2, gs.NEON_GREEN, "midleft")
        blit_pixel_text(screen, f"COPPIE {len(rnd.cards) // 2 - pairs_left}/{len(rnd.cards) // 2}",
                        (390, HUD_H // 2), 2, gs.NEON_MAGENTA, "midleft")
        best = f"{rnd.best}" if rnd.best else "--"
        blit_pixel_text(screen, f"RECORD {best}", (W - 14, HUD_H // 2), 2, gs.NEON_YELLOW, "midright")

    while True:
        dt = clock.tick()
        t += dt
        for e in pygame.event.get():
            if gs.handle_global_event(e):
                continue
            if e.type == pygame.QUIT:
                return "quit"
            if e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_ESCAPE, pygame.K_p):
                    choice = gs.in_game_menu(screen, "Memory Game", COMMANDS)
                    clock.reset()
                    if choice in ("menu", "quit"):
                        return choice
                    if choice == "restart":
                        rnd = Round()
                        particles.clear()
                elif e.key in (pygame.K_LEFT, pygame.K_a):
                    rnd.cursor = (rnd.cursor - 1) % len(rnd.cards)
                elif e.key in (pygame.K_RIGHT, pygame.K_d):
                    rnd.cursor = (rnd.cursor + 1) % len(rnd.cards)
                elif e.key in (pygame.K_UP, pygame.K_w):
                    rnd.cursor = (rnd.cursor - size.cols) % len(rnd.cards)
                elif e.key in (pygame.K_DOWN, pygame.K_s):
                    rnd.cursor = (rnd.cursor + size.cols) % len(rnd.cards)
                elif e.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
                    flip_card(rnd.cursor)
            elif e.type == pygame.MOUSEMOTION:
                for i, card in enumerate(rnd.cards):
                    if card.rect.collidepoint(e.pos):
                        rnd.cursor = i
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                for i, card in enumerate(rnd.cards):
                    if card.rect.collidepoint(e.pos):
                        rnd.cursor = i
                        flip_card(i)

        # animations and the mismatch pause
        for card in rnd.cards:
            target = 1.0 if (card.face_up or card.matched) else 0.0
            if card.flip < target:
                card.flip = min(target, card.flip + FLIP_SPEED * dt)
            elif card.flip > target:
                card.flip = max(target, card.flip - FLIP_SPEED * dt)
            card.glow = max(0.0, card.glow - dt)
        if rnd.mismatch_timer > 0:
            rnd.mismatch_timer -= dt
            if rnd.mismatch_timer <= 0:
                for card in rnd.selected:
                    card.face_up = False
                    card.wrong = False
                rnd.selected.clear()
                sfx.play("error", 0.5)
        rnd.timer.update(dt)
        particles.update(dt)
        popups.update(dt)
        draw()
        gs.present(screen)

        if all(c.matched for c in rnd.cards) and all(c.flip >= 1.0 for c in rnd.cards):
            rnd.timer.stop()
            for _ in range(30):
                dt = clock.tick()
                t += dt
                particles.update(dt)
                popups.update(dt)
                draw()
                gs.present(screen)
                pygame.event.pump()
            new_record = record_best(load_scores, save_scores, record_key, rnd.moves, lower_is_better=True)
            best = get_best(load_scores, record_key, rnd.moves)
            perfect = len(rnd.cards) // 2
            choice = gs.end_screen(screen, "HAI VINTO!", [
                f"Mosse: {rnd.moves} (minimo possibile: {perfect})   Tempo: {rnd.timer}",
                f"Record ({size.label.split()[0].lower()}): {best} mosse",
            ], new_record=new_record, win=True)
            clock.reset()
            if choice in ("menu", "quit"):
                return choice
            rnd = Round()
            particles.clear()
            popups.clear()


if __name__ == "__main__":
    main()
    gs.shutdown()
