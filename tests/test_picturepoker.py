import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

import pytest # type: ignore
from casinogames.picturepoker.PicturePoker import PicturePoker

#basic fixture to start a fresh game
@pytest.fixture
def game():
    return PicturePoker(starting_stars=0)

def test_start_round_deals_cards(game):
    game.start_round()
    assert len(game.player_hand) == 5
    assert len(game.luigi_hand) == 5
    assert game.bet >= 1

@pytest.mark.parametrize("replacements", [["cloud", "luigi"], ["star", "flower"]])
def test_player_discard_consumes_selected_replacements(game, replacements):
    # Drawing the same symbols is legal; verify draws and held cards, not luck.
    game.player_hand = ["cloud", "luigi", "mario", "mushroom", "star"]
    game.deck = replacements + ["flower", "cloud"]
    before = list(game.player_hand)
    game.player_discard([0, 1])
    assert game.player_hand == replacements + before[2:]
    assert game.deck == ["flower", "cloud"]

def test_hand_evaluation_pair(game):
    hand = ["mario", "mario", "cloud", "luigi", "star"]
    val, rank = game.evaluate_hand(hand)
    assert rank == "one_pair"

def test_hand_evaluation_full_house(game):
    hand = ["mario", "mario", "mario", "luigi", "luigi"]
    val, rank = game.evaluate_hand(hand)
    assert rank == "full_house"

def test_resolve_round_player_wins(game):
    #force known hands
    game.player_hand = ["cloud"] * 5
    game.luigi_hand = ["luigi"] * 5
    game.bet = 2
    result = game.resolve_round()
    assert result["outcome"] == "win"
    assert result["coins"] == 32  # 2 * 16 multiplier
    assert result["stars"] == 1

def test_resolve_round_luigi_wins(game):
    game.player_hand = ["mario"] * 2 + ["luigi"] * 3
    game.luigi_hand = ["star"] * 4 + ["cloud"]
    game.bet = 2
    result = game.resolve_round()
    assert result["outcome"] == "lose"
    assert result["coins"] == 2

# tie breaking tests

def test_symbol_priority_player_wins_with_cloud_pair(game):
    game.player_hand = ["cloud", "cloud", "mario", "flower", "star"]
    game.luigi_hand = ["star", "star", "mario", "flower", "luigi"]
    game.bet = 1
    result = game.resolve_round()
    assert result["outcome"] == "win"

def test_symbol_priority_luigi_wins_with_better_pair(game):
    game.player_hand = ["mushroom", "mushroom", "cloud", "flower", "star"]
    game.luigi_hand = ["cloud", "cloud", "luigi", "mario", "star"]
    game.bet = 1
    result = game.resolve_round()
    assert result["outcome"] == "lose"

def test_symbol_priority_tie_requires_identical_cards(game):
    junk_hand = ["cloud", "mushroom", "flower", "luigi", "mario"]
    game.player_hand = list(junk_hand)
    game.luigi_hand = list(junk_hand)
    game.bet = 3
    result = game.resolve_round()
    assert result["outcome"] == "tie"
