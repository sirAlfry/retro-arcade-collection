"""The Tic Tac Toe AI: correctness of the state and strength of the search."""
from __future__ import annotations

import random

import pytest

from game_ai import AIAlgorithm, GameAI, GameResult, TicTacToeState

X, O = 1, -1


def board(rows: str) -> list[list[int | None]]:
    """Build a board from a compact string like ``"XO. .X. ..O"``."""
    mapping = {"X": X, "O": O, ".": None}
    return [[mapping[ch] for ch in row] for row in rows.split()]


def human_can_beat(state: TicTacToeState, ai: GameAI) -> bool:
    """Explore *every* human reply: True if any line of play beats the AI (O)."""
    if state.is_terminal():
        return state.get_result(O) == GameResult.LOSS
    if state.current_player == X:
        return any(human_can_beat(state.make_move(m), ai) for m in state.get_legal_moves())
    return human_can_beat(state.make_move(ai.get_best_move(state)), ai)


@pytest.mark.parametrize("first_player", [X, O])
def test_hard_ai_is_unbeatable(first_player):
    ai = GameAI.for_level("hard", player_id=O, rng=random.Random(42))
    assert not human_can_beat(TicTacToeState(current_player=first_player), ai)


def test_alpha_beta_is_unbeatable_too():
    ai = GameAI("alpha_beta", difficulty=9, player_id=O)
    assert not human_can_beat(TicTacToeState(current_player=X), ai)


def test_ai_takes_the_win():
    state = TicTacToeState(board("OO. XX. X.."), current_player=O)
    ai = GameAI.for_level("hard", player_id=O)
    assert ai.get_best_move(state) == (0, 2)


def test_ai_blocks_the_threat():
    state = TicTacToeState(board("XX. .O. ..."), current_player=O)
    ai = GameAI.for_level("hard", player_id=O)
    assert ai.get_best_move(state) == (0, 2)


def test_winner_and_terminal_detection():
    s = TicTacToeState(board("XXX OO. ..."), current_player=O)
    assert s.get_winner() == X
    assert s.is_terminal()
    assert s.get_result(X) == GameResult.WIN
    assert s.get_result(O) == GameResult.LOSS
    draw = TicTacToeState(board("XOX XOO OXX"))
    assert draw.get_winner() is None and draw.get_result(X) == GameResult.DRAW


def test_make_move_is_immutable():
    s = TicTacToeState()
    s2 = s.make_move((1, 1))
    assert s.board[1][1] is None and s2.board[1][1] == X
    assert s2.current_player == O


def test_blunder_rate_one_plays_random_legal_moves():
    ai = GameAI("minimax", difficulty=9, player_id=O, blunder_rate=1.0, rng=random.Random(3))
    state = TicTacToeState(board("XX. .O. ..."), current_player=O)
    moves = {ai.get_best_move(state) for _ in range(40)}
    assert moves <= set(state.get_legal_moves())
    assert len(moves) > 1  # it really is random


def test_ties_are_broken_randomly():
    # On an empty board every corner/centre is "optimal": seeds should vary.
    picks = {GameAI.for_level("hard", player_id=X, rng=random.Random(seed))
             .get_best_move(TicTacToeState(current_player=X)) for seed in range(20)}
    assert len(picks) > 1


def test_unknown_algorithm_falls_back_to_minimax():
    assert GameAI("does-not-exist").algorithm == AIAlgorithm.MINIMAX


def test_slots_really_work():
    with pytest.raises(AttributeError):
        TicTacToeState().unexpected = 1  # type: ignore[attr-defined]
