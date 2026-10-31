import asyncio
from copy import deepcopy
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import discord

from casinogames.session_store import SessionStore
from casinogames.thrilling_cards import ThrillingMatch
from cogs.thrilling_cards_cog import KIND, ThrillingCardsCog, ThrillingView, _clock_token, _projection


def environment(tmp_path, monkeypatch):
    import casinogames.expansion_render as renderer
    calls = []
    def render(kind, public, **kwargs):
        calls.append((kind, deepcopy(public), deepcopy(kwargs)))
        return BytesIO(b'playable-render-fixture')
    monkeypatch.setattr(renderer, 'render_table', render)
    message = SimpleNamespace(id=500, edit=AsyncMock())
    channel = SimpleNamespace(id=88, guild=SimpleNamespace(id=77),
        send=AsyncMock(return_value=message), fetch_message=AsyncMock(return_value=message))
    bot = SimpleNamespace(get_channel=lambda channel_id: channel)
    store = SessionStore(tmp_path / 'sessions.sqlite3')
    cog = ThrillingCardsCog(bot, store=store)
    cog._animated = AsyncMock(return_value=False)
    cog._public_allowed = AsyncMock(return_value=True)
    def interaction(player=1, guild=77, bot_user=False):
        return SimpleNamespace(user=SimpleNamespace(id=player, bot=bot_user), guild_id=guild,
            channel_id=88, channel=channel, response=SimpleNamespace(defer=AsyncMock(), send_message=AsyncMock()),
            followup=SimpleNamespace(send=AsyncMock()))
    return cog, store, interaction, message, channel, calls


def lobby(cog, store, players=(1,)):
    return store.create(77, 1, KIND, dict(phase='lobby', players=list(players), ready=[],
        match=None, boot=cog.boot_id, channel_id=88, message_id=500))


def playing(cog, store, players=(1, 2, 3)):
    match = ThrillingMatch(list(players))
    match.next_hand(cards=['AS', 'KH', '2C', '3D'][:len(players)])
    return store.create(77, 1, KIND, dict(phase='playing', players=list(players), ready=list(players),
        match=match.to_dict(), boot=cog.boot_id, channel_id=88, message_id=500))


def content(inter):
    return ' '.join(str(call.args[0] if call.args else call.kwargs.get('content', ''))
                    for call in inter.followup.send.call_args_list)


@pytest.mark.parametrize('count', [2, 3, 4])
def test_lobby_join_ready_start_requires_owner_and_every_consent(tmp_path, monkeypatch, count):
    async def run():
        cog, store, inter, _, _, _ = environment(tmp_path, monkeypatch)
        try:
            await cog.thrilling.callback(cog, inter(), None)
            snap = store.active(77, 1, KIND)
            assert snap['state']['message_id'] == 500
            for p in range(2, count + 1):
                await cog.handle(inter(p), snap['id'], snap['revision'], 'join')
                snap = store.get(snap['id'])
            bad = inter(1)
            await cog.handle(bad, snap['id'], snap['revision'], 'start')
            assert 'all ready' in content(bad)
            for p in range(1, count + 1):
                await cog.handle(inter(p), snap['id'], snap['revision'], 'ready')
                snap = store.get(snap['id'])
            bad = inter(2)
            await cog.handle(bad, snap['id'], snap['revision'], 'start')
            assert 'Only the owner' in content(bad)
            await cog.handle(inter(1), snap['id'], snap['revision'], 'start')
            snap = store.get(snap['id'])
            assert snap['state']['phase'] == 'playing'
            assert len(ThrillingMatch.from_dict(snap['state']['match']).hand.players) == count
            assert _clock_token(snap) == ('turn', 0, 1)
        finally:
            cog.cog_unload()
    asyncio.run(run())


def test_stale_duplicate_and_out_of_turn_actions_cannot_spend_twice(tmp_path, monkeypatch):
    async def run():
        cog, store, inter, _, _, _ = environment(tmp_path, monkeypatch)
        try:
            snap = playing(cog, store)
            await cog.handle(inter(2), snap['id'], snap['revision'], 'open', 5, private=True)
            assert store.get(snap['id'])['revision'] == 0
            await cog.handle(inter(1), snap['id'], snap['revision'], 'open', 5, private=True)
            duplicate = inter(1)
            await cog.handle(duplicate, snap['id'], snap['revision'], 'open', 5, private=True)
            after = store.get(snap['id'])
            hand = ThrillingMatch.from_dict(after['state']['match']).hand
            assert hand.pot == 7 and hand.revision == 1
            assert 'stale' in content(duplicate)
        finally:
            cog.cog_unload()
    asyncio.run(run())


def test_private_render_authentication_and_public_card_mask(tmp_path, monkeypatch):
    async def run():
        cog, store, inter, message, _, calls = environment(tmp_path, monkeypatch)
        try:
            snap = playing(cog, store)
            await cog._publish(snap)
            public = calls[-1][1]
            assert all(seat['card'] is None for seat in public['seats'])
            assert all(card not in message.edit.call_args.kwargs['content'] for card in ('AS', 'KH', '2C'))
            user = inter(2)
            await cog.handle(user, snap['id'], snap['revision'], 'private')
            private = calls[-1][1]
            assert [s['card'] for s in private['seats']] == ['AS', None, '2C']
            assert user.followup.send.call_args.kwargs['ephemeral'] is True
            other = inter(999)
            await cog.handle(other, snap['id'], snap['revision'], 'private')
            assert 'Only a dealt player' in content(other)
            assert len(calls) == 2
            view = ThrillingView(cog, snap, viewer=2)
            assert not await view.interaction_check(inter(1))
            assert await view.interaction_check(inter(2))
        finally:
            cog.cog_unload()
    asyncio.run(run())


def test_foreign_guild_and_bot_cannot_join_or_resume(tmp_path, monkeypatch):
    async def run():
        cog, store, inter, _, _, _ = environment(tmp_path, monkeypatch)
        try:
            snap = lobby(cog, store)
            bad = inter(2, guild=999)
            await cog.handle(bad, snap['id'], snap['revision'], 'join')
            assert 'in this server' in content(bad)
            bad = inter(2, bot_user=True)
            await cog.handle(bad, snap['id'], snap['revision'], 'join')
            assert 'human' in content(bad)
            assert store.get(snap['id']) == snap
        finally:
            cog.cog_unload()
    asyncio.run(run())


def test_refresh_rules_and_out_of_turn_leave_never_extend_turn(tmp_path, monkeypatch):
    async def run():
        cog, store, inter, _, _, _ = environment(tmp_path, monkeypatch)
        try:
            snap = playing(cog, store)
            await cog._publish(snap)
            deadline = cog.deadlines[snap['id']]
            for action in ('rules', 'refresh', 'private'):
                await cog.handle(inter(1), snap['id'], snap['revision'], action)
                assert cog.deadlines[snap['id']] == deadline
            await cog.handle(inter(3), snap['id'], snap['revision'], 'leave')
            assert cog.deadlines[snap['id']] == deadline
            saved = store.get(snap['id'])
            match = ThrillingMatch.from_dict(saved['state']['match'])
            assert match.departed == {3}
            assert match.hand.commitments[3] == 1
        finally:
            cog.cog_unload()
    asyncio.run(run())


def test_restart_requires_explicit_resume_without_redealing(tmp_path, monkeypatch):
    async def run():
        old, store, inter, _, channel, _ = environment(tmp_path, monkeypatch)
        snap = playing(old, store)
        old.cog_unload()
        new = ThrillingCardsCog(old.bot, store=store)
        new._animated = AsyncMock(return_value=False)
        new._public_allowed = AsyncMock(return_value=True)
        try:
            bad = inter(1)
            await new.handle(bad, snap['id'], snap['revision'], 'open', 2)
            assert 'paused' in content(bad)
            assert not new.deadlines
            await new.thrilling.callback(new, inter(2), snap['id'])
            saved = store.get(snap['id'])
            assert saved['state']['match'] == snap['state']['match']
            assert saved['state']['boot'] == new.boot_id
            assert saved['id'] in new.deadlines
            channel.fetch_message.assert_awaited()
        finally:
            new.cog_unload()
    asyncio.run(run())


def test_timeout_folds_once_and_settles_practice_pot(tmp_path, monkeypatch):
    async def run():
        cog, store, _, _, _, _ = environment(tmp_path, monkeypatch)
        try:
            snap = playing(cog, store, players=(1, 2))
            token = _clock_token(snap)
            await cog._timeout(snap['id'], token, 0)
            saved = store.get(snap['id'])
            match = ThrillingMatch.from_dict(saved['state']['match'])
            assert match.hand.result['reason'] == 'fold'
            assert match.hand.result['winner'] == 2
            assert match.chips == {1: 74, 2: 76}
            assert match.hand.result['revealed'] == {}
            await cog._timeout(snap['id'], token, 0)
            assert store.get(snap['id']) == saved
        finally:
            cog.cog_unload()
    asyncio.run(run())


def test_lobby_expiry_never_deals_or_changes_a_wallet(tmp_path, monkeypatch):
    async def run():
        cog, store, _, _, _, _ = environment(tmp_path, monkeypatch)
        snap = lobby(cog, store, players=(1, 2))
        await cog._timeout(snap['id'], ('lobby',), 0)
        saved = store.get(snap['id'])
        assert saved['status'] == 'finished'
        assert saved['state']['phase'] == 'expired'
        assert saved['state']['match'] is None
        cog.cog_unload()
    asyncio.run(run())


def test_renderer_failure_keeps_saved_hand_and_safe_text_playable(tmp_path, monkeypatch):
    async def run():
        import casinogames.expansion_render as renderer
        cog, store, inter, message, _, _ = environment(tmp_path, monkeypatch)
        def broken(*args, **kwargs):
            raise RuntimeError('image unavailable')
        monkeypatch.setattr(renderer, 'render_table', broken)
        try:
            snap = playing(cog, store)
            user = inter(1)
            await cog.handle(user, snap['id'], snap['revision'], 'open', 2, private=True)
            saved = store.get(snap['id'])
            assert saved['status'] == 'active'
            assert ThrillingMatch.from_dict(saved['state']['match']).hand.target == 2
            assert 'AS' not in message.edit.call_args.kwargs['content']
            assert 'AS' not in content(user)
            assert 'KH' in content(user)
            assert message.edit.call_args.kwargs['attachments'] == []
        finally:
            cog.cog_unload()
    asyncio.run(run())


def test_failed_publication_pauses_saved_action_and_resume_preserves_cards(tmp_path, monkeypatch):
    async def run():
        cog, store, inter, message, _, _ = environment(tmp_path, monkeypatch)
        try:
            snap = playing(cog, store)
            message.edit.side_effect = RuntimeError('network down')
            await cog.handle(inter(1), snap['id'], snap['revision'], 'open', 3)
            saved = store.get(snap['id'])
            assert saved['status'] == 'paused'
            hand = ThrillingMatch.from_dict(saved['state']['match']).hand
            assert hand.target == 3 and hand.cards[1] == 'AS'
            assert snap['id'] not in cog.tasks
            message.edit.side_effect = None
            await cog.thrilling.callback(cog, inter(2), snap['id'])
            resumed = store.get(snap['id'])
            assert resumed['status'] == 'active'
            assert resumed['state']['match'] == saved['state']['match']
        finally:
            cog.cog_unload()
    asyncio.run(run())


def test_five_hands_finish_with_conserved_standings_and_no_replay_rewards(tmp_path, monkeypatch):
    async def run():
        cog, store, inter, _, _, _ = environment(tmp_path, monkeypatch)
        try:
            snap = playing(cog, store, players=(1, 2))
            for number in range(5):
                hand = ThrillingMatch.from_dict(snap['state']['match']).hand
                await cog.handle(inter(hand.turn), snap['id'], snap['revision'], 'open', 1)
                snap = store.get(snap['id'])
                hand = ThrillingMatch.from_dict(snap['state']['match']).hand
                await cog.handle(inter(hand.turn), snap['id'], snap['revision'], 'call')
                snap = store.get(snap['id'])
                if number < 4:
                    await cog.handle(inter(1), snap['id'], snap['revision'], 'next')
                    snap = store.get(snap['id'])
            assert snap['status'] == 'finished'
            match = ThrillingMatch.from_dict(snap['state']['match'])
            assert len(match.hands) == 5 and sum(match.chips.values()) == 150
            await cog.handle(inter(1), snap['id'], snap['revision'], 'next')
            assert store.get(snap['id']) == snap
        finally:
            cog.cog_unload()
    asyncio.run(run())


@pytest.mark.parametrize('magic, filename', [(b'GIF89a', 'thrilling.gif'), (b'\x89PNG\r\n', 'thrilling.png')])
def test_filename_follows_rendered_bytes_even_with_animation_enabled(tmp_path, monkeypatch, magic, filename):
    async def run():
        import casinogames.expansion_render as renderer
        cog, store, _, _, _, _ = environment(tmp_path, monkeypatch)
        cog._animated.return_value = True
        monkeypatch.setattr(renderer, 'render_table', lambda *a, **k: BytesIO(magic + b'image'))
        payload = await cog._payload(playing(cog, store))
        assert payload['attachments'][0].filename == filename
        cog.cog_unload()
    asyncio.run(run())


def test_private_dispatch_defensively_rejects_another_user(tmp_path, monkeypatch):
    async def run():
        cog, store, inter, _, _, _ = environment(tmp_path, monkeypatch)
        snap = playing(cog, store)
        view = ThrillingView(cog, snap, viewer=1)
        other = inter(2)
        await view.dispatch(other, 'rules')
        other.response.send_message.assert_awaited_once()
        other.response.defer.assert_not_awaited()
        assert store.get(snap['id']) == snap
        cog.cog_unload()
    asyncio.run(run())


def test_private_channel_cannot_create_public_lobby(tmp_path, monkeypatch):
    async def run():
        cog, store, inter, _, channel, _ = environment(tmp_path, monkeypatch)
        cog._public_allowed.return_value = False
        user = inter(1)
        await cog.thrilling.callback(cog, user, None)
        assert 'configured public casino channel' in content(user)
        assert store.active(77, 1, KIND) is None
        channel.send.assert_not_awaited()
        cog.cog_unload()
    asyncio.run(run())


def test_resume_from_private_channel_only_edits_eligible_saved_channel(tmp_path, monkeypatch):
    async def run():
        cog, store, inter, message, channel, _ = environment(tmp_path, monkeypatch)
        try:
            snap = playing(cog, store)
            cog._public_allowed.side_effect = lambda guild, channel_id: channel_id == 88
            user = inter(2)
            user.channel_id = 99
            await cog.thrilling.callback(cog, user, snap['id'])
            message.edit.assert_awaited()
            channel.send.assert_not_awaited()
            assert store.get(snap['id'])['state']['channel_id'] == 88
        finally:
            cog.cog_unload()
    asyncio.run(run())


def test_resume_cannot_publish_into_newly_private_saved_channel(tmp_path, monkeypatch):
    async def run():
        cog, store, inter, message, channel, _ = environment(tmp_path, monkeypatch)
        snap = playing(cog, store)
        cog._public_allowed.return_value = False
        user = inter(2)
        await cog.thrilling.callback(cog, user, snap['id'])
        assert 'configured public casino channel' in content(user)
        message.edit.assert_not_awaited()
        channel.send.assert_not_awaited()
        assert store.get(snap['id'])['status'] == 'paused'
        cog.cog_unload()
    asyncio.run(run())


def test_attachment_http_failure_retries_safe_text_without_reapplying_action(tmp_path, monkeypatch):
    async def run():
        cog, store, inter, message, _, _ = environment(tmp_path, monkeypatch)
        try:
            snap = playing(cog, store)
            response = SimpleNamespace(status=413, reason='Payload Too Large')
            message.edit.side_effect = [discord.HTTPException(response, 'attachment rejected'), None]
            await cog.handle(inter(1), snap['id'], snap['revision'], 'open', 3)
            saved = store.get(snap['id'])
            hand = ThrillingMatch.from_dict(saved['state']['match']).hand
            assert saved['status'] == 'active' and hand.revision == 1 and hand.target == 3
            assert message.edit.await_count == 2
            retry = message.edit.call_args.kwargs
            assert retry['attachments'] == []
            assert 'AS' not in retry['content'] and 'KH' not in retry['content']
            assert snap['id'] in cog.deadlines
        finally:
            cog.cog_unload()
    asyncio.run(run())


def test_forbidden_publication_does_not_retry_or_expose_text(tmp_path, monkeypatch):
    async def run():
        cog, store, inter, message, _, _ = environment(tmp_path, monkeypatch)
        snap = playing(cog, store)
        response = SimpleNamespace(status=403, reason='Forbidden')
        message.edit.side_effect = discord.Forbidden(response, 'cannot publish')
        await cog.handle(inter(1), snap['id'], snap['revision'], 'open', 3)
        assert message.edit.await_count == 1
        assert store.get(snap['id'])['status'] == 'paused'
        cog.cog_unload()
    asyncio.run(run())
