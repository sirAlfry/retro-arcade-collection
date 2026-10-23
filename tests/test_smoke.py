"""
End-to-end smoke tests: every game is actually *played* for a few hundred
frames without a window, with scripted key presses, then closed.

They catch crashes in drawing code, menus and game loops that unit tests on
pure logic would never see.
"""
from __future__ import annotations

import importlib

import pygame
import pytest

import retro_arcade_interface as launcher

K = pygame

# (module, frames, [(frame, keys...)]) - frame 2 confirms the pre-game menus
GAMES = [
    ("snake", [(5, K.K_RIGHT), (40, K.K_UP), (70, K.K_LEFT), (100, K.K_DOWN)]),
    ("tetris", [(10, K.K_LEFT), (20, K.K_UP), (30, K.K_SPACE), (40, K.K_c), (60, K.K_z),
                (80, K.K_SPACE), (100, K.K_RIGHT), (120, K.K_SPACE)]),
    ("pong", [(2, K.K_RETURN), (50, K.K_w)]),
    ("breakout", [(30, K.K_SPACE), (60, K.K_LEFT)]),
    ("space_invaders", [(f, K.K_SPACE) for f in range(100, 280, 20)]),
    ("maze_runner", [(2, K.K_RETURN), (20, K.K_RIGHT), (30, K.K_DOWN), (40, K.K_h)]),
    ("memory_game", [(2, K.K_RETURN), (20, K.K_RETURN), (30, K.K_RIGHT), (40, K.K_RETURN)]),
    ("puzzle15", [(10, K.K_UP), (20, K.K_LEFT), (30, K.K_DOWN), (40, K.K_r)]),
    ("tris", [(2, K.K_RETURN), (10, K.K_RETURN), (100, K.K_RIGHT), (110, K.K_RETURN)]),
]


@pytest.mark.parametrize(("module_name", "presses"), GAMES, ids=[g[0] for g in GAMES])
def test_game_runs_and_quits(scripted, module_name, presses):
    for frame, key in presses:
        scripted.at(frame, scripted.key(key))
    scripted.max_frames = 300
    module = importlib.import_module(module_name)
    assert module.main() == "quit"
    assert scripted.frame >= 300


@pytest.mark.parametrize("module_name", [g[0] for g in GAMES])
def test_pause_menu_back_to_launcher(scripted, module_name):
    """ESC opens the pause menu, M returns 'menu' to the launcher."""
    scripted.at(2, scripted.key(K.K_RETURN))   # skip pre-game menus (ignored elsewhere)
    scripted.at(30, scripted.key(K.K_ESCAPE))
    scripted.at(35, scripted.key(K.K_m))
    scripted.max_frames = 200
    module = importlib.import_module(module_name)
    assert module.main() == "menu"


def test_escape_on_pregame_menu_goes_back(scripted):
    scripted.at(3, scripted.key(K.K_ESCAPE))
    import pong
    assert pong.main() == "menu"


def test_launcher_session(scripted):
    """Navigate, open credits, launch a game, come back and quit."""
    scripted.at(5, scripted.key(K.K_RIGHT))
    scripted.at(10, scripted.key(K.K_c))
    scripted.at(30, scripted.key(K.K_ESCAPE))
    scripted.at(40, scripted.key(K.K_RETURN))        # launch Snake
    scripted.at(60, scripted.key(K.K_ESCAPE))
    scripted.at(65, scripted.key(K.K_m))             # back to the launcher
    scripted.at(90, scripted.key(K.K_ESCAPE))        # quit
    scripted.max_frames = 400
    launcher.main([])
    assert 90 <= scripted.frame < 400


def test_launcher_preview_image(tmp_path):
    out = tmp_path / "preview.png"
    launcher.render_preview(str(out))
    assert out.exists() and out.stat().st_size > 10_000


def test_catalogue_is_consistent():
    assert len(launcher.GAMES) == len(launcher.THUMB_DRAWERS) == 9
    for info in launcher.GAMES:
        module = importlib.import_module(info.module)
        assert callable(getattr(module, info.func))
        assert launcher.find_game(info.module) is info
        assert launcher.find_game(info.name.upper()) is info
    assert launcher.find_game("nope") is None


def test_layout_fits_the_screen():
    rects = launcher.tile_rects()
    screen = pygame.Rect(0, 0, launcher.W, launcher.H)
    for i, r in enumerate(rects):
        assert screen.contains(r)
        assert not r.colliderect(launcher.INFO_RECT)
        for other in rects[i + 1:]:
            assert not r.colliderect(other)
    assert screen.contains(launcher.INFO_RECT)


def test_crashing_game_is_reported_not_fatal(monkeypatch):
    import snake

    def boom(*_args):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(snake, "main", boom)
    result = launcher.launch_game("Snake", lambda: {}, lambda s: None)
    assert isinstance(result, RuntimeError)
