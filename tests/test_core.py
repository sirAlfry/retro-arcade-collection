"""Shared infrastructure: scores, pixel font, synthesizer, small physics helpers."""
from __future__ import annotations

import json
import random

import pygame
import pytest

import breakout
import pixel_font
import pong
import scores
import sfx
import space_invaders

# ---------------------------------------------------------------- scores


def test_scores_roundtrip(isolated_scores):
    store = scores.ScoreStore()
    assert store.path == isolated_scores
    store.save_scores({"snake": 12})
    store.save_scores({"tetris": 400})          # merge, not overwrite
    assert store.load_scores() == {"snake": 12, "tetris": 400}
    data = json.loads(isolated_scores.read_text(encoding="utf-8"))
    assert data["version"] == scores.SCHEMA_VERSION


def test_no_temp_files_left_behind(isolated_scores):
    scores.ScoreStore().save_scores({"a": 1})
    leftovers = [p.name for p in isolated_scores.parent.iterdir() if p.name.endswith(".tmp")]
    assert leftovers == []


def test_corrupted_file_is_quarantined(isolated_scores):
    isolated_scores.write_text("{ not json", encoding="utf-8")
    store = scores.ScoreStore()
    assert store.load_scores() == {}
    assert isolated_scores.with_name("scores.json.corrupt").exists()
    store.save_scores({"pong_wins": 1})
    assert store.load_scores() == {"pong_wins": 1}


def test_legacy_flat_format_is_read(isolated_scores):
    isolated_scores.write_text(json.dumps({"snake": 9, "tris_x": 2}), encoding="utf-8")
    assert scores.ScoreStore().load_scores() == {"snake": 9, "tris_x": 2}


def test_settings_live_next_to_scores(isolated_scores):
    store = scores.ScoreStore()
    store.save_scores({"snake": 1})
    store.set_setting("sound", False)
    assert store.get_setting("sound") is False
    assert store.load_scores() == {"snake": 1}


@pytest.mark.parametrize(("current", "value", "lower", "expected"), [
    (None, 10, False, True),
    (None, 0, False, False),     # a zero score is not a record
    (10, 12, False, True),
    (10, 8, False, False),
    (None, 30.5, True, True),
    (30.5, 29.0, True, True),
    (30.5, 31.0, True, False),
])
def test_record_best(current, value, lower, expected):
    load, save = scores.memory_store({} if current is None else {"k": current})
    assert scores.record_best(load, save, "k", value, lower_is_better=lower) is expected
    stored = load().get("k")
    assert stored == (value if expected else current)


def test_resolve_falls_back_to_the_json_store(isolated_scores):
    load, save = scores.resolve(None, None)
    save({"x": 1})
    assert json.loads(isolated_scores.read_text(encoding="utf-8"))["scores"] == {"x": 1}


# ---------------------------------------------------------------- pixel font


def test_glyph_table_is_consistent():
    for ch, rows in pixel_font._GLYPHS.items():
        assert len(rows) == pixel_font.GLYPH_HEIGHT, ch
        assert len({len(r) for r in rows}) == 1, ch
        assert set("".join(rows)) <= {"#", "."}, ch


def test_measure_and_render_sizes():
    pygame.init()
    w, h = pixel_font.measure("AB", 3)
    assert (w, h) == ((5 + 1 + 5) * 3, 7 * 3)
    surf = pixel_font.render_pixel_text("AB", 3)
    assert surf.get_size() == (w, h)
    assert pixel_font.render_pixel_text("AB", 3) is surf  # cached


def test_accents_and_unknown_characters():
    assert pixel_font.glyph_for("è") == pixel_font.glyph_for("E")
    assert pixel_font.glyph_for("à") == pixel_font.glyph_for("A")
    assert pixel_font.glyph_for("€") == pixel_font._FALLBACK


# ---------------------------------------------------------------- synthesizer


def test_every_recipe_synthesizes():
    rate = 22050
    for name, tones in sfx.RECIPES.items():
        samples = sfx.synthesize(tones, rate)
        expected = sum(max(1, int(t.dur * rate)) for t in tones)
        assert len(samples) == expected, name
        assert max(abs(s) for s in samples) <= 32767


def test_play_without_audio_device_never_crashes():
    sfx.play("eat")
    sfx.play("this-sound-does-not-exist")


# ---------------------------------------------------------------- physics helpers


def test_pong_prediction_handles_bounces():
    top, bottom = 0.0, 100.0
    # straight line
    assert pong.predict_y(0, 50, 10, 0, 100, top, bottom) == pytest.approx(50)
    # one bounce off the bottom wall: 50 + 100 = 150 -> mirrored to 50
    assert pong.predict_y(0, 50, 10, 10, 100, top, bottom) == pytest.approx(50)
    # moving away -> centre
    assert pong.predict_y(50, 10, -5, 0, 100, top, bottom) == pytest.approx(50)


def test_circle_rect_collision():
    rect = pygame.Rect(10, 10, 20, 10)
    assert breakout.circle_hits_rect(5, 15, 6, rect)
    assert not breakout.circle_hits_rect(0, 0, 5, rect)
    assert breakout.circle_hits_rect(20, 15, 1, rect)


@pytest.mark.parametrize("level", range(1, len(breakout.LEVELS) + 1))
def test_breakout_levels_fit_the_field(level):
    bricks = breakout.build_bricks(level)
    assert bricks
    for b in bricks:
        assert breakout.FIELD.contains(b.rect)
        assert 1 <= b.hp <= 3


def test_bunker_erodes():
    random.seed(0)
    bunker = space_invaders.Bunker(100, 100)
    before = len(bunker.cells)
    hit = bunker.hit(pygame.Rect(bunker.x + 20, bunker.y, 4, 12))
    assert hit and len(bunker.cells) < before
    assert not bunker.hit(pygame.Rect(0, 0, 4, 4))


def test_alien_sprites_have_two_frames_of_equal_size():
    for kind, (a, b) in space_invaders.SPRITES.items():
        assert len(a) == len(b) == 8, kind
        assert {len(r) for r in a} == {len(r) for r in b}, kind
