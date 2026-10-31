import json
from collections import Counter
import pytest
from casinogames.cuttle import Cuttle, DECK


def fixture(human=(), bot=(), points=(), permanents=(), deck=(), scrap=()):
    g=Cuttle((1,0),seed=1)
    g.hands={'1':list(human),'0':list(bot)}
    g.points=[{'card':c,'owner':p,'jacks':list(j)} for c,p,j in points]
    g.permanents=[{'card':c,'owner':p} for c,p in permanents]
    g.deck=list(deck);g.scrap=list(scrap)
    return g


def allow(g):
    assert g.phase=='counter'
    g.act(g.turn,'allow')


def test_initial_hands_and_public_projection():
    g=Cuttle(seed=1)
    assert len(g.deck)==41 and len(g.hands['1'])==5 and len(g.hands['0'])==6
    assert g.view()['hands']=={'1':[None]*5,'0':[None]*6}
    assert g.view(1)['hands']['1']==g.hands['1']
    assert 'deck' not in g.view() and 'scrap' not in g.view()


@pytest.mark.parametrize('count,threshold',[(0,21),(1,14),(2,10),(3,7),(4,5)])
def test_classic_king_thresholds(count,threshold):
    g=fixture(permanents=[(c,1) for c in ['KC','KD','KH','KS'][:count]])
    assert g.threshold(1)==threshold


def test_points_win_and_scuttle_rank_suit_order():
    g=fixture(human=['7H','7C','6S'],points=[('7D',0,[]),('6H',0,[])])
    ids={a['id'] for a in g.legal_actions(1)}
    assert 'scuttle:7H:7D' in ids and 'scuttle:7C:7D' not in ids
    assert 'scuttle:6S:6H' in ids
    g.act(1,'scuttle:7H:7D')
    assert '7D' in g.scrap and g.score(0)==6
    g=fixture(human=['AS'],points=[('10D',1,[]),('10C',1,[])])
    g.act(1,'points:AS')
    assert g.result['winner']==1 and g.result['scores']['1']==21


def test_counter_window_exists_without_a_two_and_counter_counter_restores_effect():
    g=fixture(human=['AS','2D'],bot=['2H'],points=[('10C',0,[])])
    g.act(1,'effect:AS')
    assert g.phase=='counter' and g.turn==0 and g.score(0)==10
    g.act(0,'counter:2H');g.act(1,'counter:2D');allow(g)
    assert not g.points and {'AS','2H','2D','10C'}<=set(g.scrap)
    assert g.turn==0 and g.phase=='play'
    g=fixture(human=['AS'],bot=[],points=[('10C',0,[])])
    g.act(1,'effect:AS')
    assert g.phase=='counter' and g.legal_actions(0)==[{'id':'allow','label':'Allow the pending effect / response','group':'Response'}]


def test_single_counter_cancels_effect_and_never_scores_twos():
    g=fixture(human=['AS'],bot=['2H'],points=[('10C',0,[])])
    g.act(1,'effect:AS');g.act(0,'counter:2H');allow(g)
    assert g.score(0)==10 and g.score(1)==0 and set(g.scrap)=={'AS','2H'}


def test_queen_protects_targets_and_oneoffs_but_not_queens_or_scuttles():
    g=fixture(human=['2C','9C','JC','10S'],bot=['2D'],points=[('9H',0,[])],permanents=[('QC',0),('KC',0)])
    ids={a['id'] for a in g.legal_actions(1)}
    assert 'effect:2C:QC' in ids and 'effect:2C:KC' not in ids
    assert 'effect:9C:KC' not in ids and 'jack:JC:9H' not in ids
    assert 'scuttle:10S:9H' in ids
    g=fixture(human=['AS'],bot=['2D'],permanents=[('QC',1)])
    g.act(1,'effect:AS')
    assert [a['id'] for a in g.legal_actions(0)]==['allow']


def test_three_rummages_after_counter_resolution_but_cannot_take_itself():
    g=fixture(human=['3C','2C'],bot=['2H'],scrap=['AS'])
    g.act(1,'effect:3C');g.act(0,'counter:2H');g.act(1,'counter:2C');allow(g)
    assert g.phase=='rummage'
    ids={a['id'] for a in g.legal_actions(1)}
    assert 'take:2H' in ids and 'take:3C' not in ids
    g.act(1,'take:2H')
    assert g.hands['1']==['2H'] and '3C' in g.scrap


def test_four_discard_choice_belongs_to_opponent_and_five_draws_remaining():
    g=fixture(human=['4C'],bot=['AS','2H','KD'])
    g.act(1,'effect:4C');allow(g)
    assert g.phase=='discard' and g.turn==0 and len(g.legal_actions(0))==3
    g.act(0,'discard:AS,KD')
    assert g.hands['0']==['2H'] and {'AS','KD','4C'}<=set(g.scrap) and g.turn==0
    g=fixture(human=['5C'],deck=['AS'])
    g.act(1,'effect:5C');allow(g)
    assert g.hands['1']==['AS'] and not g.deck


def test_glasses_expose_and_retain_historical_knowledge_after_removal():
    g=fixture(human=['8C'],bot=['2H','KD'])
    g.act(1,'permanent:8C')
    assert g.view()['hands']['0']==['2H','KD']
    g.act(0,'effect:2H:8C');allow(g)
    assert g.view()['hands']['0']==[None]
    assert 'KD' in g.view()['known_hands']['0']


def test_jack_stack_transfers_and_return_restores_previous_controller():
    g=fixture(human=['JC'],bot=['JD','9C'],points=[('10H',0,[])])
    g.act(1,'jack:JC:10H')
    assert g.points[0]['owner']==1
    g.act(0,'jack:JD:10H')
    assert g.points[0]['owner']==0 and g.points[0]['jacks']==['JC','JD']
    g.hands['1']=['9H']
    g.act(1,'effect:9H:JD');allow(g)
    assert g.points[0]['owner']==1 and g.points[0]['jacks']==['JC'] and 'JD' in g.hands['0']


def test_six_removes_all_permanents_and_reverses_jacks_without_scrapping_points():
    g=fixture(human=['6C'],points=[('10H',1,['JC']),('5H',0,['JD','JS'])],permanents=[('QC',0),('KD',1),('8S',1)])
    g.act(1,'effect:6C');allow(g)
    assert not g.permanents and all(not p['jacks'] for p in g.points)
    assert [p['owner'] for p in g.points]==[0,0]
    assert {'JC','JD','JS','QC','KD','8S','6C'}==set(g.scrap)


def test_forced_seven_jack_must_transfer_own_point_or_scrap_when_no_target():
    g=fixture(human=['7C'],points=[('5H',1,[])],deck=['JC'])
    g.act(1,'effect:7C');allow(g)
    assert g.phase=='forced' and g.turn==1
    assert [a['id'] for a in g.legal_actions(1)]==['jack:JC:5H']
    assert g.view()['hands']['1']==['JC']
    g.act(1,'jack:JC:5H')
    assert g.points[0]['owner']==0 and g.turn==0
    g=fixture(human=['7C'],deck=['JC'])
    g.act(1,'effect:7C');allow(g)
    assert g.phase=='play' and g.turn==0 and set(g.scrap)=={'7C','JC'}


def test_three_empty_deck_passes_draw_and_play_resets_count():
    g=fixture(human=['AS'])
    g.act(1,'pass');g.act(0,'pass');g.act(1,'points:AS')
    assert g.passes==0
    g.act(0,'pass');g.act(1,'pass');g.act(0,'pass')
    assert g.finished and g.result['winner'] is None


def test_invalid_action_and_wrong_actor_leave_snapshot_untouched():
    g=Cuttle(seed=2);before=g.to_dict()
    with pytest.raises(ValueError):g.act(0,'draw')
    with pytest.raises(ValueError):g.act(1,'counter:2C')
    assert g.to_dict()==before
    g.concede(1);assert g.result['winner']==0


def test_response_and_forced_phases_restore_without_reroll():
    g=fixture(human=['7C','2D'],bot=['2H'],deck=['5S','AS','KD'])
    for action in ['effect:7C','counter:2H','counter:2D','allow','permanent:KD']:
        restored=Cuttle.from_dict(json.loads(json.dumps(g.to_dict())))
        actor=g.turn
        g.act(actor,action);restored.act(actor,action)
        assert restored.to_dict()==g.to_dict()


@pytest.mark.parametrize('seed',range(8))
def test_complete_bot_game_has_deterministic_recovery_and_card_conservation(seed):
    g=Cuttle((1,0),seed=seed)
    for _ in range(600):
        cards=g.deck+sum(g.hands.values(),[])+g.scrap+[p['card'] for p in g.points]+[j for p in g.points for j in p['jacks']]+[p['card'] for p in g.permanents]
        if g.pending:
            cards+=[g.pending['card']]
            if g.phase=='counter':cards += [c['card'] for c in g.pending['counters']]
        assert Counter(cards)==Counter(DECK)
        if g.finished:break
        restored=Cuttle.from_dict(json.loads(json.dumps(g.to_dict())))
        action=g.bot_action();actor=g.turn
        assert restored.bot_action()==action
        g.act(actor,action);restored.act(actor,action)
        assert restored.to_dict()==g.to_dict()
    assert g.finished


def test_bot_decision_does_not_read_hidden_hand_or_future_deck():
    g=Cuttle(seed=32)
    decision=g.bot_action()
    other=g.players[1]
    hidden=list(reversed(g.hands[str(other)]+g.deck))
    n=len(g.hands[str(other)])
    g.hands[str(other)],g.deck=hidden[:n],hidden[n:]
    assert g.bot_action()==decision


def test_public_counter_window_cannot_reveal_whether_a_two_is_held():
    with_two=fixture(human=('AS',),bot=('2H','5S'),points=(('10H',0,()),))
    without_two=fixture(human=('AS',),bot=('3H','5S'),points=(('10H',0,()),))
    with_two.act(1,'effect:AS')
    without_two.act(1,'effect:AS')
    assert with_two.view()==without_two.view()
    assert len(with_two.legal_actions(0))==2
    assert len(without_two.legal_actions(0))==1
