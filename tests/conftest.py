"""
Shared pytest setup.

* SDL runs with dummy video/audio drivers, so the whole suite runs without
  opening windows or playing sounds (it even works on machines without a
  screen or a sound card).
* Every test gets its own temporary ``scores.json`` (never touches yours).
* ``scripted`` lets a test "play" a game: it fakes the clock (no waiting),
  injects key presses at given frames and closes the window at the end.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pygame  # noqa: E402
import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_scores(tmp_path, monkeypatch) -> Path:
    """Redirect the score file to a temporary folder for every test."""
    path = tmp_path / "scores.json"
    monkeypatch.setenv("RETRO_ARCADE_SCORES", str(path))
    return path


class _FakeClock:
    """Drop-in ``pygame.time.Clock`` that never sleeps."""

    def __init__(self) -> None:
        self._fps = 60

    def tick(self, fps: int = 0) -> int:
        return int(1000 / (fps or 60))

    def get_fps(self) -> float:
        return 60.0


class _Pressed:
    def __init__(self, held: set[int]) -> None:
        self.held = held

    def __getitem__(self, key: int) -> bool:
        return key in self.held


class Script:
    """Frame-based input script for headless game runs."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.frame = 0
        self.steps: dict[int, list] = {}
        self.max_frames = 300
        self.held: set[int] = set()
        real_get = pygame.event.get

        def fake_get(*args, **kwargs):
            self.frame += 1
            events = list(real_get(*args, **kwargs))
            for item in self.steps.get(self.frame, []):
                event = item() if callable(item) else item
                if event is not None:
                    events.append(event)
            if self.frame >= self.max_frames:
                events.append(pygame.event.Event(pygame.QUIT))
            return events

        monkeypatch.setattr(pygame.event, "get", fake_get)
        monkeypatch.setattr(pygame.key, "get_pressed", lambda: _Pressed(self.held))
        monkeypatch.setattr(pygame.time, "Clock", _FakeClock)
        monkeypatch.setattr(pygame.time, "wait", lambda ms: 0)
        monkeypatch.setattr(pygame.time, "delay", lambda ms: 0)

    # -- helpers ---------------------------------------------------------
    def at(self, frame: int, *events) -> Script:
        self.steps.setdefault(frame, []).extend(events)
        return self

    @staticmethod
    def key(k: int) -> pygame.event.Event:
        return pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode="", scancode=0)

    @staticmethod
    def click(pos: tuple[int, int]) -> pygame.event.Event:
        return pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1)

    def hold(self, k: int):
        return lambda: self.held.add(k)

    def release(self, k: int):
        return lambda: self.held.discard(k)


@pytest.fixture
def scripted(monkeypatch) -> Script:
    """A fresh :class:`Script` with pygame's input and clock patched."""
    return Script(monkeypatch)
