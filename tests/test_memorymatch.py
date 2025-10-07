import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # type: ignore
from casinogames.memorymatch.MemoryMatch import MemoryMatch


@pytest.fixture()
def game():
    gm = MemoryMatch(player_id=1, bet=10, base_attempts=3)
    gm.board = [
        ("mario", False, False),
        ("mario", False, False),
        ("luigi", False, False),
        ("star", False, False),
    ]
    gm.revealed = []
    return gm


def test_initial_state(game):
    assert game.bet == 10
    assert game.base_attempts == 3
    assert game.remaining_attempts == 3
    assert game.stars == 0


def test_flip_and_match(game):
    assert game.flip_card(0) is True
    assert game.flip_card(1) is True
    assert game.revealed[-2:] == [0, 1]
    result = game.check_match()
    assert result is True
    symbol_a, flipped_a, matched_a = game.board[0]
    assert matched_a and flipped_a and symbol_a == "mario"


def test_mismatch_reduces_attempts(game):
    game.board[0] = ("mario", False, False)
    game.board[1] = ("luigi", False, False)
    assert game.flip_card(0)
    assert game.flip_card(1)
    result = game.check_match()
    assert result is False
    assert game.remaining_attempts == 2


def test_hide_unmatched(game):
    game.board[0] = ("mario", False, False)
    game.board[1] = ("luigi", False, False)
    game.flip_card(0)
    game.flip_card(1)
    game.check_match()
    game.hide_unmatched()
    assert game.board[0][1] is False
    assert game.board[1][1] is False


def test_award_star_and_next_level(game):
    game.remaining_attempts = 1
    game.award_star()
    assert game.stars == 1
    assert game.remaining_attempts == game.base_attempts * 2
    previous_size = len(game.board)
    game.next_level()
    assert game.stars == 2
    assert len(game.board) >= previous_size
    assert game.revealed == []


def test_is_game_over(game):
    game.remaining_attempts = 0
    assert game.is_game_over() is True
    game.remaining_attempts = 1
    game.board = [("mario", False, True)] * len(game.board)
    assert game.is_game_over() is True
