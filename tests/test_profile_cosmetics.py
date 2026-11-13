"""Equipped profile artwork remains optional and preserves existing visibility."""
import asyncio
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest


def setup(monkeypatch, *, equipped=True, animations=False):
    import pymongo
    monkeypatch.setattr(pymongo,'MongoClient',MagicMock())
    import cogs.user_cog as module
    from cosmetics import profile
    record={'_id':'legacy','user_id':42,'balance':75,'games_played':9,'career_stars_total':4,
            'animations_enabled':animations,'private_email':'do-not-render','blackjack_round':{'secret':'do-not-render'}}
    if equipped:
        record['cosmetics']={'schema_version':1,'revision':2,'owned':['frame_silver','effect_sparkle'],
                             'equipped':{'profile_frame':'frame_silver','profile_effect':'effect_sparkle'},'receipts':{}}
    monkeypatch.setattr(module.EconomyManager,'ensure_user',lambda *a:record)
    monkeypatch.setattr(module.MetricsManager,'record_command_event',lambda *a:None)
    monkeypatch.setattr(module,'resolve_command_visibility',lambda *a:SimpleNamespace(ephemeral=True))
    calls=[]
    def render(public,appearance,animate=False):
        calls.append((public,appearance,animate))
        return BytesIO(b'GIF89a' if animate else b'\x89PNG')
    monkeypatch.setattr(profile,'render_profile',render)
    inter=SimpleNamespace(user=SimpleNamespace(id=42,name='player',display_name='Player',display_avatar=SimpleNamespace(url='https://example.com/avatar.png')),
                          response=SimpleNamespace(defer=AsyncMock()),followup=SimpleNamespace(send=AsyncMock()))
    return module,module.UserCog(SimpleNamespace()),inter,calls,profile


@pytest.mark.parametrize('animations,expected',[(False,False),(True,True),(None,True)])
def test_profile_renders_only_public_fields_and_respects_animation_preference(monkeypatch,animations,expected):
    async def run():
        _,cog,inter,calls,_=setup(monkeypatch,animations=animations)
        await cog.profile.callback(cog,inter)
        public,look,animate=calls[0]
        assert public=={'name':'Player','balance':75,'games_played':9,'career_stars':4}
        assert look.profile_frame=='silver' and animate==expected
        sent=inter.followup.send.call_args.kwargs
        assert sent['ephemeral'] and len(sent['embed'].fields)==7
        assert sent['files'][0].filename==('profile.gif' if expected else 'profile.png')
        assert sent['embed'].image.url=='attachment://'+sent['files'][0].filename
    asyncio.run(run())


def test_default_profile_keeps_existing_embed_without_new_art(monkeypatch):
    async def run():
        _,cog,inter,calls,_=setup(monkeypatch,equipped=False)
        await cog.profile.callback(cog,inter)
        assert not calls and not inter.followup.send.call_args.kwargs['files']
    asyncio.run(run())


def test_render_failure_preserves_profile_statistics(monkeypatch):
    async def run():
        _,cog,inter,_,profile=setup(monkeypatch)
        monkeypatch.setattr(profile,'render_profile',lambda *a,**k:(_ for _ in ()).throw(RuntimeError('image failed')))
        await cog.profile.callback(cog,inter)
        assert len(inter.followup.send.call_args.kwargs['embed'].fields)==7
        assert not inter.followup.send.call_args.kwargs['files']
    asyncio.run(run())


def test_upload_failure_retries_same_profile_without_attachment(monkeypatch):
    async def run():
        _,cog,inter,_,_=setup(monkeypatch)
        inter.followup.send.side_effect=[discord.HTTPException(SimpleNamespace(status=413,reason='too large'),'upload failed'),None]
        await cog.profile.callback(cog,inter)
        assert inter.followup.send.await_count==2
        sent=inter.followup.send.call_args.kwargs
        assert 'files' not in sent and not sent['embed'].image.url
        assert sent['ephemeral'] and len(sent['embed'].fields)==7
    asyncio.run(run())
