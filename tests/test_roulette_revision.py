import asyncio
import math
from types import SimpleNamespace
from unittest.mock import Mock, AsyncMock, MagicMock
import pytest
from PIL import Image
from casinogames.casino_games import Roulette, BET_GROUPS
from casinogames.roulette_render import WHEEL_ORDER, landing_angle, animation_frames, SPIN_DURATION_SECONDS, render

def test_five_chips_preserve_total_and_allow_mixed_placements():
    rng=Mock(randrange=Mock(return_value=3))
    game=Roulette(27,rng)
    assert game.chips == [6,6,5,5,5]
    for placement in ('red flower','red','split 4-5','black','red flower'):
        game.place(placement)
    assert game.ready
    assert game.spin()['payout'] == 6*12+6*2+5*6+5*12
    assert sum(game.chips)==27
    with pytest.raises(ValueError): game.undo()
    with pytest.raises(ValueError): game.clear()
    game.spin()
    rng.randrange.assert_called_once()

def test_editing_chips_does_not_change_budget_or_allow_early_spin():
    game=Roulette(3)
    assert len(game.chips)==3
    game.place('red')
    with pytest.raises(ValueError): game.spin()
    game.undo()
    assert game.placements==[]
    for _ in range(3): game.place('black')
    with pytest.raises(ValueError): game.place('red')
    game.clear()
    assert game.chips==[1,1,1]
    assert not game.ready

def test_wheel_mapping_and_animation_hold_real_result():
    assert sorted(WHEEL_ORDER)==list(range(12))
    for pocket in range(12):
        angle=landing_angle(pocket,900)
        recovered=round(((math.degrees(angle)+900+105)%360)/30)%12
        assert WHEEL_ORDER[recovered]==pocket
    game=Roulette(5,Mock(randrange=Mock(return_value=3)))
    game.choose('red flower')
    game.spin()
    frames,durations,loop=animation_frames(game)
    assert sum(durations)==SPIN_DURATION_SECONDS*1000
    assert not loop
    assert frames[0].size==(512,768)
    png=render(game)
    assert frames[-1].tobytes()==Image.open(png).convert('RGBA').tobytes()
    data=render(game,True)
    assert len(data.getvalue())<8_000_000
    with Image.open(data) as image:
        assert 'loop' not in image.info
        assert image.n_frames>30

def test_roulette_controls_and_settlement(monkeypatch):
    import pymongo,dotenv
    monkeypatch.setattr(pymongo,'MongoClient',MagicMock())
    monkeypatch.setattr(dotenv,'load_dotenv',lambda:None)
    from cogs.casino_machines_cog import MachineView,EconomyManager,MetricsManager,placement_label
    assert all(len(f'{placement_label(k)} (x{12//len(v)})')<=100 for k,v in BET_GROUPS.items())
    payout=Mock()
    monkeypatch.setattr(EconomyManager,'payout',payout)
    monkeypatch.setattr(MetricsManager,'record_game_result',Mock())
    async def scenario():
        game=Roulette(25,Mock(randrange=Mock(return_value=3)))
        player=SimpleNamespace(id=42,name='Player')
        cog=SimpleNamespace(game_name='Roulette',cleanup_game=AsyncMock())
        view=MachineView(cog,game,player,False)
        inter=SimpleNamespace(user=player,response=SimpleNamespace(defer=AsyncMock()),
            edit_original_response=AsyncMock(),followup=SimpleNamespace(send=AsyncMock()),
            data={'values':['red flower']})
        spin=next(c for c in view.children if getattr(c,'label',None)=='Spin')
        assert spin.disabled
        for _ in range(5): await view.choose(inter)
        assert not spin.disabled
        await view.undo(inter)
        assert spin.disabled
        await view.choose(inter)
        await view.spin(inter)
        await view.spin(inter)
        payout.assert_called_once_with(42,300,'Player')
        assert inter.edit_original_response.call_args.kwargs['embed'] is None
    asyncio.run(scenario())


@pytest.mark.parametrize('pocket', range(12))
def test_ball_is_carried_by_actual_pocket_without_stopping_wheel(pocket):
    from casinogames.roulette_render import motion_at
    first = motion_at(11.2, pocket)
    last = motion_at(12.1, pocket)
    assert last[0] > first[0]
    for rotation, angle, radius in (first, last):
        assert angle == pytest.approx(landing_angle(pocket, rotation))
        assert radius < 60  # Inside the green radial slots, not the symbol ring.
    before = motion_at(9.4 - .00001, pocket)
    after = motion_at(9.4, pocket)
    assert abs(before[1] - after[1]) < .001
    assert before[2] == pytest.approx(after[2])


def test_idle_motion_and_loss_do_not_change_outcome_or_credit():
    game=Roulette(25,Mock(randrange=Mock(return_value=11)))
    idle,durations,loop=animation_frames(game)
    assert loop and idle[0].tobytes()!=idle[1].tobytes()
    assert game.result is None and game.placements==[]
    game.choose('red')
    result=game.spin().copy()
    frames,durations,loop=animation_frames(game)
    assert result['payout']==0 and game.result==result
    assert not loop and sum(durations)==SPIN_DURATION_SECONDS*1000
    assert frames[-1].tobytes()==Image.open(render(game)).convert('RGBA').tobytes()


@pytest.mark.parametrize('animated', [True, False])
def test_betting_edits_honor_animation_preference(monkeypatch, animated):
    import pymongo,dotenv
    monkeypatch.setattr(pymongo,'MongoClient',MagicMock())
    monkeypatch.setattr(dotenv,'load_dotenv',lambda:None)
    from cogs.casino_machines_cog import MachineView
    async def scenario():
        game=Roulette(25)
        view=MachineView(SimpleNamespace(),game,SimpleNamespace(id=42),animated)
        view.payload=AsyncMock(return_value={})
        inter=SimpleNamespace(response=SimpleNamespace(defer=AsyncMock()),
            edit_original_response=AsyncMock(),data={'values':['red']})
        await view.choose(inter)
        view.payload.assert_awaited_with(animate=animated)
        await view.undo(inter)
        view.payload.assert_awaited_with(animate=animated)
        await view.choose(inter)
        await view.clear(inter)
        view.payload.assert_awaited_with(animate=animated)
        assert game.placements==[] and game.result is None
    asyncio.run(scenario())
