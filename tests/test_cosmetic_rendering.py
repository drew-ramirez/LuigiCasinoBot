"""Appearance isolation, safe previews, and real duel-table integration offline."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import FrozenInstanceError
from io import BytesIO
import logging
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import AsyncMock

from PIL import Image, ImageChops
import pytest

from casinogames.casino_art import background, sprite
from cosmetics.catalog import Appearance
from cosmetics.profile import render_profile
from cosmetics.rendering import current_appearance, run_with_appearance

PUBLIC = {'name':'Luigi Fan', 'balance':12345, 'games_played':123, 'career_stars':45}


def test_classic_background_is_unchanged_and_alternate_felts_never_mutate_source():
    source=sprite('felt').tobytes()
    expected=sprite('felt').resize((256,192),Image.Resampling.NEAREST)
    assert background((256,192)).tobytes()==expected.tobytes()
    for theme in ('midnight','rose'):
        image=run_with_appearance(Appearance(felt=theme),background,(256,192))
        assert image.size==expected.size and image.mode=='RGBA'
        assert image.tobytes()!=expected.tobytes()
        assert image.getchannel('A').tobytes()==expected.getchannel('A').tobytes()
        assert len(image.getcolors(256*192))>30  # The texture is not a flat fill.
        image.paste('black',(0,0,256,192))
        again=run_with_appearance(Appearance(felt=theme),background,(256,192))
        assert again.getpixel((128,96))!=(0,0,0,255)
    assert sprite('felt').tobytes()==source
    assert background((256,192)).tobytes()==expected.tobytes()
    assert run_with_appearance(Appearance(felt='missing'),background,(256,192)).tobytes()==expected.tobytes()


def test_nested_context_restores_after_failure_and_appearance_is_frozen():
    classic=Appearance();midnight=Appearance(felt='midnight')
    with pytest.raises(FrozenInstanceError): midnight.felt='rose'
    def inner():
        assert current_appearance().felt=='rose'
        raise RuntimeError('render failed')
    def outer():
        assert current_appearance()==midnight
        with pytest.raises(RuntimeError):run_with_appearance(Appearance(felt='rose'),inner)
        assert current_appearance()==midnight
    run_with_appearance(midnight,outer)
    assert current_appearance()==classic
    with pytest.raises(TypeError):run_with_appearance({'felt':'rose'},lambda:None)
    assert current_appearance()==classic


def test_two_simultaneous_render_threads_keep_their_own_theme():
    barrier=Barrier(2)
    def render():
        selected=current_appearance()
        barrier.wait(timeout=5)
        pixels=background((32,24)).tobytes()
        barrier.wait(timeout=5)
        assert current_appearance()==selected
        return selected,pixels
    with ThreadPoolExecutor(max_workers=2) as executor:
        first=executor.submit(run_with_appearance,Appearance(felt='midnight'),render)
        second=executor.submit(run_with_appearance,Appearance(felt='rose'),render)
        a,b=first.result(),second.result()
    assert a[0].felt=='midnight' and b[0].felt=='rose' and a[1]!=b[1]
    assert current_appearance()==Appearance()


@pytest.mark.parametrize('theme',['classic','midnight','rose'])
def test_profile_png_uses_only_explicit_public_fields_and_preserves_context(theme):
    appearance=Appearance(felt=theme,profile_frame='silver')
    public=deepcopy(PUBLIC);before=deepcopy(public)
    expected=render_profile(public,appearance).getvalue()
    assert public==before
    public.update(deck=['SECRET'],user_id=123,cosmetics={'SECRET':'PRIVATE'},password='DO_NOT_RENDER')
    assert render_profile(public,appearance).getvalue()==expected
    assert b'SECRET' not in expected and b'DO_NOT_RENDER' not in expected
    with Image.open(BytesIO(expected)) as image:
        assert image.format=='PNG' and image.size==(512,320)
    assert current_appearance()==Appearance()


def test_silver_frame_is_visible_without_changing_public_statistics():
    with Image.open(render_profile(PUBLIC,Appearance())) as original:
        normal=original.convert('RGB')
    with Image.open(render_profile(PUBLIC,Appearance(profile_frame='silver'))) as original:
        framed=original.convert('RGB')
    assert ImageChops.difference(normal,framed).getbbox() is not None
    assert ImageChops.difference(normal.crop((24,32,484,292)),framed.crop((24,32,484,292))).getbbox() is None


def test_profile_sparkles_move_but_static_preference_always_emits_png():
    appearance=Appearance(felt='midnight',profile_frame='silver',profile_effect='sparkle')
    with Image.open(render_profile(PUBLIC,appearance,animate=False)) as image:
        assert image.format=='PNG'
    with Image.open(render_profile(PUBLIC,appearance,animate=True)) as image:
        assert image.format=='GIF' and image.n_frames>=6 and image.info['loop']==0
        first=image.convert('RGB');image.seek(2);later=image.convert('RGB')
        assert ImageChops.difference(first,later).getbbox() is not None
    with Image.open(render_profile(PUBLIC,Appearance(),animate=True)) as image:
        assert image.format=='PNG'  # No unowned effect is synthesized.
    assert current_appearance()==Appearance()


def _cog(tmp_path,cosmetics=None):
    from casinogames.session_store import SessionStore
    from cogs.card_tables_cog import CardTablesCog
    return CardTablesCog(SimpleNamespace(),store=SessionStore(tmp_path/'cosmetic-tables.db'),cosmetics=cosmetics)


def test_duel_public_uses_host_and_private_uses_viewer_without_exposing_hands(tmp_path,monkeypatch):
    import casinogames.duel_render as renderer
    calls=[];lookups=[]
    def lookup(player):
        lookups.append(player)
        return Appearance(felt='midnight' if player==11 else 'rose')
    def render(kind,public,**kwargs):
        calls.append((current_appearance(),deepcopy(public)))
        return BytesIO(b'PNG')
    monkeypatch.setattr(renderer,'render_duel',render)
    async def run():
        cog=_cog(tmp_path,SimpleNamespace(appearance_for=lookup))
        try:
            saved=cog.service.start(77,11,'scopa',opponent=22,seed=8)
            saved,_=cog.service.change(saved['id'],saved['revision'],22,'accept',guild=77)
            await asyncio.gather(cog.payload(saved),cog.payload(saved,22))
            public=next(row for row in calls if row[1]['viewer_id'] is None)
            private=next(row for row in calls if row[1]['viewer_id']==22)
            assert public[0].felt=='midnight' and private[0].felt=='rose'
            assert all(card is None for hand in public[1]['hands'].values() for card in hand)
            assert all(card is None for card in private[1]['hands']['11'])
            assert all(card is not None for card in private[1]['hands']['22'])
            assert sorted(lookups)==[11,22]
        finally:cog.cog_unload()
    asyncio.run(run())
    assert current_appearance()==Appearance()


@pytest.mark.parametrize('lookup',['raises','malformed','none'])
def test_duel_lookup_failure_keeps_classic_image_and_saved_state(tmp_path,monkeypatch,caplog,lookup):
    import casinogames.duel_render as renderer
    seen=[]
    def resolve(_player):
        if lookup=='raises':raise RuntimeError('lookup unavailable')
        return {'felt':'rose'}
    def render(*args,**kwargs):
        seen.append(current_appearance())
        return BytesIO(b'PNG')
    monkeypatch.setattr(renderer,'render_duel',render)
    async def run():
        cog=_cog(tmp_path,None if lookup=='none' else SimpleNamespace(appearance_for=resolve))
        try:
            saved=cog.service.start(77,11,'scopa',seed=8);before=deepcopy(saved)
            payload=await cog.payload(saved,11)
            assert payload['attachments'] and saved==before
            assert cog.service.store.get(saved['id'])==before
        finally:cog.cog_unload()
    with caplog.at_level(logging.WARNING):asyncio.run(run())
    assert seen==[Appearance()]
    if lookup!='none':assert 'cosmetics unavailable' in caplog.text


def test_duel_sequence_renders_every_frame_under_same_appearance(tmp_path,monkeypatch):
    import casinogames.duel_render as renderer
    seen=[]
    def render(kind,history):
        seen.append((current_appearance(),deepcopy(history)))
        return BytesIO(b'GIF89a')
    monkeypatch.setattr(renderer,'render_sequence',render)
    async def run():
        cog=_cog(tmp_path,SimpleNamespace(appearance_for=lambda _:Appearance(felt='rose')))
        try:
            saved=cog.service.start(77,11,'scopa',seed=8)
            action=cog.service.actions(saved,11)[0]['id']
            saved,_=cog.service.change(saved['id'],saved['revision'],11,'play',guild=77,choice=action)
            result=await cog.payload(saved,11,animate=True,transition=True)
            assert result['attachments'][0].filename=='table.gif'
        finally:cog.cog_unload()
    asyncio.run(run())
    assert seen[0][0].felt=='rose' and len(seen[0][1])>1
    assert all(frame['viewer_id']==11 for frame in seen[0][1])
    assert current_appearance()==Appearance()


def test_animation_preference_failure_is_static_and_does_not_read_database(tmp_path,monkeypatch,caplog):
    import sys
    def fail(_player):raise RuntimeError('preference unavailable')
    monkeypatch.setitem(sys.modules,'economy.EconomyManager',SimpleNamespace(EconomyManager=SimpleNamespace(animations_enabled=fail)))
    async def run():
        cog=_cog(tmp_path)
        try:assert await cog.animated(11) is False
        finally:cog.cog_unload()
    with caplog.at_level(logging.WARNING):asyncio.run(run())
    assert 'preference unavailable' in caplog.text


def test_production_setup_injects_store_and_failed_setup_preserves_games(tmp_path,monkeypatch,caplog):
    import cogs.card_tables_cog as module
    import cosmetics.store as store
    service=SimpleNamespace(appearance_for=lambda _:Appearance())
    monkeypatch.setenv('CASINO_SESSION_DB',str(tmp_path/'setup.db'))
    monkeypatch.setattr(store,'CosmeticsStore',lambda:service)
    async def run():
        bot=SimpleNamespace(add_cog=AsyncMock())
        await module.setup(bot)
        cog=bot.add_cog.call_args.args[0]
        assert cog.cosmetics is service
        cog.cog_unload()
        def fail():raise RuntimeError('store unavailable')
        monkeypatch.setattr(store,'CosmeticsStore',fail)
        await module.setup(bot)
        cog=bot.add_cog.call_args.args[0]
        assert cog.cosmetics is None
        cog.cog_unload()
    with caplog.at_level(logging.WARNING):asyncio.run(run())
    assert 'cosmetics setup unavailable' in caplog.text
