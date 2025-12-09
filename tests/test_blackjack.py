import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from casinogames.blackjack.Blackjack import Blackjack
from casinogames.cards.standard_deck import Card, best_blackjack_total


def test_best_blackjack_total_prefers_soft_when_under_21():
    hand = [Card("A", "spades"), Card("9", "hearts")]
    total, is_soft = best_blackjack_total(hand)
    assert total == 20
    assert is_soft is True


def test_player_blackjack_beats_dealer_21_non_blackjack():
    game = Blackjack(10)
    game.player_hand = [Card("A", "spades"), Card("K", "hearts")]
    game.dealer_hand = [Card("10", "clubs"), Card("7", "diamonds"), Card("4", "hearts")]
    game.deck = []
    result = game.stand()
    assert result["outcome"] == "blackjack"
    assert result["payout"] == 25  # 3:2 on base bet 10
    assert result["net"] == 15


def test_hit_and_bust():
    game = Blackjack(10)
    game.player_hand = [Card("10", "hearts"), Card("9", "clubs")]
    game.dealer_hand = [Card("2", "spades"), Card("2", "hearts")]
    game.deck = [Card("5", "diamonds")]
    result = game.hit()
    assert result["outcome"] == "bust"
    assert result["payout"] == 0
    assert result["net"] == -10


def test_dealer_stands_on_soft_17_when_flag_false():
    game = Blackjack(10, dealer_hits_soft_17=False)
    game.player_hand = [Card("10", "hearts"), Card("8", "clubs")]
    game.dealer_hand = [Card("A", "spades"), Card("6", "hearts")]
    game.deck = [Card("9", "diamonds")]  # would bust dealer if drawn
    result = game.stand()
    assert result["outcome"] == "win"
    assert result["payout"] == 20


def test_dealer_hits_soft_17_when_flag_true():
    game = Blackjack(10, dealer_hits_soft_17=True)
    game.player_hand = [Card("10", "hearts"), Card("8", "clubs")]
    game.dealer_hand = [Card("A", "spades"), Card("6", "hearts")]
    game.deck = [Card("10", "diamonds")]
    result = game.stand()
    assert result["outcome"] == "win"
    assert len(result["dealer_hand"]) == 3  # dealer drew on soft 17
    assert result["dealer_total"] < result["player_total"]


def test_push_on_equal_totals_without_blackjack():
    game = Blackjack(10)
    game.player_hand = [Card("10", "hearts"), Card("K", "clubs")]
    game.dealer_hand = [Card("Q", "spades"), Card("J", "diamonds")]
    game.deck = []
    result = game.stand()
    assert result["outcome"] == "push"
    assert result["payout"] == 10
    assert result["net"] == 0


def test_double_down_doubles_stake_and_payout():
    game = Blackjack(10)
    game.player_hand = [Card("5", "hearts"), Card("4", "clubs")]
    game.dealer_hand = [Card("6", "spades"), Card("9", "diamonds")]
    game.deck = [Card("8", "hearts"), Card("9", "clubs")]  # first to player, second to dealer if needed
    result = game.double_down()
    assert result["outcome"] == "win"
    assert result["stake"] == 20
    assert result["payout"] == 40
    assert result["net"] == 20
