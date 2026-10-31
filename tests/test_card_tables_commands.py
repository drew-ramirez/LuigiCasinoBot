"""Offline command/interaction regressions with saved engines and no live services."""
import asyncio
import json
from copy import deepcopy
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from casinogames.session_store import SessionStore


def environment(tmp_path, monkeypatch, *, public=False):
    import pymongo
    monkeypatch.setattr(pymongo, 'MongoClient', MagicMock())
    import cogs.card_tables_cog as module
    import casinogames.duel_render as renderer
    calls=[]
    def render(kind, projection, **options):
        calls.append((kind,deepcopy(projection),deepcopy(options)))
        return BytesIO(b'\x89PNG\r\n')
    monkeypatch.setattr(renderer,'render_duel',render)
    cog=module.CardTablesCog(SimpleNamespace(),store=SessionStore(tmp_path/'tables.db'))
    cog.visible=AsyncMock(return_value=public)
    cog.animated=AsyncMock(return_value=False)
    message=SimpleNamespace(id=500,edit=AsyncMock())
    channel=SimpleNamespace(id=88,guild=SimpleNamespace(id=77),send=AsyncMock(return_value=message))
    def interaction(actor=42):
        return SimpleNamespace(user=SimpleNamespace(id=actor,bot=False),guild_id=77,guild=SimpleNamespace(id=77),channel_id=88,channel=channel,
            data={'values':['0']},response=SimpleNamespace(defer=AsyncMock(),send_message=AsyncMock(),edit_message=AsyncMock()),
            followup=SimpleNamespace(send=AsyncMock(return_value=message)),edit_original_response=AsyncMock(return_value=message))
    return module,cog,interaction,message,calls


def button(view,label):
    return next(c for c in view.children if isinstance(c,discord.ui.Button) and c.label==label)


@pytest.mark.parametrize('command,kind',[('tripletriad','triple_triad'),('red7','red7'),('scopa','scopa'),('cuttle','cuttle'),('platoon','platoon'),('pazaak','pazaak'),('war','casino_war')])
def test_all_seven_commands_deal_offline_and_render_private_projection(tmp_path,monkeypatch,command,kind):
    async def run():
        module,cog,interaction,message,calls=environment(tmp_path,monkeypatch)
        try:
            inter=interaction()
            await getattr(cog,command).callback(cog,inter,animations=False)
            inter.response.defer.assert_awaited_once()
            assert calls and calls[-1][0]==kind
            saved=cog.service.store.active(77,42,kind)
            if saved is None:  # Casino War normally settles on its first comparison.
                assert kind=='casino_war' and calls[-1][1]['result']
            else:
                assert json.loads(json.dumps(cog.service.engine(saved).to_dict()))==saved['state']['game']
                assert calls[-1][1]['hands']==cog.service.projection(saved,42)['hands']
            assert inter.edit_original_response.await_count>=1
        finally:cog.cog_unload()
    asyncio.run(run())


def test_move_selection_is_read_only_until_confirm_and_duplicate_cannot_draw_again(tmp_path,monkeypatch):
    async def run():
        module,cog,interaction,_,calls=environment(tmp_path,monkeypatch)
        try:
            saved=cog.service.start(77,42,'scopa',seed=8)
            actions=cog.service.actions(saved,42)
            view=module.CardTableView(cog,saved,42,group=actions[0]['group'])
            select=next(c for c in view.children if isinstance(c,discord.ui.Select) and c.row==1)
            inter=interaction()
            original_payload=cog.payload
            async def acknowledged_payload(*args,**kwargs):
                inter.response.defer.assert_awaited_once()
                return await original_payload(*args,**kwargs)
            cog.payload=acknowledged_payload
            await select.callback(inter)
            cog.payload=original_payload
            assert cog.service.store.get(saved['id'])==saved
            confirmed=inter.edit_original_response.call_args.kwargs['view']
            assert confirmed.choice==actions[0]['id']
            await button(confirmed,'Confirm move').callback(interaction())
            after=cog.service.store.get(saved['id'])
            assert after['revision']==saved['revision']+1
            assert after['state']['game']!=saved['state']['game']
            assert len(cog.service.engine(after).hands['42'])==2  # Exactly one human play and Luigi reply.
            await button(confirmed,'Confirm move').callback(interaction())
            assert cog.service.store.get(saved['id'])==after
        finally:cog.cog_unload()
    asyncio.run(run())


def test_groups_and_moves_paginate_to_discord_limits_without_mutation(tmp_path,monkeypatch):
    async def run():
        module,cog,interaction,_,_=environment(tmp_path,monkeypatch)
        try:
            saved=cog.service.start(77,42,'scopa',seed=2)
            actions=[{'id':f'{g}:{i}','label':f'Move {g} {i}','group':f'Card {g}'} for g in range(31) for i in range(61)]
            monkeypatch.setattr(cog.service,'actions',lambda *a:actions)
            view=module.CardTableView(cog,saved,42,group='Card 0')
            assert all(len(c.options)<=25 for c in view.children if isinstance(c,discord.ui.Select))
            inter=interaction();await button(view,'More moves').callback(inter)
            second=inter.edit_original_response.call_args.kwargs['view']
            assert second.page==1
            assert len(next(c for c in second.children if isinstance(c,discord.ui.Select) and c.row==1).options)==25
            inter=interaction();await button(view,'More cards').callback(inter)
            second=inter.edit_original_response.call_args.kwargs['view']
            assert len(next(c for c in second.children if isinstance(c,discord.ui.Select) and c.row==0).options)==6
            assert second.group is None and second.page==0 and second.choice is None
            assert cog.service.store.get(saved['id'])==saved
        finally:cog.cog_unload()
    asyncio.run(run())


def test_private_owner_check_and_spectator_cannot_mutate_or_obtain_hand(tmp_path,monkeypatch):
    async def run():
        module,cog,interaction,_,_=environment(tmp_path,monkeypatch)
        try:
            saved=cog.service.start(77,42,'cuttle',seed=4)
            private=module.CardTableView(cog,saved,42)
            intruder=interaction(99)
            await private.dispatch(intruder,'private')
            intruder.response.send_message.assert_awaited_once()
            assert not intruder.edit_original_response.called
            await cog.handle(interaction(99),saved,'confirm',choice='draw')
            assert cog.service.store.get(saved['id'])==saved
            public=await cog.payload(saved)
            for card in saved['state']['game']['hands']['42']:
                assert card not in public['content']
            assert all(c is None for h in cog.service.projection(saved)['hands'].values() for c in h)
        finally:cog.cog_unload()
    asyncio.run(run())


def test_human_invitation_requires_public_channel_and_explicit_opponent_acceptance(tmp_path,monkeypatch):
    async def run():
        module,cog,interaction,_,calls=environment(tmp_path,monkeypatch)
        try:
            opponent=SimpleNamespace(id=43,bot=False)
            await cog.start(interaction(),'scopa',opponent,animations=False)
            assert cog.service.store.active(77,42,'scopa') is None
            cog.visible.return_value=True
            await cog.start(interaction(),'scopa',opponent,animations=False)
            invited=cog.service.store.active(77,42,'scopa')
            assert invited['state']['game'] is None and invited['state']['phase']=='invited'
            await cog.handle(interaction(42),invited,'accept')
            assert cog.service.store.get(invited['id'])==invited
            await cog.handle(interaction(43),invited,'accept')
            dealt=cog.service.store.get(invited['id'])
            assert dealt['state']['game'] is not None
            public_views=[p for _,p,_ in calls if all(c is None for h in p['hands'].values() for c in h)]
            assert public_views and public_views[-1]['hands']['42']==[None]*3
        finally:cog.cog_unload()
    asyncio.run(run())


def test_restart_resume_preserves_deck_and_old_timeout_cannot_pause_new_revision(tmp_path,monkeypatch):
    async def run():
        module,cog,interaction,_,_=environment(tmp_path,monkeypatch)
        try:
            saved=cog.service.start(77,42,'cuttle',seed=17)
            paused,_=cog.service.change(saved['id'],saved['revision'],42,'pause',guild=77)
            cog.service=module.DuelService(SessionStore(tmp_path/'tables.db'),module.engines())
            await cog.start(interaction(),'cuttle',table=saved['id'],animations=False)
            resumed=cog.service.store.get(saved['id'])
            assert resumed['status']=='active' and resumed['state']['game']==paused['state']['game']
            await cog.expire(saved['id'],saved['revision'],0)
            assert cog.service.store.get(saved['id'])==resumed
            await cog.expire(saved['id'],resumed['revision'],0)
            current=cog.service.store.get(saved['id'])
            assert current['status']=='paused' and current['state']['game']==resumed['state']['game']
        finally:cog.cog_unload()
    asyncio.run(run())


def test_render_and_upload_failures_use_same_saved_state(tmp_path,monkeypatch):
    async def run():
        module,cog,interaction,_,_=environment(tmp_path,monkeypatch)
        import casinogames.duel_render as renderer
        try:
            saved=cog.service.start(77,42,'scopa',seed=2)
            def fail(*a,**k):raise RuntimeError('renderer unavailable')
            monkeypatch.setattr(renderer,'render_duel',fail)
            payload=await cog.payload(saved,42)
            assert payload['attachments']==[] and 'Scopa' in payload['content']
            assert cog.service.store.get(saved['id'])==saved
            payload['attachments']=[discord.File(BytesIO(b'png'),filename='table.png')]
            response=SimpleNamespace(status=400,reason='Bad Request')
            send=AsyncMock(side_effect=[discord.HTTPException(response,'upload failed'),'sent'])
            assert await cog._send(send,payload)=='sent'
            first,second=[call.kwargs for call in send.call_args_list]
            assert first['content']==second['content'] and second['attachments']==[]
            assert cog.service.store.get(saved['id'])==saved
        finally:cog.cog_unload()
    asyncio.run(run())



def test_concession_final_projection_has_no_live_turn_or_move_controls(tmp_path,monkeypatch):
    async def run():
        module,cog,interaction,_,_=environment(tmp_path,monkeypatch)
        try:
            saved=cog.service.start(77,42,'cuttle',seed=8)
            await cog.handle(interaction(),saved,'concede',viewer=42)
            ended=cog.service.store.get(saved['id'])
            projection=cog.service.projection(ended,42)
            assert projection['phase']=='finished' and projection['turn'] is None
            assert projection['result']['winner']==0
            assert cog.service.frames(ended,42)[-1]['result']==projection['result']
            assert cog.service.actions(ended,42)==[]
            assert len(cog.service.store.records(77,42,'cuttle'))==1
        finally:cog.cog_unload()
    asyncio.run(run())


def test_simultaneous_confirms_commit_one_player_move_and_one_bot_reply(tmp_path,monkeypatch):
    async def run():
        module,cog,interaction,_,_=environment(tmp_path,monkeypatch)
        try:
            saved=cog.service.start(77,42,'scopa',seed=23)
            action=cog.service.actions(saved,42)[0]['id']
            await asyncio.gather(*(cog.handle(interaction(),saved,'confirm',viewer=42,choice=action) for _ in range(2)))
            latest=cog.service.store.get(saved['id'])
            assert latest['revision']==saved['revision']+1
            assert len(cog.service.engine(latest).hands['42'])==2
            assert len(cog.service.engine(latest).hands['0'])==2
        finally:cog.cog_unload()
    asyncio.run(run())


def test_delivery_failure_after_move_pauses_exact_committed_state(tmp_path,monkeypatch):
    async def run():
        module,cog,interaction,_,_=environment(tmp_path,monkeypatch)
        try:
            saved=cog.service.start(77,42,'scopa',seed=23)
            action=cog.service.actions(saved,42)[0]['id']
            expected=cog.service.engine(saved)
            expected.act(42,action);expected.act(0,expected.bot_action())
            cog.private_message=AsyncMock(side_effect=RuntimeError('delivery unavailable'))
            await cog.handle(interaction(),saved,'confirm',viewer=42,choice=action)
            paused=cog.service.store.get(saved['id'])
            assert paused['status']=='paused' and paused['state']['game']==expected.to_dict()
            assert paused['revision']==saved['revision']+2
        finally:cog.cog_unload()
    asyncio.run(run())


def test_initial_delivery_failure_preserves_paused_deal_for_reopening(tmp_path,monkeypatch):
    async def run():
        module,cog,interaction,_,_=environment(tmp_path,monkeypatch)
        try:
            cog.private_message=AsyncMock(side_effect=RuntimeError('delivery unavailable'))
            await cog.start(interaction(),'scopa',animations=False)
            saved=cog.service.store.active(77,42,'scopa')
            assert saved and saved['status']=='paused'
            assert saved['state']['game'] and len(saved['state']['game']['hands']['42'])==3
        finally:cog.cog_unload()
    asyncio.run(run())




def test_spectator_refresh_stays_public_and_never_opens_private_hand(tmp_path,monkeypatch):
    async def run():
        module,cog,interaction,_,calls=environment(tmp_path,monkeypatch,public=True)
        try:
            await cog.start(interaction(),'cuttle',animations=False)
            saved=cog.service.store.active(77,42,'cuttle')
            calls.clear()
            spectator=interaction(99)
            await cog.handle(spectator,saved,'refresh')
            assert calls and all(all(card is None for hand in p['hands'].values() for card in hand) for _,p,_ in calls)
            assert not spectator.edit_original_response.called
            assert cog.service.store.get(saved['id'])==saved
        finally:cog.cog_unload()
    asyncio.run(run())


def test_animated_reply_uses_every_safe_trace_frame(tmp_path, monkeypatch):
    async def run():
        _, cog, _, _, _ = environment(tmp_path, monkeypatch)
        import casinogames.duel_render as renderer
        sequences = []
        def render(kind, frames):
            sequences.append((kind, deepcopy(frames)))
            return BytesIO(b'GIF89a')
        monkeypatch.setattr(renderer, 'render_sequence', render)
        saved = cog.service.start(77, 42, 'scopa', seed=23)
        saved, _ = cog.service.change(saved['id'], saved['revision'], 42, 'play', guild=77,
                                      choice=cog.service.actions(saved, 42)[0]['id'])
        payload = await cog.payload(saved, animate=True, transition=True)
        assert payload['attachments'][0].filename == 'table.gif'
        assert len(sequences[0][1]) == 3
        for frame in sequences[0][1]:
            assert frame['viewer_id'] is None
            assert all(card is None for hand in frame['hands'].values() for card in hand)
        assert sequences[0][1][-1] == cog.service.projection(saved)
        cog.cog_unload()
    asyncio.run(run())


def test_immediately_finished_war_honors_animation_override(tmp_path, monkeypatch):
    async def run():
        _, cog, interaction, _, calls = environment(tmp_path, monkeypatch)
        saved = cog.service.start(77, 42, 'casino_war', seed=0)
        assert saved['status'] == 'finished'
        await cog.start(interaction(), 'casino_war', table=saved['id'], animations=True)
        assert calls[-1][2]['animate'] is True
        assert cog.service.store.get(saved['id']) == saved
        cog.cog_unload()
    asyncio.run(run())
