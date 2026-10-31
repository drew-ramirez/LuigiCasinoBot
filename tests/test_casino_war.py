import json
import pytest
from casinogames.casino_war import CasinoWar


@pytest.mark.parametrize('cards,outcome,gross', [(['AS','KH'],'win',40),(['2S','KH'],'loss',0)])
def test_initial_comparison(cards,outcome,gross):
    game=CasinoWar(deck=cards)
    assert game.finished and game.result['outcome']==outcome and game.result['gross']==gross
    assert game.legal_actions(1)==[]


@pytest.mark.parametrize('after,outcome,gross', [(['KS','QH'],'win',60),(['KS','KH'],'war_tie',80),(['2S','KH'],'loss',0)])
def test_three_burn_war_payouts(after,outcome,gross):
    game=CasinoWar(deck=['5S','5H','AS','AC','AD']+after+['2C'])
    assert not game.finished and game.phase=='tie'
    game.act(1,'war')
    assert game.cards==after and game.burned==3 and game.deck==['2C']
    assert game.result['gross']==gross and game.result['net']==gross-40
    assert game.result['outcome']==outcome
    before=game.to_dict()
    with pytest.raises(ValueError): game.act(1,'war')
    assert game.to_dict()==before


def test_surrender_and_private_future_cards():
    game=CasinoWar(deck=['5S','5H','AS','AC','AD','2C','3C'])
    assert 'AS' not in json.dumps(game.view())
    game.act(1,'surrender')
    assert game.result['gross']==10 and game.result['net']==-10
    assert game.burned==0


def test_invalid_action_and_exhausted_shoe_are_atomic():
    game=CasinoWar(deck=['5S','5H','AS'])
    before=game.to_dict()
    for actor,action in [(0,'war'),(1,'hit'),(1,'war')]:
        with pytest.raises(ValueError): game.act(actor,action)
        assert game.to_dict()==before


def test_save_restores_future_war_and_seed():
    game=CasinoWar(deck=['5S','5H','AS','AC','AD','KS','KH'])
    copy=CasinoWar.from_dict(json.loads(json.dumps(game.to_dict())))
    game.act(1,'war');copy.act(1,'war')
    assert copy.to_dict()==game.to_dict()
    assert CasinoWar(seed=14).to_dict()==CasinoWar(seed=14).to_dict()


@pytest.mark.parametrize('stake',[0,3,-2,True,2.5])
def test_exact_even_practice_stake(stake):
    with pytest.raises(ValueError): CasinoWar(stake=stake)
