import asyncio
from itertools import permutations
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, MagicMock
import pytest
from PIL import Image
from casinogames.casino_games import Roulette, Slots
from casinogames.casino_render import render

@pytest.mark.parametrize(('selection', 'winners', 'gross'), [
    *[(name, {pocket}, 60) for pocket, name in enumerate((
        'red star', 'red mario', 'red luigi', 'red flower', 'red mushroom', 'red cloud',
        'black star', 'black mario', 'black luigi', 'black flower', 'black mushroom', 'black cloud',
    ))],
    ('red', {0, 1, 2, 3, 4, 5}, 10),
    ('black', {6, 7, 8, 9, 10, 11}, 10),
    *[(f'split {a}-{b}', {a - 1, b - 1}, 30) for a, b in (
        (1, 2), (2, 3), (4, 5), (5, 6), (7, 8), (8, 9), (10, 11), (11, 12),
        (1, 4), (2, 5), (3, 6), (4, 7), (5, 8), (6, 9), (7, 10), (8, 11), (9, 12),
    )],
    *[(f'corner {a}/{b}/{c}/{d}', {a - 1, b - 1, c - 1, d - 1}, 15)
      for a, b, c, d in (
          (1, 2, 4, 5), (2, 3, 5, 6), (4, 5, 7, 8),
          (5, 6, 8, 9), (7, 8, 10, 11), (8, 9, 11, 12),
      )],
])
def test_roulette_payout_for_each_bet_type(selection, winners, gross):
    for pocket in range(12):
        draws = [pocket, (pocket + 1) % 12]
        game = Roulette(5, Mock(randrange=Mock(side_effect=draws)))
        for _ in range(5):
            game.place(selection)
        result = {'pocket': pocket, 'payout': gross if pocket in winners else 0}
        assert game.spin() == result
        assert game.spin() == result
        with pytest.raises(ValueError):
            game.place(selection)


def test_slot_payouts_follow_the_published_paytable():
    examples = [
        (('superstar',) * 3, 20),
        (('mushroom',) * 3, 10),
        (('flower',) * 3, 10),
        (('star',) * 3, 15),
        (('feather',) * 3, 5),
        (('egg',) * 3, 5),
        (('star', 'superstar', 'star'), 15),
        (('superstar', 'star', 'superstar'), 4),
        (('superstar', 'feather', 'egg'), 2),
        (('star', 'star', 'mushroom'), 0),
    ]
    for reels, multiplier in examples:
        for order in sorted(set(permutations(reels))):
            game = Slots(5, Mock(choice=Mock(side_effect=order)))
            for index in range(3):
                result = game.stop(index)
            assert result == {'payout': 5 * multiplier}, order


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
