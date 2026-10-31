import json
import pytest
from casinogames.platoon import Platoon, compare_piles, valid_pile

LEFT=['X1','2S','KS','AC','QH','9H','8H','7H','4H','3H']
RIGHT=['QD','8D','10D','9D','AD','KD','3D','7D','6D','4D']


def battle_game():
    g=Platoon(hands={1:LEFT,0:RIGHT},deck=['AS','2C'])
    for player,assignment in [(1,[0,0,1,3,2,2,4,4,4,4]),(0,[0,0,1,1,2,3,3,4,4,4])]:
        for card,pile in enumerate(assignment):g.act(player,f'assign:{card}:{pile}')
        g.act(player,'lock')
    g.act(1,'predict:0:0');g.act(0,'predict:1:3')
    return g


@pytest.mark.parametrize('a,b,sign,exchange',[
    (['KS'],['QH','9H'],1,False),(['AS'],['KH'],1,False),
    (['2S'],['AH'] ,1,False),(['KS'],['KH','2H'],-1,False),
    (['AS','2S'],['AH','3H'],-1,False),(['2S'],['2H'],0,False),
    (['X1','2S'],['KH'],1,True),(['X1','AS'],['KH'],-1,True),
    (['X1','KS'],['AH'],1,True),(['X1','KS'],['X2','AH'],-1,False),
])
def test_special_comparisons_and_single_wizard_exchange(a,b,sign,exchange):
    actual,event=compare_piles(a,b)
    assert actual==sign and event['exchange']==exchange
    assert event['left']==(b if exchange else a)


@pytest.mark.parametrize('cards', [[],['X1'],['KS','AH'],['X1','X2','3C']])
def test_illegal_formations(cards):
    assert not valid_pile(cards)


def test_editor_requires_all_cards_and_five_legal_piles_and_allows_moves():
    g=Platoon(hands={1:LEFT,0:RIGHT},deck=['AS','2C'])
    before=g.to_dict()
    with pytest.raises(ValueError):g.act(1,'lock')
    assert g.to_dict()==before
    g.act(1,'assign:0:0');g.act(1,'assign:1:0')
    assert g.piles(1)[0]==['X1','2S']
    g.act(1,'assign:1:1');g.act(1,'undo:1')
    assert g.assignments['1'][1] is None
    assert not any(a['id']=='lock' for a in g.legal_actions(1))
    with pytest.raises(ValueError):g.act(0,'assign:0:0')


def test_complete_researched_three_battle_campaign_and_predictions():
    g=battle_game()
    assert g.turn==1 and g.phase=='battle'
    g.act(1,'battle:0:0')
    assert g.scores=={'1':1,'0':0} and g.history[-1]['exchange']
    assert g.prediction_results['1'] is True
    g.act(0,'battle:2:2')
    assert g.scores['1']==2
    g.act(1,'battle:1:1')
    assert g.finished and g.result['winner']==1 and len(g.history)==3
    assert g.result['prediction_accuracy']['0'] is None
    assert g.spent['1']==[0,2,1]
    # Unused Bishop is still hidden in the public table.
    assert g.view()['formations']['1'][3]['cards']==[None]


def test_draw_counts_against_challenger_and_remains_visibly_drawn():
    g=battle_game()
    g.hands['1'][2]='2S';g.hands['0'][2]='2H';g.hands['0'][3]='X2'
    # Opposing 2+Wizard would exchange; use plain equal two-card totals instead.
    g.hands['1'][2]='QS';g.hands['0'][2]='3C';g.hands['0'][3]='7C'
    g.act(1,'battle:1:1')
    assert g.history[-1]['winner'] is None and g.history[-1]['credited']==0
    assert g.scores=={'1':0,'0':1} and 'Draw' in g.log[0]


def test_public_and_opponent_projections_hide_live_formations_and_future_deck():
    g=battle_game()
    for viewer in (None,99,0):
        projection=g.view(viewer)
        assert projection['formations']['1'][0]['cards']==[None,None]
        assert projection['hands']['1']==[None]*10
        assert 'deck' not in projection
    own=g.view(1)
    assert own['formations']['1'][0]['cards']==['X1','2S']
    own['formations']['1'][0]['cards'][0]='wrong'
    assert g.piles(1)[0][0]=='X1'
    g.act(1,'battle:0:0')
    assert g.view()['formations']['1'][0]['cards']==['X1','2S']
    assert g.view()['formations']['0'][1]['cards']==[None,None]


def test_opening_ties_redraw_without_exposing_unused_deck():
    g=battle_game()
    # Reset only the opening fixture to exercise equal ranks / later winner.
    g.phase='prediction';g.turn=0;g.predictions={'1':[1,0]};g.opening=[]
    g.deck=['5S','5H','2S','AS','KS']
    g.act(0,'predict:1:0')
    assert g.turn==0 and g.opening==[['5S','5H'],['2S','AS']]
    assert g.deck==['KS']
    assert 'deck' not in g.view()


def test_bad_actions_and_exhausted_opening_rollback_atomically():
    g=battle_game();before=g.to_dict()
    for actor,action in [(0,'battle:0:0'),(1,'battle:99:0'),(1,'lock')]:
        with pytest.raises(ValueError):g.act(actor,action)
        assert g.to_dict()==before
    g.phase='prediction';g.turn=0;g.predictions={'1':[1,0]};g.deck=['2S','2H']
    before=g.to_dict()
    with pytest.raises(ValueError):g.act(0,'predict:1:0')
    assert g.to_dict()==before


def test_bot_ignores_concealed_opposing_strengths():
    g=battle_game();action=g.bot_action()
    g.hands['0']=['AS']*10
    assert g.bot_action()==action


def test_seeded_full_campaign_json_recovery_and_legal_bot():
    for seed in range(30):
        g=Platoon(seed=seed)
        assert len(set(g.hands['1']+g.hands['0']))==20
        for _ in range(80):
            if g.finished:break
            copy=Platoon.from_dict(json.loads(json.dumps(g.to_dict())))
            action=g.bot_action();actor=g.turn
            assert action in {a['id'] for a in g.legal_actions(actor)}
            g.act(actor,action);copy.act(actor,action)
            assert copy.to_dict()==g.to_dict()
        assert g.finished and 3<=len(g.history)<=5
