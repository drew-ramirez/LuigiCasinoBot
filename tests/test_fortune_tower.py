"""Tower decisions use saved cards and exact practice-point arithmetic."""
from collections import Counter
import json
import random

import pytest

from casinogames.fortune_tower import FortuneTower


def scripted(*cards):
    # Full natural Diamond deck, with the supplied draw-order prefix.
    rest = FortuneTower.make_deck()
    for card in cards:
        rest.remove(card)
    return FortuneTower(deck=list(cards) + rest)


def test_diamond_composition_and_seeded_reproducibility():
    assert Counter(FortuneTower.make_deck()) == {**{n: 8 for n in range(1, 8)}, 0: 4}
    assert FortuneTower(rng=random.Random(6)).to_dict() == FortuneTower(rng=random.Random(6)).to_dict()


@pytest.mark.parametrize("stake", [0, -15, 1, 29, 30.0, True])
def test_rejects_non_integral_or_fractional_point_stakes(stake):
    with pytest.raises(ValueError):
        FortuneTower(stake=stake)


def test_opening_does_not_compare_hidden_gate_and_bank_is_idempotent():
    game = scripted(3, 3, 4)
    assert game.offer == 14
    assert not game.gate_used
    before = game.to_dict()
    result = game.bank()
    assert result == {"outcome": "banked", "gross": 14, "net": -16,
                      "score": 14, "row": 2, "multiplier": 1, "practice_only": True}
    assert game.bank() == result
    assert game.deck == before["deck"]
    with pytest.raises(ValueError):
        game.deal_next()


def test_hero_protection_preserves_gate_and_later_offer_can_fall():
    game = scripted(5, 3, 4, 3, 0, 2)
    event = game.deal_next()
    assert event["hazards"] == [0]
    assert event["protected"]
    assert event["replacement"] is None
    assert not game.gate_used
    assert game.offer == 10 < event["previous_offer"]
    assert game.net == -20


def test_gate_replaces_first_danger_then_second_danger_busts():
    game = scripted(5, 3, 4, 3, 4, 2)
    event = game.deal_next()
    assert event["replacement"] == {"index": 0, "discarded": 3, "card": 5}
    assert event["remaining_hazards"] == [1]
    assert game.rows[-1] == [5, 4, 2]
    assert game.result["outcome"] == "bust"
    assert game.result["gross"] == 0
    assert game.net == -30


def test_failed_gate_replacement_busts_even_on_single_hazard():
    game = scripted(3, 3, 4, 3, 6, 2)
    game.deal_next()
    assert game.gate_used
    assert game.result["outcome"] == "bust"


def test_used_gate_cannot_rescue_another_row():
    game = scripted(5, 3, 4, 3, 6, 2, 5, 1, 4, 7)
    game.deal_next()
    assert game.offer == 26
    game.deal_next()
    assert game.result["outcome"] == "bust"


def test_hero_gate_house_convention_protects_entire_row():
    game = scripted(0, 3, 4, 3, 4, 2)
    event = game.deal_next()
    assert game.gate_used and event["protected"]
    assert not game.finished
    assert game.offer == 12
    assert game.rows[-1] == [0, 4, 2]


def test_outside_parent_geometry_does_not_wrap_rows():
    game = scripted(5, 3, 4, 4, 7, 3)
    event = game.deal_next()
    assert event["hazards"] == []
    assert not game.gate_used
    assert game.offer == 28


def test_sets_keep_highest_multiplier_across_safe_rows():
    game = scripted(7, 3, 3, 4, 4, 4, 5, 6, 5, 6)
    assert game.multiplier == 2 and game.offer == 24
    game.deal_next()
    assert game.multiplier == 3 and game.offer == 72
    game.deal_next()
    assert game.multiplier == 3 and game.offer == 132


def test_full_tower_jackpot_includes_unused_gate_under_house_rules():
    # This test deck intentionally repeats ranks beyond the natural deck count
    # to isolate maximum-row settlement without a shuffled stochastic fixture.
    rows = [[(width % 2) + 1] * width for width in range(2, 9)]
    game = FortuneTower(deck=[7] + [c for row in rows for c in row])
    for _ in range(6):
        game.deal_next()
    total = 7 + sum(map(sum, rows))
    assert game.finished
    assert game.result["outcome"] == "jackpot"
    assert game.offer == 2 * total * 8
    assert game.bank() == game.result


def test_eighth_row_with_used_gate_banks_only_current_row():
    rows = [[2, 3], [2, 4, 4]] + [[(width % 2) + 5] * width for width in range(4, 9)]
    game = FortuneTower(deck=[7] + [c for row in rows for c in row])
    for _ in range(6):
        game.deal_next()
    assert game.gate_used and game.finished
    assert game.result["outcome"] == "complete"
    assert game.offer == 2 * sum(rows[-1]) * 8


def test_json_roundtrip_preserves_future_cards_and_offer():
    game = scripted(5, 3, 4, 3, 0, 2, 6, 7, 4, 6)
    game.deal_next()
    restored = FortuneTower.from_dict(json.loads(json.dumps(game.to_dict())))
    assert restored.to_dict() == game.to_dict()
    assert restored.deal_next() == game.deal_next()
    assert restored.to_dict() == game.to_dict()
    assert restored.bank() == game.bank()


def test_public_payload_never_exposes_unused_gate_or_deck():
    game = scripted(7, 3, 4)
    state = game.public_state()
    assert state["gate"] is None
    assert "deck" not in state
    assert 7 not in state["rows"][0]
    state["rows"][0][0] = 0
    assert game.rows == [[3, 4]]
    private = game.to_dict()
    private["deck"][0] = 0
    assert private["deck"] != game.deck


def test_timeout_accepts_existing_offer_exactly_once():
    game = scripted(5, 3, 4)
    before = game.to_dict()
    assert game.expire()["gross"] == 14
    assert game.expire()["gross"] == 14
    assert game.deck == before["deck"]


def test_failed_deal_does_not_consume_part_of_row():
    game = scripted(5, 3, 4)
    game.deck = [1]
    before = game.to_dict()
    with pytest.raises(ValueError):
        game.deal_next()
    assert game.to_dict() == before


def test_restore_rejects_other_rules_or_malformed_cards():
    state = scripted(5, 3, 4).to_dict()
    state["rules_version"] = "future"
    with pytest.raises(ValueError):
        FortuneTower.from_dict(state)
    state["rules_version"] = FortuneTower.RULES_VERSION
    state["rows"][0][0] = 9
    with pytest.raises(ValueError):
        FortuneTower.from_dict(state)
