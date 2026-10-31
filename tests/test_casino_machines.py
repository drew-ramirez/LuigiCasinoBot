import asyncio
from itertools import product
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, MagicMock
import pytest
from PIL import Image
from casinogames.casino_games import Roulette, Slots, BET_GROUPS
from casinogames.casino_render import render

@pytest.mark.parametrize('selection', list(BET_GROUPS))
def test_all_roulette_pockets(selection):
    for pocket in range(12):
        rng = Mock()
        rng.randrange.return_value = pocket
        game = Roulette(5, rng)
        game.choose(selection)
        expected = 5 * (12 // len(BET_GROUPS[selection])) if pocket in BET_GROUPS[selection] else 0
        assert game.spin() == {'pocket': pocket, 'payout': expected}
        game.spin()
        rng.randrange.assert_called_once_with(12)
        with pytest.raises(ValueError):
            game.choose('red')

def test_slot_paytable_exhaustively():
    for reels in product(Slots.SYMBOLS, repeat=3):
        ordinary = [s for s in reels if s != 'superstar']
        wild = 3-len(ordinary)
        expected = 20 if wild == 3 else 4 if wild == 2 else Slots.PAYTABLE[ordinary[0]] if len(set(ordinary)) == 1 else 2 if wild == 1 else 0
        assert Slots.multiplier(reels) == expected

def test_stop_is_idempotent():
    rng = Mock()
    rng.choice.side_effect = ['star', 'star', 'star']
    game = Slots(10, rng)
    game.stop(0)
    game.stop(0)
    assert game.result is None
    game.stop(2)
    assert game.stop(1) == {'payout': 150}
    game.stop(1)
    assert rng.choice.call_count == 3

@pytest.mark.parametrize('cls', [Roulette, Slots])
def test_render_does_not_change_outcome(cls):
    game = cls(5)
    for animated in (False, True):
        data = render(game, animated)
        assert len(data.getvalue()) < 8_000_000
        with Image.open(data) as img:
            assert img.size == (512,768)
            if animated:
                assert img.n_frames > 1
    assert game.result is None
    if cls is Slots:
        assert game.reels == [None]*3

def test_buttons_settle_once_and_reject_other_players(monkeypatch):
    import pymongo
    import dotenv
    monkeypatch.setattr(pymongo, 'MongoClient', MagicMock())
    monkeypatch.setattr(dotenv, 'load_dotenv', lambda: None)
    from cogs.casino_machines_cog import MachineView, EconomyManager, MetricsManager
    payout = Mock()
    monkeypatch.setattr(EconomyManager, 'payout', payout)
    monkeypatch.setattr(MetricsManager, 'record_game_result', Mock())
    async def scenario():
        game = Slots(5, Mock(choice=Mock(return_value='star')))
        cog = SimpleNamespace(game_name='Slots', cleanup_game=AsyncMock())
        player = SimpleNamespace(id=42, name='Player')
        view = MachineView(cog, game, player, False)
        other = SimpleNamespace(user=SimpleNamespace(id=9), response=SimpleNamespace(send_message=AsyncMock()))
        assert not await view.interaction_check(other)
        inter = SimpleNamespace(user=player, response=SimpleNamespace(defer=AsyncMock()), edit_original_response=AsyncMock())
        for index in (0,0,1,2,2):
            await view.act(inter,index)
        payout.assert_called_once_with(42,75,'Player')
        cog.cleanup_game.assert_awaited_once_with(42)
    asyncio.run(scenario())

def test_wager_menu_only_charges_once(monkeypatch):
    import pymongo
    import dotenv
    monkeypatch.setattr(pymongo, 'MongoClient', MagicMock())
    monkeypatch.setattr(dotenv, 'load_dotenv', lambda: None)
    from utils.bet_selector import BetSelectView, EconomyManager
    monkeypatch.setattr(EconomyManager,'balance',Mock(return_value=100))
    wager = Mock(return_value=True)
    monkeypatch.setattr(EconomyManager,'wager',wager)
    async def scenario():
        start = AsyncMock()
        view = BetSelectView(42,'Player',start)
        inter = SimpleNamespace(user=SimpleNamespace(id=42),response=SimpleNamespace(send_message=AsyncMock()))
        await view.children[0].callback(inter)
        await view.children[1].callback(inter)
        assert wager.call_count == 1
        assert start.await_count == 1
    asyncio.run(scenario())
