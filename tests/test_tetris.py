"""Rules of Tetris (pure logic, no window needed)."""
from __future__ import annotations

import random

from tetris import (
    LINE_SCORES,
    LOCK_DELAY,
    SHAPES,
    Piece,
    TetrisLogic,
    gravity_interval,
)


def make(seed: int = 1) -> TetrisLogic:
    return TetrisLogic(rng=random.Random(seed))


def test_seven_bag_gives_every_piece_once_per_bag():
    game = make()
    sequence = [game.piece.kind]
    for _ in range(13):
        game.spawn()
        sequence.append(game.piece.kind)
    assert sorted(sequence[:7]) == sorted(SHAPES)
    assert sorted(sequence[7:]) == sorted(SHAPES)


def test_piece_spawns_centered_at_the_top():
    game = make()
    assert game.piece is not None
    xs = [x for x, _ in game.piece.cells()]
    assert min(xs) >= 3 and max(xs) <= 6


def test_moves_stop_at_the_walls():
    game = make()
    while game.move(-1):
        pass
    assert min(x for x, _ in game.piece.cells()) == 0
    assert not game.move(-1)


def test_rotation_uses_wall_kicks():
    game = make()
    game.piece = Piece("I", 0, 0, rotation=1)  # vertical I touching the left wall
    while game.move(-1):
        pass
    assert game.rotate(1)  # would collide without a kick
    assert all(0 <= x < game.cols for x, _ in game.piece.cells())


def test_hard_drop_scores_two_points_per_row_and_locks():
    game = make()
    start_y = game.piece.y
    distance = game.hard_drop()
    assert distance > 15
    assert game.score == 2 * distance
    assert any(game.board[game.rows - 1])
    assert game.piece is not None and game.piece.y <= start_y + 1  # next piece spawned


def test_line_clear_scoring_uses_the_level():
    game = make()
    game.level = 3
    for x in range(game.cols - 1):
        game.board[game.rows - 1][x] = "Z"
    game.piece = Piece("I", game.cols - 1, 0, rotation=1)  # vertical I fills the last column
    game.piece.x = game.cols - 3  # column offset inside the 4x4 box
    game.hard_drop()
    assert game.clearing_rows == [game.rows - 1]
    assert game.score >= LINE_SCORES[1] * 3
    game.update(1.0)  # finish the animation
    assert not game.clearing_rows
    assert not any(game.board[game.rows - 1][: game.cols - 3])


def test_four_lines_is_a_tetris():
    game = make()
    for y in range(game.rows - 4, game.rows):
        for x in range(game.cols - 1):
            game.board[y][x] = "J"
    game.piece = Piece("I", game.cols - 3, 0, rotation=1)
    game.hard_drop()
    assert len(game.clearing_rows) == 4
    assert "lines4" in game.pop_events()


def test_hold_only_once_per_piece():
    game = make()
    first = game.piece.kind
    assert game.hold_piece()
    assert game.hold == first
    assert not game.hold_piece()
    game.hard_drop()
    assert game.hold_piece()  # allowed again after locking


def test_lock_delay():
    game = make()
    while game.soft_drop():
        pass
    assert game.on_ground
    game.update(LOCK_DELAY * 0.5)
    assert game.piece is not None and game.on_ground  # still movable
    game.update(LOCK_DELAY)
    assert "lock" in game.pop_events()


def test_block_out_ends_the_game():
    game = make()
    for y in range(3):
        for x in range(game.cols):
            game.board[y][x] = "O"
    game.spawn()
    assert game.game_over


def test_gravity_gets_faster_with_levels():
    values = [gravity_interval(level) for level in range(1, 16)]
    assert values == sorted(values, reverse=True)
    assert values[0] == 1.0
    assert values[-1] >= 0.02
