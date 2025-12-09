import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from casinogames.poker.Poker import Poker, RANK_ORDER
from casinogames.cards.standard_deck import Card


def make_hand(cards):
    return [Card(rank, suit) for rank, suit in cards]


def test_straight_flush_beats_four_kind():
    game = Poker(10)
    game.player_hand = make_hand([("9", "hearts"), ("10", "hearts"), ("J", "hearts"), ("Q", "hearts"), ("K", "hearts")])
    game.dealer_hand = make_hand([("A", "clubs"), ("A", "diamonds"), ("A", "spades"), ("A", "hearts"), ("5", "clubs")])
    game.deck = []
    result = game.resolve_round()
    assert result["outcome"] == "win"
    assert result["payout"] == 20
    assert result["net"] == 10


def test_full_house_beats_flush():
    game = Poker(5)
    game.player_hand = make_hand([("K", "spades"), ("K", "hearts"), ("K", "diamonds"), ("2", "clubs"), ("2", "hearts")])
    game.dealer_hand = make_hand([("A", "clubs"), ("J", "clubs"), ("8", "clubs"), ("5", "clubs"), ("3", "clubs")])
    game.deck = []
    result = game.resolve_round()
    assert result["outcome"] == "win"


def test_pair_loses_to_two_pair():
    game = Poker(5)
    game.player_hand = make_hand([("A", "hearts"), ("A", "clubs"), ("9", "diamonds"), ("6", "spades"), ("2", "hearts")])
    game.dealer_hand = make_hand([("K", "hearts"), ("K", "clubs"), ("3", "spades"), ("3", "diamonds"), ("7", "clubs")])
    game.deck = []
    result = game.resolve_round()
    assert result["outcome"] == "lose"
    assert result["payout"] == 0
    assert result["net"] == -5


def test_push_on_identical_high_cards():
    game = Poker(3)
    junk_hand = make_hand([("A", "hearts"), ("10", "clubs"), ("7", "spades"), ("4", "diamonds"), ("2", "clubs")])
    game.player_hand = list(junk_hand)
    game.dealer_hand = list(junk_hand)
    game.deck = []
    result = game.resolve_round()
    assert result["outcome"] == "push"
    assert result["payout"] == 3
    assert result["net"] == 0


def test_wheel_straight_low_ace():
    game = Poker(4)
    game.player_hand = make_hand([("A", "hearts"), ("2", "clubs"), ("3", "spades"), ("4", "diamonds"), ("5", "clubs")])
    game.dealer_hand = make_hand([("9", "hearts"), ("9", "clubs"), ("8", "spades"), ("7", "diamonds"), ("6", "clubs")])
    game.deck = []
    result = game.resolve_round()
    assert result["outcome"] == "win"


def test_dealer_discards_keeps_pair():
    game = Poker(5)
    game.dealer_hand = make_hand([("K", "spades"), ("K", "hearts"), ("4", "clubs"), ("8", "diamonds"), ("2", "clubs")])
    keep_mask = game._dealer_keep_mask(game.dealer_hand)
    assert keep_mask.count(True) >= 2  # keeps the pair


def test_tie_breaker_higher_pair_wins():
    game = Poker(2)
    game.player_hand = make_hand([("Q", "hearts"), ("Q", "clubs"), ("9", "diamonds"), ("6", "spades"), ("2", "hearts")])
    game.dealer_hand = make_hand([("J", "hearts"), ("J", "clubs"), ("A", "diamonds"), ("K", "spades"), ("4", "hearts")])
    game.deck = []
    result = game.resolve_round()
    assert result["outcome"] == "win"
