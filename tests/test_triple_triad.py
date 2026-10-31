from copy import deepcopy
import json
import pytest
from casinogames.triple_triad import TripleTriad, CARDS


def match():
    game = TripleTriad((11, 22), seed=1)
    game.turn = 11
    return game


def card(n=1):
    return {'id': 'fixture', 'name': 'Fixture', 'north': n, 'east': n, 'south': n, 'west': n}


def test_equal_open_hands_and_random_starter_are_reproducible():
    game = TripleTriad((11, 22), seed=7)
    assert game.to_dict() == TripleTriad((11, 22), seed=7).to_dict()
    assert game.hands['11'] == game.hands['22'] == list(CARDS)
    assert game.turn in game.players
    assert game.view()['hands'] == game.hands
    assert len(game.legal_actions(game.turn)) == 46


@pytest.mark.parametrize('players', [(1,), (1,1), (1,2,3), (-1,0), (True,0)])
def test_invalid_players_rejected(players):
    with pytest.raises(ValueError): TripleTriad(players)


def test_only_strict_opposing_touching_edge_captures():
    game = match()
    game.hands['11'][0].update(east=5)
    game.table[5] = {'card': card(5), 'owner': 22}
    game.act(11, 'place:cloud:4')
    assert game.table[5]['owner'] == 22
    assert game.captures == []
    game = match()
    game.hands['11'][0].update(east=6)
    game.table[5] = {'card': card(5), 'owner': 22}
    game.act(11, 'place:cloud:4')
    assert game.table[5]['owner'] == 11
    assert game.captures == [{'slot':5,'edge':'east','attack':6,'defend':5}]


def test_capture_does_not_wrap_right_edge_into_next_row():
    game = match()
    game.hands['11'][0].update(east=9)
    game.table[3] = {'card':card(1), 'owner':22}
    game.act(11, 'place:cloud:2')
    assert game.table[3]['owner'] == 22


def test_multiple_captures_but_no_recursive_chain():
    game = match()
    game.hands['11'][0].update(north=9,east=9,south=9,west=9)
    for position in (1,3,5,7): game.table[position]={'card':card(1),'owner':22}
    game.table[2] = {'card':card(1),'owner':22}
    game.table[5]['card']['north'] = 8
    game.act(11, 'place:cloud:4')
    assert [c['slot'] for c in game.captures] == [1,5,7,3]
    assert game.table[2]['owner'] == 22


def test_previously_captured_card_can_be_recaptured():
    game = match()
    game.hands['11'][0].update(east=6)
    game.table[5] = {'card':card(1),'owner':22}
    game.act(11, 'place:cloud:4')
    assert game.table[5]['owner'] == 11
    game.hands['22'][0].update(south=9)
    game.act(22, 'place:cloud:2')
    assert game.table[5]['owner'] == 22


def test_ninth_placement_counts_unused_tenth_card_for_draw():
    game = match()
    for hand in game.hands.values():
        for c in hand: c.update(north=1,east=1,south=1,west=1)
    for position in range(9):
        actor = game.turn
        chosen = game.hands[str(actor)][0]['id']
        game.act(actor, f'place:{chosen}:{position}')
    assert game.finished and game.turn is None
    assert game.result == {'winner':None,'reason':'draw','scores':{'11':5,'22':5}}
    assert sum(len(hand) for hand in game.hands.values()) == 1
    assert game.legal_actions(11) == []


def test_invalid_and_repeated_turns_leave_state_unchanged():
    game = match(); before = game.to_dict()
    for actor,action in [(22,'place:cloud:4'),(99,'concede'),(11,'place:cloud:9'),(11,'place:invalid:1')]:
        with pytest.raises(ValueError): game.act(actor,action)
        assert game.to_dict() == before
    game.act(11,'place:cloud:4'); before=game.to_dict()
    with pytest.raises(ValueError): game.act(11,'place:flower:1')
    assert game.to_dict() == before


def test_seeded_rounds_restore_every_move_and_conserve_ten_cards():
    for seed in range(30):
        game=TripleTriad((1,0),seed)
        while not game.finished:
            restored=TripleTriad.from_dict(json.loads(json.dumps(game.to_dict())))
            action=game.bot_action()
            assert restored.bot_action()==action
            actor=game.turn
            game.act(actor,action);restored.act(actor,action)
            assert game.to_dict()==restored.to_dict()
            assert sum(game.scores().values())==10
        assert sum(slot is not None for slot in game.table)==9


def test_snapshot_copy_and_concession_out_of_turn():
    game=match(); snapshot=game.view();snapshot['hands']['11'].clear()
    assert len(game.hands['11'])==5
    game.concede(22)
    assert game.result['winner']==11
    before=game.to_dict()
    with pytest.raises(ValueError):game.concede(22)
    assert game.to_dict()==before
    before['version']='unknown'
    with pytest.raises(ValueError):TripleTriad.from_dict(before)
