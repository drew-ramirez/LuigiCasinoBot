import json
import random
import pytest

from casinogames.thrilling_cards import ThrillingCards, ThrillingMatch, card_strength


def test_research_settlement_example_conserves_practice_chips():
    game = ThrillingCards([1, 2, 3], unit=10, cards=['KH', 'KD', '2C'])
    game.act(1, 'open', 3)
    game.act(2, 'raise', 2)
    game.act(3, 'fold')
    game.act(1, 'call')
    assert game.result['winner'] == 1
    assert game.result['pot'] == 110
    assert game.result['net'] == {1: 60, 2: -50, 3: -10}
    assert sum(game.result['net'].values()) == 0
    assert game.result['revealed'] == {1: 'KH', 2: 'KD'}


@pytest.mark.parametrize('count', [2, 3, 4])
def test_every_player_must_respond_even_when_opening_matches_ante(count):
    players = list(range(1, count + 1))
    game = ThrillingCards(players, cards=['2C', '3D', '4H', '5S'][:count])
    game.act(1, 'open', 1)
    for p in players[1:]:
        assert game.turn == p
        assert game.result is None
        game.act(p, 'call')
    assert game.result['winner'] == count
    assert game.pot == count


def test_two_raise_cap_reopens_action_and_limits_commitment():
    game = ThrillingCards([1, 2, 3, 4], cards=['AS', 'AH', 'AD', 'AC'])
    game.act(1, 'open', 5)
    game.act(2, 'raise', 5)
    game.act(3, 'raise', 5)
    assert game.target == 15
    before = game.to_dict()
    with pytest.raises(ValueError):
        game.act(4, 'raise', 1)
    assert game.to_dict() == before
    for p in (4, 1, 2):
        game.act(p, 'call')
    assert game.result['winner'] == 1
    assert game.result['pot'] == 60
    assert max(game.commitments.values()) == 15


def test_live_private_projection_hides_own_card_and_public_hides_everything():
    game = ThrillingCards([1, 2, 3], cards=['AS', 'KH', '2C'])
    for viewer in (None, 999):
        state = game.view(viewer)
        assert all(seat['card'] is None for seat in state['seats'])
        assert all(code not in json.dumps(state) for code in game.cards.values())
        assert state['actions'] == ()
    for viewer in game.players:
        state = game.view(viewer)
        seats = {seat['player_id']: seat for seat in state['seats']}
        assert seats[viewer]['card'] is None
        assert game.cards[viewer] not in json.dumps(state)
        for other in set(game.players) - {viewer}:
            assert seats[other]['card'] == game.cards[other]


def test_fold_win_does_not_publicly_reveal_any_card():
    game = ThrillingCards([1, 2, 3], cards=['AS', 'KH', '2C'])
    game.act(1, 'open', 2)
    game.fold(3)
    assert game.turn == 2
    game.act(2, 'fold')
    assert game.result['winner'] == 1
    assert game.result['reason'] == 'fold'
    assert game.result['revealed'] == {}
    assert all(seat['card'] is None for seat in game.view()['seats'])
    assert sum(game.result['net'].values()) == 0


def test_departure_before_open_passes_opening_choice_and_timeout_preserves_ante():
    game = ThrillingCards([1, 2, 3], cards=['AS', 'KH', '2C'])
    game.fold(1)
    assert game.turn == 2
    assert game.legal_actions(2) == ('open', 'fold')
    game.act(2, 'open', 1)
    game.fold(3)
    assert game.result['net'] == {1: -1, 2: 2, 3: -1}


def test_out_of_turn_departure_can_trigger_showdown_after_last_raise():
    game = ThrillingCards([1, 2, 3], cards=['AS', 'KH', '2C'])
    game.act(1, 'open', 1)
    game.act(2, 'call')
    game.fold(3)
    assert game.result['reason'] == 'showdown'
    assert game.result['revealed'] == {1: 'AS', 2: 'KH'}


def test_rejected_stale_duplicate_and_illegal_actions_never_mutate():
    game = ThrillingCards([1, 2], cards=['AS', 'KH'])
    before = game.to_dict()
    for args in ((2, 'open', 2), (999, 'fold'), (1, 'open', 0),
                 (1, 'open', True), (1, 'open', 6), (1, 'call')):
        with pytest.raises(ValueError):
            game.act(*args)
        assert game.to_dict() == before
    game.act(1, 'open', 2, expected_revision=0)
    with pytest.raises(ValueError):
        game.act(2, 'call', expected_revision=0)
    assert game.revision == 1
    game.act(2, 'call', expected_revision=1)
    finished = game.to_dict()
    for p in game.players:
        with pytest.raises(ValueError):
            game.fold(p)
    assert game.to_dict() == finished


@pytest.mark.parametrize('cards', [['AS', 'AS'], ['1S', 'KH'], ['AS'], ['AS', 'KH', '2C']])
def test_rejects_invalid_or_duplicate_deals(cards):
    with pytest.raises(ValueError):
        ThrillingCards([1, 2], cards=cards)


def test_rank_precedes_suit_and_suits_order_ascending():
    assert card_strength('2S') < card_strength('3C')
    assert card_strength('AC') < card_strength('AD') < card_strength('AH') < card_strength('AS')


def test_json_roundtrip_preserves_all_views_and_resumes_same_outcome():
    game = ThrillingCards([1, 2, 3], unit=10, cards=['KH', 'KD', '2C'])
    game.act(1, 'open', 3)
    game.act(2, 'raise', 2)
    restored = ThrillingCards.from_dict(json.loads(json.dumps(game.to_dict())))
    for p in (None, 1, 2, 3, 999):
        assert restored.view(p) == game.view(p)
    for item in (game, restored):
        item.act(3, 'fold')
        item.act(1, 'call')
    assert restored.result == game.result
    saved = restored.to_dict()
    saved['events'].clear()
    assert restored.revision == 4
    assert ThrillingCards.from_dict(game.to_dict()).result == game.result


def test_randomized_tables_always_finish_conserve_chips_and_obey_cap():
    rng = random.Random(81)
    for _ in range(100):
        game = ThrillingCards(list(range(1, rng.randint(2, 4) + 1)), unit=10, rng=rng)
        for _ in range(20):
            if game.result is not None:
                break
            action = rng.choice(game.legal_actions(game.turn))
            game.act(game.turn, action, rng.randint(1, 5) if action in ('open', 'raise') else None)
        assert game.result is not None
        assert sum(game.result['net'].values()) == 0
        assert max(game.commitments.values()) <= 150
        assert ThrillingCards.from_dict(game.to_dict()).result == game.result


def test_five_hand_match_rotates_opener_and_settles_only_once():
    match = ThrillingMatch([1, 2, 3])
    for n in range(5):
        hand = match.next_hand(cards=['AS', 'KH', '2C'])
        assert hand.turn == (n % 3) + 1
        hand.act(hand.turn, 'open', 1)
        while hand.result is None:
            hand.act(hand.turn, 'call')
        match.settle_hand()
        chips = dict(match.chips)
        match.settle_hand()
        assert match.chips == chips
        assert sum(match.chips.values()) == 225
    assert match.finished
    assert match.standings()[0]['net'] == 10
    with pytest.raises(ValueError):
        match.next_hand()


def test_departure_ends_match_early_and_standings_allow_ties():
    match = ThrillingMatch([1, 2, 3])
    assert [seat['place'] for seat in match.standings()] == [1, 1, 1]
    match.leave(2)
    match.leave(3)
    assert match.finished
    with pytest.raises(ValueError):
        match.next_hand()


def test_starting_next_hand_cannot_drop_previous_settlement():
    match = ThrillingMatch([1, 2])
    first = match.next_hand(cards=['AS', 'KH'])
    first.act(1, 'open', 5)
    first.act(2, 'call')
    match.next_hand(cards=['2C', '3D'])
    assert match.chips == {1: 80, 2: 70}
    assert len(match.hands) == 1
    assert match.hand.turn == 2


def test_match_roundtrip_keeps_chips_departures_and_current_private_views():
    match = ThrillingMatch([1, 2, 3])
    hand = match.next_hand(cards=['AS', 'KH', '2C'])
    hand.act(1, 'open', 5)
    hand.act(2, 'call')
    hand.act(3, 'call')
    match.settle_hand()
    hand = match.next_hand(cards=['KS', 'QH', '3C'])
    hand.act(2, 'open', 3)
    match.leave(3)
    restored = ThrillingMatch.from_dict(json.loads(json.dumps(match.to_dict())))
    assert restored.chips == match.chips
    assert restored.departed == {3}
    assert restored.standings() == match.standings()
    for viewer in (None, 1, 2, 3):
        assert restored.hand.view(viewer) == hand.view(viewer)
    for game in (match, restored):
        game.hand.act(1, 'call')
        game.settle_hand()
    assert restored.to_dict() == match.to_dict()
    assert restored.chips == match.chips
    again = ThrillingMatch.from_dict(restored.to_dict())
    again.settle_hand()
    assert again.chips == restored.chips
