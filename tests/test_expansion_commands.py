"""Saved solo Discord flows with real engines/store and no live Discord or Mongo."""
import asyncio
import json
from copy import deepcopy
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from casinogames.blackjack import Blackjack
from casinogames.challenges import MemoryMaster, EndlessPairs
from casinogames.fortune_tower import FortuneTower
from casinogames.session_store import SessionStore
from economy.blackjack_table import BlackjackTable


class Users:
    """In-memory single-document Mongo adapter; concurrency is tested separately."""
    def __init__(self, balance=500):
        self.doc = {"_id": "owner-42", "user_id": 42, "balance": balance}
        self.writes = 0

    def find_one(self, query):
        return deepcopy(self.doc)

    def find_one_and_update(self, query, update, return_document):
        for key, expected in query.items():
            actual = self.doc
            for part in key.split('.'):
                actual = actual.get(part) if isinstance(actual, dict) else None
            if isinstance(expected, dict):
                if '$gte' in expected and actual < expected['$gte']:
                    return None
                if '$exists' in expected and (actual is not None) != expected['$exists']:
                    return None
            elif actual != expected:
                return None
        self.doc.update(deepcopy(update.get('$set', {})))
        for key, amount in update.get('$inc', {}).items():
            self.doc[key] = self.doc.get(key, 0) + amount
        for key, amount in update.get('$max', {}).items():
            self.doc[key] = max(self.doc.get(key, 0), amount)
        self.writes += 1
        return deepcopy(self.doc)


def environment(tmp_path, monkeypatch, *, balance=500, cards=None):
    import pymongo
    monkeypatch.setattr(pymongo, 'MongoClient', MagicMock())
    import cogs.casino_expansion_cog as module
    monkeypatch.setattr(module.EconomyManager, 'animations_enabled', lambda *args: False)
    monkeypatch.setattr(module, 'resolve_command_visibility', lambda *args: SimpleNamespace(ephemeral=True, is_public=False))
    calls = []
    def render(kind, public, **options):
        calls.append((kind, deepcopy(public), deepcopy(options)))
        return BytesIO(b'GIF89a' if options.get('animate') else b'\x89PNG\r\n')
    monkeypatch.setattr(module, 'render_table', render)
    store = SessionStore(tmp_path / 'solo.sqlite3')
    users = Users(balance)
    cards = cards or ['8S', '6H', '3D', '10C', '9S', '8H']
    table = BlackjackTable(users, game_factory=lambda bet: Blackjack(bet, shoe=cards))
    cog = module.CasinoExpansionCog(SimpleNamespace(), store=store, blackjack=table)
    message = SimpleNamespace(id=500, edit=AsyncMock())
    def interaction(owner=42):
        return SimpleNamespace(user=SimpleNamespace(id=owner, name='Player', bot=False),
            guild_id=77, guild=SimpleNamespace(id=77), channel_id=88,
            response=SimpleNamespace(defer=AsyncMock(), send_message=AsyncMock()),
            followup=SimpleNamespace(send=AsyncMock()),
            edit_original_response=AsyncMock(return_value=message))
    return module, cog, store, users, interaction, message, calls


def saved(store, kind, game):
    return store.create(77, 42, kind, {'game': game.to_dict()})


def current_view(cog, kind):
    return cog.views[(42, kind)]


@pytest.mark.parametrize('stars,cols,count', [(0, 4, 16), (5, 6, 18), (10, 5, 20)])
def test_memory_layout_obeys_discord_rows_and_preserves_authentic_coordinates(tmp_path, monkeypatch, stars, cols, count):
    async def run():
        module, cog, store, _, _, _, _ = environment(tmp_path, monkeypatch)
        try:
            snap = saved(store, 'memory_master', MemoryMaster(stars=stars, seed=11))
            view = module.SoloView(cog, snap, 'memory_master', 42, False)
            assert len(view.children) <= 25
            rows = {}
            for child in view.children:
                rows[child.row] = rows.get(child.row, 0) + (5 if isinstance(child, discord.ui.Select) else 1)
            assert max(rows.values()) <= 5
            if cols == 6:
                select = next(child for child in view.children if isinstance(child, discord.ui.Select))
                assert len(select.options) == count
                assert select.options[5].label == 'A6'
                assert select.options[-1].label == 'C6'
            else:
                grid = [child for child in view.children if child.row < 4]
                assert len(grid) == count
                assert grid[-1].label == f'D{cols}'
        finally:
            cog.cog_unload()
    asyncio.run(run())


def test_pause_resume_exact_board_then_finish_submits_one_record(tmp_path, monkeypatch):
    async def run():
        module, cog, store, _, interaction, _, _ = environment(tmp_path, monkeypatch)
        kind = 'pairagone_endless'
        try:
            snap = saved(store, kind, EndlessPairs(seed=7))
            await cog.publish(interaction(), snap, kind, 42, False)
            await current_view(cog, kind).run(interaction(), 'pause')
            paused = store.get(snap['id'])
            assert paused['status'] == 'paused'
            assert paused['state'] == snap['state']
            await current_view(cog, kind).run(interaction(), 'resume')
            resumed = store.get(snap['id'])
            assert resumed['status'] == 'active'
            assert resumed['state'] == snap['state']
            finishing = current_view(cog, kind)
            await finishing.run(interaction(), 'finish')
            await finishing.run(interaction(), 'finish')
            assert store.get(snap['id'])['status'] == 'finished'
            assert len(store.records(77, 42, kind)) == 1
        finally:
            cog.cog_unload()
    asyncio.run(run())


def test_paused_finish_button_can_finalize_without_resuming(tmp_path, monkeypatch):
    async def run():
        _, cog, store, _, interaction, _, _ = environment(tmp_path, monkeypatch)
        kind = 'memory_master'
        try:
            snap = saved(store, kind, MemoryMaster(seed=8))
            await cog.publish(interaction(), snap, kind, 42, False)
            await current_view(cog, kind).run(interaction(), 'pause')
            view = current_view(cog, kind)
            finish = next(child for child in view.children if child.label == 'Finish & save')
            await finish.callback(interaction())
            assert store.get(snap['id'])['status'] == 'finished'
            assert len(store.records(77, 42, kind)) == 1
        finally:
            cog.cog_unload()
    asyncio.run(run())


def test_duplicate_choices_and_other_owner_cannot_advance_saved_board(tmp_path, monkeypatch):
    async def run():
        _, cog, store, _, interaction, _, _ = environment(tmp_path, monkeypatch)
        kind = 'memory_master'
        try:
            snap = saved(store, kind, MemoryMaster(seed=9))
            await cog.publish(interaction(), snap, kind, 42, False)
            view = current_view(cog, kind)
            other = interaction(99)
            assert not await view.interaction_check(other)
            await view.run(other, 'choose', 0)
            assert store.get(snap['id']) == snap
            await asyncio.gather(view.run(interaction(), 'choose', 0), view.run(interaction(), 'choose', 1))
            after = store.get(snap['id'])
            assert after['revision'] == 1
            assert len(after['state']['game']['selected']) == 1
            assert after['state']['game']['attempts'] == 0
        finally:
            cog.cog_unload()
    asyncio.run(run())


def test_render_failure_uses_saved_readable_state_and_retry_does_not_reroll(tmp_path, monkeypatch):
    async def run():
        module, cog, store, _, interaction, _, _ = environment(tmp_path, monkeypatch)
        kind = 'memory_master'
        try:
            snap = saved(store, kind, MemoryMaster(seed=19))
            await cog.publish(interaction(), snap, kind, 42, True)
            old = current_view(cog, kind)
            monkeypatch.setattr(module, 'render_table', MagicMock(side_effect=RuntimeError('encoder failure')))
            inter = interaction()
            await old.run(inter, 'choose', 0)
            committed = store.get(snap['id'])
            payload = inter.edit_original_response.call_args.kwargs
            assert payload['attachments'] == []
            assert 'Image unavailable' in payload['content']
            assert snap['state']['game']['board'][0] in payload['content']
            assert committed['state']['game']['board'] == snap['state']['game']['board']
            await old.run(interaction(), 'choose', 0)
            assert store.get(snap['id']) == committed
        finally:
            cog.cog_unload()
    asyncio.run(run())


def test_static_preference_and_explicit_animation_override(tmp_path, monkeypatch):
    async def run():
        _, cog, store, _, interaction, _, calls = environment(tmp_path, monkeypatch)
        try:
            await cog.start_solo(interaction(), 'memory_master')
            original = store.active(77, 42, 'memory_master')
            assert calls[-1][2]['animate'] is False
            await cog.start_solo(interaction(), 'memory_master', animations=True)
            assert calls[-1][2]['animate'] is True
            assert store.active(77, 42, 'memory_master') == original
        finally:
            cog.cog_unload()
    asyncio.run(run())


def test_blackjack_confirmation_duplicate_double_and_result_buttons(tmp_path, monkeypatch):
    async def run():
        _, cog, _, users, interaction, _, calls = environment(tmp_path, monkeypatch)
        try:
            start = interaction()
            await cog.blackjack_start.callback(cog, start, wager=100, animations=False)
            assert users.writes == 0
            menu = start.edit_original_response.call_args.kwargs['view']
            deal = menu.children[0]
            await deal.callback(interaction())
            first = cog.blackjack.get(42)
            assert first['balance'] == 400
            await deal.callback(interaction())
            assert users.writes == 1
            view = current_view(cog, 'blackjack')
            labels = [child.label for child in view.children]
            assert 'Double +100' in labels
            assert calls[-1][1]['dealer'] == ['6H', None]
            assert '10C' not in str(calls[-1][1])
            inter = interaction()
            await view.run(inter, 'double')
            result = cog.blackjack.get(42)
            assert result['balance'] == 700
            assert result['game']['result']['payout'] == 400
            assert 'Returned 400' in inter.edit_original_response.call_args.kwargs['content']
            assert [child.label for child in current_view(cog, 'blackjack').children] == ['Play again', 'Rules']
            await view.run(interaction(), 'double')
            assert users.writes == 2
        finally:
            cog.cog_unload()
    asyncio.run(run())


def test_unfunded_blackjack_optional_stakes_are_disabled_and_odd_wager_never_deals(tmp_path, monkeypatch):
    async def run():
        _, cog, _, users, interaction, _, _ = environment(tmp_path, monkeypatch, balance=100,
            cards=['8S', '10H', '8D', '7C', '9S', '8H'])
        try:
            odd = interaction()
            await cog.blackjack_start.callback(cog, odd, wager=99, animations=False)
            assert users.writes == 0
            assert 'even wager' in odd.edit_original_response.call_args.kwargs['content']
            snap = cog.blackjack.start(42, 100)
            await cog.publish(interaction(), snap, 'blackjack', 42, False)
            buttons = {child.label: child for child in current_view(cog, 'blackjack').children}
            assert buttons['Double +100'].disabled
            assert buttons['Split +100'].disabled
            assert not buttons['Hit'].disabled and not buttons['Stand'].disabled
        finally:
            cog.cog_unload()
    asyncio.run(run())


@pytest.mark.parametrize('kind', ['memory_master', 'pairagone_endless', 'fortune_tower', 'blackjack'])
def test_timeout_pauses_skills_and_banks_or_stands_wager_tables(tmp_path, monkeypatch, kind):
    async def run():
        _, cog, store, users, interaction, message, _ = environment(tmp_path, monkeypatch)
        try:
            if kind == 'blackjack':
                snap = cog.blackjack.start(42, 100)
            else:
                game = {'memory_master': lambda: MemoryMaster(seed=1),
                        'pairagone_endless': lambda: EndlessPairs(seed=1),
                        'fortune_tower': FortuneTower}[kind]()
                snap = saved(store, kind, game)
            await cog.publish(interaction(), snap, kind, 42, False)
            view = current_view(cog, kind)
            await view.on_timeout()
            if kind == 'blackjack':
                result = cog.blackjack.get(42)
                assert result['game']['result'] is not None
                assert result['game']['hands'][0]['cards'] == snap['game']['hands'][0]['cards']
                writes = users.writes
                await view.on_timeout()
                assert users.writes == writes
            elif kind == 'fortune_tower':
                result = store.get(snap['id'])
                assert result['status'] == 'finished'
                assert result['state']['game']['result']['outcome'] == 'banked'
                assert len(store.records(77, 42, kind)) == 1
                assert 'Result: banked' in message.edit.call_args.kwargs['content']
            else:
                result = store.get(snap['id'])
                assert result['status'] == 'paused'
                assert result['state'] == snap['state']
            assert message.edit.call_args.kwargs['view'] is None
        finally:
            cog.cog_unload()
    asyncio.run(run())


def test_stale_timeout_cannot_remove_replacement_controls(tmp_path, monkeypatch):
    async def run():
        _, cog, store, _, interaction, message, _ = environment(tmp_path, monkeypatch)
        kind = 'memory_master'
        try:
            snap = saved(store, kind, MemoryMaster(seed=13))
            await cog.publish(interaction(), snap, kind, 42, False)
            old = current_view(cog, kind)
            await old.run(interaction(), 'choose', 0)
            current = current_view(cog, kind)
            before = store.get(snap['id'])
            await old.on_timeout()
            assert store.get(snap['id']) == before
            assert current_view(cog, kind) is current
            message.edit.assert_not_awaited()
        finally:
            cog.cog_unload()
    asyncio.run(run())


def test_discord_upload_failure_retries_text_after_single_blackjack_settlement(tmp_path, monkeypatch):
    async def run():
        _, cog, _, users, interaction, message, _ = environment(tmp_path, monkeypatch)
        try:
            snap = cog.blackjack.start(42, 100)
            await cog.publish(interaction(), snap, 'blackjack', 42, True)
            view = current_view(cog, 'blackjack')
            inter = interaction()
            response = SimpleNamespace(status=413, reason='Payload Too Large')
            inter.edit_original_response.side_effect = [discord.HTTPException(response, 'upload rejected'), message]
            await view.run(inter, 'double')
            assert inter.edit_original_response.await_count == 2
            fallback = inter.edit_original_response.call_args.kwargs
            assert fallback['attachments'] == []
            assert 'Returned 400' in fallback['content']
            assert users.writes == 2
            assert cog.blackjack.get(42)['balance'] == 700
        finally:
            cog.cog_unload()
    asyncio.run(run())


def test_blackjack_command_resumes_same_funded_hand_without_new_wager(tmp_path, monkeypatch):
    async def run():
        _, cog, _, users, interaction, _, _ = environment(tmp_path, monkeypatch)
        try:
            before = cog.blackjack.start(42, 100)
            inter = interaction()
            await cog.blackjack_start.callback(cog, inter, wager=200, animations=False)
            assert users.writes == 1
            assert cog.blackjack.get(42) == before
            assert current_view(cog, 'blackjack').snapshot == before
            assert 'Hand 1' in inter.edit_original_response.call_args.kwargs['content']
        finally:
            cog.cog_unload()
    asyncio.run(run())


def test_known_cards_only_lists_previously_shown_positions_without_mutation(tmp_path, monkeypatch):
    async def run():
        _, cog, store, _, interaction, _, _ = environment(tmp_path, monkeypatch)
        kind = 'memory_master'
        try:
            game = MemoryMaster(seed=25)
            snap = saved(store, kind, game)
            await cog.publish(interaction(), snap, kind, 42, False)
            inter = interaction()
            await current_view(cog, kind).run(inter, 'notes')
            content = inter.response.send_message.call_args.args[0]
            assert content.count(':') == len(game.hints)
            assert 'assisted play' in content
            assert inter.response.send_message.call_args.kwargs['ephemeral'] is True
            assert store.get(snap['id']) == snap
        finally:
            cog.cog_unload()
    asyncio.run(run())


def test_solo_cogs_register_serializable_command_schemas_and_visibility_keys(tmp_path, monkeypatch):
    """Exercise discord.py registration/serialization without login or tree sync."""
    async def run():
        from discord.ext import commands
        _, cog, _, _, _, _, _ = environment(tmp_path, monkeypatch)
        from cogs.casino_config_cog import CasinoConfigCog, GAME_COMMAND_CHOICES
        from config.casino_config import DEFAULT_GAME_COMMAND_KEYS
        bot = commands.Bot(command_prefix='!', intents=discord.Intents.none())
        try:
            cog.bot = bot
            await bot.add_cog(cog)
            await bot.add_cog(CasinoConfigCog(bot))
            payload = json.loads(json.dumps([command.to_dict(bot.tree) for command in bot.tree.get_commands()]))
            registered = {command['name']: command for command in payload}
            names = {'casino_memorymaster', 'casino_pairagone_endless', 'casino_fortune_tower', 'casino_blackjack'}
            assert names.issubset(registered)
            assert 'casino' in registered
            for name in names:
                command = registered[name]
                assert 1 <= len(command['description']) <= 100
                assert len(command.get('options', [])) <= 25
            blackjack = {option['name']: option for option in registered['casino_blackjack']['options']}
            assert blackjack['wager']['type'] == discord.AppCommandOptionType.integer.value
            assert blackjack['wager']['min_value'] == 2
            assert blackjack['wager']['max_value'] == 1000000
            assert blackjack['animations']['type'] == discord.AppCommandOptionType.boolean.value
            keys = {'memory_master', 'pairagone_endless', 'blackjack', 'fortune_tower'}
            assert keys.issubset(DEFAULT_GAME_COMMAND_KEYS)
            assert keys.issubset({choice.value for choice in GAME_COMMAND_CHOICES})
        finally:
            await bot.close()
    asyncio.run(run())
