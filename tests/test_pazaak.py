import json
import pytest
from casinogames.pazaak import Pazaak, DEFAULT_SIDE


def playing(draws=None):
    game=Pazaak(seed=1,draws=draws)
    game.act(1,'ready');game.act(0,'ready')
    return game


def test_configurable_deck_cap_and_private_configuration():
    g=Pazaak(seed=1)
    assert g.phase=='side_deck' and len(g.side_decks['1'])==10
    g.act(1,'replace:0:±6')
    assert g.side_decks['1'][0]=='±6'
    assert g.view(0)['hands']['1']==[None]*10
    g.act(1,'replace:1:±6')
    assert not any(a['id']=='replace:2:±6' for a in g.legal_actions(1))
    before=g.to_dict()
    with pytest.raises(ValueError):g.act(1,'replace:2:±6')
    assert g.to_dict()==before
    g.act(1,'ready');g.act(0,'ready')
    assert all(len(h)==4 for h in g.hands.values())
    assert all(g.view()['hands'][str(p)]==[None]*4 for p in g.players)


def test_negative_modifier_can_rescue_bust_once_before_end():
    g=playing([10,10,10,10,10])
    actor=g.turn;key=str(actor)
    g.boards[key]=[10,10,3];g.hands[key]=['-4','+1','±2',None]
    g.act(actor,'side:0:-')
    assert g.total(actor)==19 and not g.finished
    assert g.hands[key][0] is None
    assert not any(a['id'].startswith('side:') for a in g.legal_actions(actor))
    g.act(actor,'stand')
    assert g.standing[key] and g.turn!=actor


def test_tied_set_awards_nothing_and_side_cards_persist():
    g=playing([1,1,1])
    actor=g.turn;other=g.other(actor)
    g.boards[str(actor)]=[10,8];g.boards[str(other)]=[10,8]
    g.standing[str(other)]=True
    g.hands[str(actor)][0]=None
    before=json.loads(json.dumps(g.hands))
    g.act(actor,'stand')
    assert g.phase=='set_end' and g.last_set['winner'] is None and list(g.scores.values())==[0,0]
    g.act(1,'next')
    assert g.hands==before and g.set_number==2
    assert g.turn==g.players[(g.opener+1)%2]


def test_bust_on_end_and_first_three_sets():
    g=playing([1]*10)
    for _ in range(3):
        actor=g.turn;other=g.other(actor)
        # Force the same player to win by standing both totals in a tiny fixture.
        g.boards['1']=[10,9];g.boards['0']=[10,8]
        g.standing[str(other)]=True
        g.act(actor,'stand')
        if not g.finished:g.act(1,'next')
    assert g.finished and g.result['winner']==1 and g.result['scores']['1']==3
    before=g.to_dict()
    with pytest.raises(ValueError):g.act(1,'next')
    assert g.to_dict()==before
    g=playing([1])
    g.boards[str(g.turn)]=[10,10,1]
    loser=g.turn;g.act(loser,'end')
    assert g.last_set['winner']==g.other(loser)


def test_nine_card_safe_win_and_no_tenth_card():
    g=playing([1])
    p=g.turn;g.boards[str(p)]=[1]*8;g.hands[str(p)]=['+1',None,None,None]
    g.act(p,'side:0:+')
    assert g.phase=='set_end' and g.last_set['winner']==p
    assert g.last_set['reason']=='nine-card safe win'
    assert len(g.boards[str(p)])==9


def test_invalid_actions_and_failed_draw_restore_rng_and_deck():
    g=playing([1])
    before=g.to_dict()
    with pytest.raises(ValueError):g.act(g.other(g.turn),'end')
    assert g.to_dict()==before
    with pytest.raises(ValueError,match='exhausted'):g.act(g.turn,'end')
    assert g.to_dict()==before


def test_json_resume_reproduces_full_match_and_bot_ignores_opponent_hand():
    g=playing()
    for _ in range(300):
        if g.finished:break
        restored=Pazaak.from_dict(json.loads(json.dumps(g.to_dict())))
        action=g.bot_action()
        g.act(g.turn,action);restored.act(restored.turn,action)
        assert g.to_dict()==restored.to_dict()
    assert g.finished
    g=playing();g.boards[str(g.turn)]=[7,6]
    action=g.bot_action();g.hands[str(g.other(g.turn))]=['±6']*4
    assert g.bot_action()==action


def test_sidecard_signs_and_private_deck_never_in_public():
    g=playing();p=g.turn;g.hands[str(p)]=['±6',None,None,None]
    ids={a['id'] for a in g.legal_actions(p)}
    assert {'side:0:+','side:0:-'}<=ids
    assert g.view()['side_decks']=={}
    assert 'rng_state' not in g.view() and 'draws' not in g.view()
    private=g.view(p);private['hands'][str(p)][0]='bad'
    assert g.hands[str(p)][0]=='±6'
