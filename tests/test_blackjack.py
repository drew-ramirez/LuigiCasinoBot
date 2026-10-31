"""Behavioral examples for the published House Blackjack v1 rules."""
import json
import random

import pytest

from casinogames.blackjack import Blackjack, hand_total


def deal(*cards, bet=100):
    return Blackjack(bet, shoe=cards)


@pytest.mark.parametrize("cards,total,soft", [
    (["AS", "6H"], 17, True), (["AS", "AH", "9D"], 21, True),
    (["AS", "6H", "10D"], 17, False), (["AS", "AH", "9D", "KC"], 21, False),
])
def test_soft_totals(cards, total, soft):
    assert hand_total(cards) == (total, soft)


@pytest.mark.parametrize("bet", [0, -2, 1, 99, 1.5, True])
def test_wager_requires_exact_even_chips(bet):
    with pytest.raises(ValueError):
        Blackjack(bet)


@pytest.mark.parametrize("cards,outcome,payout", [
    (("AS", "9H", "KD", "8C"), "blackjack", 250),
    (("AS", "AH", "KD", "QC"), "push", 100),
    (("10S", "AH", "9D", "QC"), "loss", 0),
])
def test_initial_naturals_resolve_before_extra_bets(cards, outcome, payout):
    game = deal(*cards)
    assert game.result["payout"] == payout
    assert game.result["hands"][0]["outcome"] == outcome
    assert not game.allowed_actions()
    before = game.to_dict()
    with pytest.raises(ValueError):
        game.act("double")
    assert game.to_dict() == before


def test_dealer_stands_on_soft_17():
    game = deal("10S", "AH", "8D", "6C", "KS")
    game.act("stand")
    assert game.result["payout"] == 200
    assert game.dealer == ["AH", "6C"]
    assert game.shoe == ["KS"]


def test_double_draws_once_and_returns_gross_stake():
    game = deal("8S", "6H", "3D", "10C", "9S", "8H")
    assert game.extra_stake("double") == 100
    game.act("double")
    assert game.result["committed"] == 200
    assert game.result["payout"] == 400
    assert game.result["profit"] == 200
    assert len(game.hands[0]["cards"]) == 3


def test_hit_removes_double_and_bust_does_not_draw_dealer():
    game = deal("8S", "6H", "3D", "10C", "2S", "KH", "8D")
    game.act("hit")
    assert game.allowed_actions() == ("hit", "stand")
    game.act("hit")
    assert game.result["hands"][0]["outcome"] == "bust"
    assert game.dealer == ["6H", "10C"]
    assert game.shoe == ["8D"]


def test_split_uses_same_shoe_and_deals_second_hand_on_activation():
    game = deal("8S", "10H", "8D", "7C", "10S", "2H", "6D")
    game.act("split")
    assert game.hands[0]["cards"] == ["8S", "10S"]
    assert game.hands[1]["cards"] == ["8D"]
    assert "split" not in game.allowed_actions()
    game.act("stand")
    assert game.active_hand == 1
    assert game.hands[1]["cards"] == ["8D", "2H"]
    game.act("double")
    assert game.result["payout"] == 200
    assert game.result["committed"] == 300
    assert [h["outcome"] for h in game.result["hands"]] == ["win", "loss"]


def test_same_value_face_cards_are_not_same_rank():
    game = deal("JS", "10H", "QD", "7C")
    assert "split" not in game.allowed_actions()


def test_split_aces_receive_one_card_each_and_21_is_not_natural():
    game = deal("AS", "10H", "AD", "7C", "KS", "QH")
    game.act("split")
    assert game.result["payout"] == 400
    assert [h["outcome"] for h in game.result["hands"]] == ["win", "win"]
    assert all(len(hand["cards"]) == 2 for hand in game.hands)


def test_timeout_completes_unplayed_split_hand_and_is_idempotent():
    game = deal("8S", "10H", "8D", "7C", "10S", "9H")
    game.act("split")
    result = game.timeout()
    assert result["payout"] == 300
    assert game.hands[1]["cards"] == ["8D", "9H"]
    before = game.to_dict()
    assert game.timeout() == result
    assert game.to_dict() == before


def test_public_snapshot_cannot_reveal_hole_or_shoe_or_mutate_game():
    game = deal("8S", "10H", "8D", "7C", "10S", "9H")
    public = game.public_state()
    assert public["dealer"] == ["10H", None]
    assert public["dealer_total"] is None
    assert "7C" not in json.dumps(public)
    assert "shoe" not in public
    public["hands"][0]["cards"].append("AS")
    assert game.hands[0]["cards"] == ["8S", "8D"]
    game.timeout()
    assert game.public_state()["dealer"] == ["10H", "7C"]


def test_json_roundtrip_continues_exact_shoe_and_outcome():
    game = deal("8S", "10H", "8D", "7C", "10S", "9H")
    game.act("split")
    saved = json.loads(json.dumps(game.to_dict()))
    resumed = Blackjack.from_dict(saved)
    assert resumed.to_dict() == game.to_dict()
    assert resumed.timeout() == game.timeout()
    assert resumed.to_dict() == game.to_dict()
    saved["shoe"].clear()
    assert resumed.to_dict() != saved


def test_invalid_save_version_rejected():
    game = Blackjack(100, random.Random(3))
    saved = game.to_dict()
    saved["version"] = 77
    with pytest.raises(ValueError):
        Blackjack.from_dict(saved)


def test_short_injected_shoe_fails_atomically():
    game = deal("8S", "6H", "3D", "10C", "9S")
    before = game.to_dict()
    with pytest.raises(ValueError, match="exhausted"):
        game.act("double")
    assert game.to_dict() == before


def test_seeded_six_deck_rounds_are_reproducible():
    game = Blackjack(100, random.Random(109))
    same = Blackjack(100, random.Random(109))
    assert game.to_dict() == same.to_dict()
    assert len(game.shoe) == 308
    assert game.timeout() == same.timeout()
