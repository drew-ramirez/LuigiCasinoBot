from copy import deepcopy
import json
import pytest
from casinogames.red7 import Red7, qualifying, palette_score, DECK, card_key


def match():
    game=Red7((11,22),seed=5)
    game.turn=11
    game.palettes={'11':['R1'],'22':['R7']}
    game.hands={'11':['B2','B3'],'22':['Y1']}
    return game


@pytest.mark.parametrize('rule,palette,expected',[
    ('red',['V7','R6','B7'],['B7']),
    ('orange',['R2','B2','V5','Y5'],['V5','Y5']),
    ('yellow',['R1','R5','B6','B7'],['B6','B7']),
    ('green',['R1','V2','G4','B7'],['V2','G4']),
    ('blue',['R1','R7','V6','G4'],['G4','V6','R7']),
    ('indigo',['R1','V2','R2','B3','V5','Y6','G7'],['V5','Y6','G7']),
    ('violet',['R1','V2','B3','R4'],['R1','V2','B3']),
])
def test_all_seven_criteria_choose_correct_best_subset(rule,palette,expected):
    assert qualifying(palette,rule)==expected


def test_number_before_color_and_highest_qualifying_card_tiebreak():
    assert card_key('V7')>card_key('R6')>card_key('O6')
    assert palette_score(['R2','V2'],'orange')<palette_score(['G3','V3'],'orange')
    assert palette_score(['R2','V2'],'orange')>palette_score(['G2','V2'],'orange')
    assert palette_score(['R2','V2','G2'],'orange')>palette_score(['R7','V7'],'orange')


def test_duplicate_ranks_do_not_extend_a_run():
    assert len(qualifying(['R2','V2','G3'],'indigo'))==2
    assert qualifying(['R2','V2','G3'],'indigo')==['R2','G3']


@pytest.mark.parametrize('rule',['green','violet'])
def test_no_qualifying_cards_never_leads(rule):
    game=match();game.palettes={'11':['R7'],'22':['B5']}
    assert not game._leads(11,game.palettes['11'],rule)
    assert palette_score(game.palettes['11'],rule)[0]==0


def test_starting_player_is_after_initial_red_leader_and_deal_has_49_unique_cards():
    for seed in range(10):
        game=Red7((11,22),seed)
        leader=max(game.players,key=lambda p:card_key(game.palettes[str(p)][0]))
        assert game.turn!=leader
        cards=game.deck+sum(game.hands.values(),[])+sum(game.palettes.values(),[])
        assert len(cards)==len(set(cards))==49
        assert all(len(h)==7 for h in game.hands.values())
        assert game.to_dict()==Red7((11,22),seed).to_dict()


def test_compound_turn_is_atomic_even_when_palette_play_alone_would_lose():
    game=match()
    ids={a['id'] for a in game.legal_actions(11)}
    assert 'play:B2' not in ids
    assert 'both:B2:B3' in ids
    before=game.to_dict()
    with pytest.raises(ValueError):game.act(11,'play:B2')
    assert game.to_dict()==before
    game.act(11,'both:B2:B3')
    assert not game.finished and game.turn==22
    assert game.rule=='blue' and game.canvas==['B3']
    assert game.palettes['11']==['R1','B2'] and game.hands['11']==[]


def test_empty_hand_eliminates_when_its_next_turn_arrives():
    game=match();game.act(11,'both:B2:B3')
    game.hands['22']=['Y7','O2']
    game.act(22,'both:Y7:O2')
    assert game.result['winner']==22 and game.result['reason']=='empty_hand'


def test_losing_card_change_is_not_offered_but_concede_is():
    game=match()
    game.hands['11']=['R6']
    assert game.legal_actions(11)==[{'id':'concede','label':'Concede round','group':'Concede',
                                   'description':'You lose this round; no community coins are involved.'}]
    game.act(11,'concede')
    assert game.result['winner']==22


def test_rule_only_action_keeps_palette_and_discards_exactly_one():
    game=match();game.palettes['11']=['R1','B2']
    game.act(11,'rule:B3')
    assert game.palettes['11']==['R1','B2'] and game.canvas==['B3']
    assert game.hands['11']==['B2']


def test_private_hands_deck_and_action_ids_are_not_in_public_projection():
    game=Red7((11,22),seed=8)
    public=game.view()
    assert 'deck' not in public and 'actions' not in public
    for p in game.players:
        own=game.view(p)
        assert own['hands'][str(p)]==game.hands[str(p)]
        other=next(i for i in game.players if i!=p)
        assert own['hands'][str(other)]==[None]*7
        assert all(c not in json.dumps(public) for c in game.hands[str(p)])
    assert game.view(999)['hands']==public['hands']


def test_bot_does_not_read_opponents_hand_or_unused_deck():
    game=match();before=game.bot_action()
    game.hands['22']=['R5','G6','O3'];game.deck=['V1','B7']
    assert game.bot_action()==before


def test_invalid_actor_reused_card_and_action_leave_state_unchanged():
    game=match(); before=game.to_dict()
    for actor,action in [(22,'concede'),(99,'play:B2'),(11,'both:B2:B2'),(11,'rule:R5')]:
        with pytest.raises(ValueError):game.act(actor,action)
        assert game.to_dict()==before
    game.act(11,'both:B2:B3'); before=game.to_dict()
    with pytest.raises(ValueError):game.act(11,'both:B2:B3')
    assert game.to_dict()==before


def test_json_recovery_each_turn_and_card_conservation():
    for seed in range(35):
        game=Red7((1,0),seed)
        for turn in range(20):
            if game.finished:break
            restored=Red7.from_dict(json.loads(json.dumps(game.to_dict())))
            action=game.bot_action();actor=game.turn
            assert action==restored.bot_action()
            game.act(actor,action);restored.act(actor,action)
            assert game.to_dict()==restored.to_dict()
            cards=game.deck+sum(game.hands.values(),[])+sum(game.palettes.values(),[])+game.canvas
            assert len(cards)==len(set(cards))==49
        assert game.finished
        assert game.result['winner'] in game.players


def test_out_of_turn_departure_and_snapshot_isolation():
    game=match(); public=game.view(11);public['hands']['11'].clear()
    assert len(game.hands['11'])==2
    game.concede(22)
    assert game.result['winner']==11
    with pytest.raises(ValueError):game.concede(11)
    bad=game.to_dict();bad['version']='future'
    with pytest.raises(ValueError):Red7.from_dict(bad)
