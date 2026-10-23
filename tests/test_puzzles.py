"""Puzzle 15, Maze Runner, Memory and Snake rules."""
from __future__ import annotations

import random
from collections import deque

import pytest

import maze_runner
import memory_game
import puzzle15
from snake import RED_POINTS, SnakeLogic

# ---------------------------------------------------------------- Puzzle 15


def test_solved_board_is_solvable():
    assert puzzle15.is_solvable(puzzle15.SOLVED)


def test_one_move_from_solution_is_solvable():
    # Regression: the first version rejected exactly these boards, so every
    # shuffle it produced was impossible to solve.
    board = puzzle15.SOLVED[:]
    puzzle15.slide(board, 14)
    assert puzzle15.is_solvable(board)


def test_swapping_two_tiles_makes_it_unsolvable():
    board = puzzle15.SOLVED[:]
    board[13], board[14] = board[14], board[13]
    assert not puzzle15.is_solvable(board)


@pytest.mark.parametrize("seed", range(50))
def test_shuffle_is_always_solvable_and_not_solved(seed):
    board = puzzle15.shuffled(random.Random(seed))
    assert sorted(board) == list(range(16))
    assert puzzle15.is_solvable(board)
    assert not puzzle15.is_solved(board)


def test_random_walks_stay_solvable():
    rng = random.Random(7)
    board = puzzle15.SOLVED[:]
    for _ in range(500):
        puzzle15.slide(board, rng.randrange(16))
        assert puzzle15.is_solvable(board)


def test_slide_moves_a_whole_row():
    board = puzzle15.SOLVED[:]          # blank at index 15
    moved = puzzle15.slide(board, 12)   # first tile of the last row
    assert moved == 3
    assert board[12:] == [0, 13, 14, 15]


def test_slide_rejects_diagonal_tiles():
    board = puzzle15.SOLVED[:]
    assert puzzle15.slide(board, 10) == 0


def test_push_moves_tile_in_arrow_direction():
    board = puzzle15.SOLVED[:]
    assert puzzle15.push(board, 1, 0) == 1     # RIGHT: tile 15 slides right
    assert board[14:16] == [0, 15]
    assert puzzle15.push(board, 0, 1) == 1     # DOWN: tile above the blank slides down
    assert board[14] == 11


# ---------------------------------------------------------------- Maze Runner


def floor_cells(grid):
    return {(x, y) for y, row in enumerate(grid) for x, v in enumerate(row) if v == 0}


@pytest.mark.parametrize("diff", maze_runner.DIFFICULTIES, ids=lambda d: d.key)
def test_maze_is_perfect_and_solvable(diff):
    grid = maze_runner.generate_maze(diff.cols, diff.rows, random.Random(5))
    floor = floor_cells(grid)
    # connected: BFS from the start reaches every floor cell
    seen = {(0, 0)}
    queue = deque([(0, 0)])
    edges = 0
    while queue:
        x, y = queue.popleft()
        for n in ((x + 1, y), (x, y + 1)):
            if n in floor:
                edges += 1
        for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if n in floor and n not in seen:
                seen.add(n)
                queue.append(n)
    assert seen == floor
    # a tree has exactly V - 1 edges: no loops -> "perfect" maze
    assert edges == len(floor) - 1
    goal = (len(grid[0]) - 1, len(grid) - 1)
    path = maze_runner.shortest_path(grid, (0, 0), goal)
    assert path[0] == (0, 0) and path[-1] == goal


def test_shortest_path_on_tiny_grid():
    grid = [[0, 0, 0],
            [1, 1, 0],
            [0, 0, 0]]
    assert maze_runner.shortest_path(grid, (0, 0), (0, 2)) == [
        (0, 0), (1, 0), (2, 0), (2, 1), (2, 2), (1, 2), (0, 2)]
    grid[1][2] = 1
    assert maze_runner.shortest_path(grid, (0, 0), (0, 2)) == []


def test_even_sizes_are_made_odd():
    grid = maze_runner.generate_maze(10, 8, random.Random(1))
    assert len(grid) % 2 == 1 and len(grid[0]) % 2 == 1


# ---------------------------------------------------------------- Memory


@pytest.mark.parametrize("size", memory_game.SIZES, ids=lambda s: s.key)
def test_memory_deal_has_pairs_and_fits_the_screen(size):
    cards = memory_game.deal(size, random.Random(2))
    assert len(cards) == size.cols * size.rows
    counts = {}
    for c in cards:
        counts[c.icon] = counts.get(c.icon, 0) + 1
    assert set(counts.values()) == {2}
    for i, a in enumerate(cards):
        assert a.rect.left >= 0 and a.rect.right <= memory_game.W
        assert a.rect.top >= memory_game.HUD_H and a.rect.bottom <= memory_game.H
        for b in cards[i + 1:]:
            assert not a.rect.colliderect(b.rect)


def test_memory_icons_are_7x7():
    for name, (art, _color) in memory_game.ICONS.items():
        assert len(art) == 7, name
        assert all(len(row) == 7 for row in art), name


# ---------------------------------------------------------------- Snake


def test_snake_eats_and_grows():
    game = SnakeLogic(random.Random(1), cols=10, rows=10)
    head = game.body[0]
    game.red = (head[0] + 1, head[1])
    game.started = True
    game.step()
    assert game.score == RED_POINTS
    assert len(game.body) == 4


def test_snake_ignores_reverse_and_buffers_turns():
    game = SnakeLogic(random.Random(1), cols=20, rows=20)
    game.turn((-1, 0))            # 180° turn: ignored
    assert not game.queue
    game.turn((0, -1))            # up...
    game.turn((-1, 0))            # ...then left, both kept
    assert list(game.queue) == [(0, -1), (-1, 0)]


def test_snake_dies_on_walls():
    game = SnakeLogic(random.Random(1), cols=6, rows=6)
    game.red = (0, 0)
    for _ in range(10):
        game.step()
    assert not game.alive


def test_snake_can_follow_its_own_tail():
    game = SnakeLogic(random.Random(1), cols=10, rows=10)
    game.body = [(5, 5), (5, 6), (4, 6), (4, 5)]  # head next to the tail
    game.direction = (0, -1)
    game.red = (0, 0)
    game.queue.append((-1, 0))
    game.step()                   # moves into the cell the tail is leaving
    assert game.alive
