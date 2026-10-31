import json
from collections import Counter
import pytest
from casinogames.scopa import Scopa, DECK


def test_initial_deal_and_hidden_hand():
    game=Scopa((1,0),seed=2)
    assert len(game.deck)==30 and len(game.table)==4
    assert [len(h) for h in game.hands.values()]==[3,3]
    assert game.turn==1 and sum(c.startswith('K') for c in game.table)<3
    assert game.view()['hands']=={'1':[None]*3,'0':[None]*3}
    assert game.view(1)['hands']['1']==game.hands['1']
    assert 'deck' not in game.view()


def test_equal_single_takes_precedence_over_summing_set():
    game=Scopa(seed=1)
    game.hands['1']=['5S']
    game.table=['AD','4C','5H','5D']
    actions=game.legal_actions(1)
    assert {a['id'] for a in actions}=={'play:5S:5H','play:5S:5D'}
    with pytest.raises(ValueError):game.act(1,'play:5S:AD,4C')
    game.act(1,'play:5S:5D')
    assert game.captured['1']==['5S','5D'] and game.table==['AD','4C','5H']


def test_all_summing_sets_and_mandatory_capture():
    game=Scopa(seed=1)
    game.hands['1']=['JS']
    game.table=['AD','3C','4H','5D','7S']
    assert {a['id'] for a in game.legal_actions(1)}=={
        'play:JS:AD,3C,4H','play:JS:AD,7S','play:JS:3C,5D'}
    before=game.to_dict()
    with pytest.raises(ValueError):game.act(1,'play:JS:')
    assert game.to_dict()==before


def test_sweep_except_final_play_and_last_capturer_leftovers():
    game=Scopa(seed=1)
    game.hands={'1':['2S'],'0':['KH']};game.deck=[];game.table=['2D']
    game.act(1,'play:2S:2D')
    assert game.sweeps['1']==1
    game.act(0,'play:KH:')
    assert game.finished and game.table==[] and 'KH' in game.captured['1']
    game=Scopa(seed=1)
    game.hands={'1':['2S'],'0':[]};game.deck=[];game.table=['2D']
    game.act(1,'play:2S:2D')
    assert game.finished and game.sweeps['1']==0


def test_tied_categories_and_primiera_needs_every_suit():
    game=Scopa(seed=1)
    game.table=[];game.captured={'1':['7D','7C','7H','6S'],'0':['6D','6C','6H','7S']}
    game._finish()
    detail=game.result['breakdown']
    assert detail['1']['primiera']==81 and detail['0']['primiera']==75
    assert game.result['scores']=={'1':2,'0':0}  # equal cards and coins award neither
    game=Scopa(seed=1)
    game.table=[];game.captured={'1':['7D','7C','7H'],'0':['AC','AD','AH','AS']}
    game._finish()
    assert game.result['breakdown']['1']['primiera']==0
    assert game.result['breakdown']['0']['primiera']==64


@pytest.mark.parametrize('seed',range(10))
def test_complete_deal_roundtrip_card_conservation_and_36_placements(seed):
    game=Scopa((1,0),seed=seed)
    moves=0
    while not game.finished:
        cards=game.deck+game.table+sum(game.hands.values(),[])+sum(game.captured.values(),[])
        assert Counter(cards)==Counter(DECK)
        restored=Scopa.from_dict(json.loads(json.dumps(game.to_dict())))
        action=game.bot_action()
        assert restored.bot_action()==action
        actor=game.turn
        game.act(actor,action);restored.act(actor,action)
        assert restored.to_dict()==game.to_dict()
        moves+=1
    assert moves==36 and sum(map(len,game.captured.values()))==40
    assert sum(game.result['scores'].values())>=1


def test_wrong_actor_and_unknown_actions_do_not_mutate():
    game=Scopa(seed=1);before=game.to_dict()
    with pytest.raises(ValueError):game.act(0,game.legal_actions(1)[0]['id'])
    with pytest.raises(ValueError):game.act(1,'play:bogus:')
    assert game.to_dict()==before
    game.concede(1)
    assert game.result['winner']==0 and not game.legal_actions(0)


def test_bot_decision_does_not_read_opposing_hand_or_future_deck():
    g=Scopa(seed=32)
    decision=g.bot_action()
    other=g.players[1]
    g.hands[str(other)].reverse()
    g.deck.reverse()
    g.hands[str(other)],g.deck[:3]=g.deck[:3],g.hands[str(other)]
    assert g.bot_action()==decision


def test_finished_view_is_detached_from_engine_result():
    g=Scopa(seed=1)
    while not g.finished:g.act(g.turn,g.bot_action())
    original=g.to_dict()
    projection=g.view(1)
    projection['scores']['1']=-100
    projection['result']['scores']['1']=-200
    assert g.to_dict()==original
