"""Cosmetics UI transactions are mocked; no live Discord or economy database."""
import asyncio
from copy import deepcopy
from dataclasses import dataclass, replace
from io import BytesIO
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import discord
import pytest

from cogs.cosmetics_cog import CosmeticsCog, CosmeticsView


@dataclass(frozen=True)
class Appearance:
    deck: str='mario'
    dealer: str='luigi'
    felt: str='classic'
    profile_frame: str='none'
    profile_effect: str='none'


@dataclass(frozen=True)
class Item:
    id: str
    name: str
    slot: str
    asset_key: str


@dataclass(frozen=True)
class Offer:
    id: str
    name: str
    item_ids: tuple
    price: int

    @property
    def quote_id(self):return f'{self.id}:{self.price}:{self.item_ids}'


class Store:
    def __init__(self,catalog,offers):
        from cosmetics.catalog import CosmeticCatalog
        self.catalog=CosmeticCatalog(catalog,offers)
        self.items,self.offers=self.catalog.items,self.catalog.offers
        self.data={'user_id':42,'balance':100,'revision':0,'owned':['felt_classic'],'equipped':{'felt':'felt_classic'},
                   'appearance':Appearance(),'animations_enabled':False,
                   'profile':{'name':'Player','balance':100,'games_played':7,'career_stars':3}}
        self.requests={};self.gets=0;self.purchases=[];self.equips=[]

    def get(self,uid,username):
        assert uid==42
        self.gets+=1
        return deepcopy(self.data)

    def purchase(self,uid,offer_id,quote_id,request_id,username):
        assert uid==42
        self.purchases.append((offer_id,quote_id,request_id))
        if request_id in self.requests:
            assert self.requests[request_id]==(offer_id,quote_id)
            return {'status':'replayed','snapshot':deepcopy(self.data)}
        offer=self.offers[offer_id]
        if quote_id != offer.quote_id:raise ValueError('The offer changed. Preview the current price again.')
        if all(i in self.data['owned'] for i in offer.item_ids):
            return {'status':'already_owned','snapshot':deepcopy(self.data)}
        if self.data['balance']<offer.price:raise ValueError('Not enough coins.')
        self.data['balance']-=offer.price
        self.data['owned']=sorted(set(self.data['owned'])|set(offer.item_ids))
        self.data['revision']+=1
        self.requests[request_id]=(offer_id,quote_id)
        return {'status':'purchased','snapshot':deepcopy(self.data)}

    def equip(self,uid,item_id,revision,username):
        assert uid==42
        self.equips.append((item_id,revision))
        if revision != self.data['revision']:return deepcopy(self.data),False
        if item_id not in self.data['owned']:raise ValueError('Item is not owned.')
        item=self.items[item_id]
        self.data['equipped'][item.slot]=item.id
        self.data['appearance']=replace(self.data['appearance'],**{item.slot:item.asset_key})
        self.data['revision']+=1
        return deepcopy(self.data),True


def environment(monkeypatch, *, price=25, extra=0):
    catalog={'felt_classic':Item('felt_classic','Classic felt','felt','classic'),
             'felt_rose':Item('felt_rose','Rose felt','felt','rose')}
    offers={'starter_style':Offer('starter_style','Starter style',('felt_rose',),price)}
    for i in range(extra):
        catalog[f'felt_{i}']=Item(f'felt_{i}',f'Felt {i}','felt',f'color{i}')
        offers[f'offer_{i}']=Offer(f'offer_{i}',f'Offer {i}',(f'felt_{i}',),0)
    store=Store(catalog,offers)
    cog=CosmeticsCog(SimpleNamespace(),store=store)
    renders=[]
    def render(public,appearance,**options):
        renders.append((deepcopy(public),appearance,options))
        return BytesIO(b'\x89PNG\r\n')
    monkeypatch.setitem(sys.modules,'cosmetics.profile',SimpleNamespace(render_profile=render))
    def interaction(uid=42,guild=77):
        return SimpleNamespace(user=SimpleNamespace(id=uid,display_name='Player'),guild_id=guild,data={'values':['starter_style']},
            response=SimpleNamespace(defer=AsyncMock(),send_message=AsyncMock()),followup=SimpleNamespace(send=AsyncMock()),
            edit_original_response=AsyncMock())
    return cog,store,interaction,renders


def current(inter):return inter.edit_original_response.call_args.kwargs['view']


def button(view,label):return next(c for c in view.children if isinstance(c,discord.ui.Button) and c.label==label)


@pytest.mark.parametrize('mode',['shop','wardrobe'])
def test_browse_is_private_and_never_spends_or_equips(monkeypatch,mode):
    async def run():
        cog,store,interaction,renders=environment(monkeypatch)
        initial=deepcopy(store.data)
        inter=interaction()
        await getattr(cog,mode).callback(cog,inter)
        inter.response.defer.assert_awaited_once_with(ephemeral=True,thinking=True)
        assert store.data==initial and not store.purchases and not store.equips
        assert renders[-1][0]['games_played']==7
        assert renders[-1][2]['animate'] is False
    asyncio.run(run())


def test_paid_offer_preview_then_duplicate_confirmation_charges_exactly_once(monkeypatch):
    async def run():
        cog,store,interaction,renders=environment(monkeypatch)
        first=interaction();await cog.open(first,'shop')
        select=next(c for c in current(first).children if isinstance(c,discord.ui.Select))
        preview=interaction();await select.callback(preview)
        view=current(preview)
        assert store.data['balance']==100 and store.data['appearance'].felt=='classic'
        assert renders[-1][1].felt=='rose'
        assert '25 coins' in preview.edit_original_response.call_args.kwargs['content']
        confirm=button(view,'Confirm purchase · 25 coins')
        await asyncio.gather(confirm.callback(interaction()),confirm.callback(interaction()))
        assert store.data['balance']==75 and store.data['owned']==['felt_classic','felt_rose']
        assert len(store.requests)==1 and len({p[2] for p in store.purchases})==1
        assert store.data['appearance'].felt=='classic'  # Buying does not silently equip.
        reopened=interaction();await cog.open(reopened,'shop')
        await cog.handle(reopened,current(reopened),'select',selection='starter_style')
        assert not any(isinstance(c,discord.ui.Button) and 'Confirm' in c.label for c in current(reopened).children)
    asyncio.run(run())


@pytest.mark.parametrize('uid,guild',[(99,77),(42,88)])
def test_wrong_user_or_guild_cannot_purchase_or_read_saved_state(monkeypatch,uid,guild):
    async def run():
        cog,store,interaction,_=environment(monkeypatch)
        view=CosmeticsView(cog,77,store.get(42,'Player'),'shop',selected='starter_style')
        initial_gets=store.gets
        inter=interaction(uid,guild)
        await button(view,'Confirm purchase · 25 coins').callback(inter)
        inter.response.send_message.assert_awaited_once()
        assert not inter.response.defer.called and not store.purchases and store.gets==initial_gets
    asyncio.run(run())


def test_stale_equip_refreshes_without_overwriting_and_reopen_uses_saved_choice(monkeypatch):
    async def run():
        cog,store,interaction,_=environment(monkeypatch)
        store.data['owned'].append('felt_rose')
        stale=CosmeticsView(cog,77,store.get(42,'Player'),'wardrobe',selected='felt_rose')
        store.data['revision']+=1
        inter=interaction();await cog.handle(inter,stale,'equip')
        assert store.data['appearance'].felt=='classic'
        assert 'stale' in inter.edit_original_response.call_args.kwargs['content']
        fresh=current(inter);await cog.handle(inter,fresh,'equip')
        assert store.data['appearance'].felt=='rose'
        rebuilt=CosmeticsCog(SimpleNamespace(),store=store)
        reopened=interaction();await rebuilt.open(reopened,'wardrobe')
        assert current(reopened).snapshot['equipped']['felt']=='felt_rose'
        assert store.data['balance']==100
    asyncio.run(run())


def test_changed_price_cannot_use_old_confirmation_quote(monkeypatch):
    async def run():
        cog,store,interaction,_=environment(monkeypatch)
        view=CosmeticsView(cog,77,store.get(42,'Player'),'shop',selected='starter_style')
        cog.offers['starter_style']=replace(cog.offers['starter_style'],price=40)
        inter=interaction();await cog.handle(inter,view,'purchase')
        assert store.data['balance']==100 and len(store.requests)==0
        assert 'offer changed' in inter.followup.send.call_args.args[0]
    asyncio.run(run())


@pytest.mark.parametrize('mode',['shop','wardrobe'])
def test_twenty_five_option_paging_preserves_all_entries(monkeypatch,mode):
    async def run():
        cog,store,interaction,_=environment(monkeypatch,extra=31)
        store.data['owned']=list(cog.catalog)
        inter=interaction();await cog.open(inter,mode)
        first=current(inter)
        select=next(c for c in first.children if isinstance(c,discord.ui.Select))
        assert len(select.options)==25
        await button(first,'Next').callback(inter)
        second=current(inter)
        select2=next(c for c in second.children if isinstance(c,discord.ui.Select))
        assert 0<len(select2.options)<=25
        expected=set(cog.catalog if mode=='wardrobe' else cog.offers)
        assert {o.value for o in select.options}|{o.value for o in select2.options}==expected
        assert second.selected is None and not store.purchases and not store.equips
    asyncio.run(run())


def test_renderer_failure_keeps_saved_purchase_and_text_controls(monkeypatch):
    async def run():
        cog,store,interaction,_=environment(monkeypatch)
        def broken(*a,**k):raise RuntimeError('bad image')
        monkeypatch.setitem(sys.modules,'cosmetics.profile',SimpleNamespace(render_profile=broken))
        view=CosmeticsView(cog,77,store.get(42,'Player'),'shop',selected='starter_style')
        inter=interaction();await cog.handle(inter,view,'purchase')
        assert store.data['balance']==75
        payload=inter.edit_original_response.call_args.kwargs
        assert payload['attachments']==[] and 'Purchase saved' in payload['content']
    asyncio.run(run())


def test_upload_failure_retries_same_text_and_permanent_failure_cannot_recharge(monkeypatch):
    async def run():
        cog,store,interaction,_=environment(monkeypatch)
        view=CosmeticsView(cog,77,store.get(42,'Player'),'shop',selected='starter_style')
        inter=interaction()
        response=SimpleNamespace(status=400,reason='Bad Request')
        inter.edit_original_response.side_effect=[discord.HTTPException(response,'bad upload'),None]
        await cog.handle(inter,view,'purchase')
        calls=inter.edit_original_response.call_args_list
        assert len(calls)==2 and calls[0].kwargs['content']==calls[1].kwargs['content']
        assert calls[1].kwargs['attachments']==[] and store.data['balance']==75
        retry=interaction();retry.edit_original_response.side_effect=RuntimeError('delivery offline')
        await cog.handle(retry,view,'purchase')
        assert store.data['balance']==75 and len(store.requests)==1
        assert retry.followup.send.called
        await cog.handle(interaction(),view,'purchase')
        assert store.data['balance']==75
    asyncio.run(run())


def test_unowned_item_and_forged_select_are_rejected_without_mutation(monkeypatch):
    async def run():
        cog,store,interaction,_=environment(monkeypatch)
        view=CosmeticsView(cog,77,store.get(42,'Player'),'wardrobe')
        inter=interaction();await cog.handle(inter,view,'select',selection='felt_rose')
        assert inter.followup.send.called and not store.equips
        inter=interaction();inter.data={'values':['not-a-real-id']}
        select=next(c for c in view.children if isinstance(c,discord.ui.Select))
        await select.callback(inter)
        assert inter.response.send_message.called and not store.purchases
        assert store.data['balance']==100
    asyncio.run(run())


def test_actual_catalog_store_and_renderer_claim_then_equip_survive_new_cog():
    from cosmetics.catalog import CATALOG, OFFERS, DEFAULTS
    from cosmetics.store import CosmeticsStore
    class Collection:
        def __init__(self):
            self.doc={'_id':'player42','user_id':42,'username':'Player','balance':100,'animations_enabled':False}
            self.writes=0
        def find_one(self,query):return deepcopy(self.doc)
        def find_one_and_update(self,query,update,return_document):
            for key,expected in query.items():
                value=self.doc
                exists=True
                for part in key.split('.'):
                    if not isinstance(value,dict) or part not in value:
                        value=None;exists=False;break
                    value=value[part]
                if isinstance(expected,dict):
                    if '$gte' in expected and (value is None or value<expected['$gte']):return None
                    if '$exists' in expected and exists!=expected['$exists']:return None
                elif value!=expected:return None
            self.doc.update(deepcopy(update.get('$set',{})))
            for key,value in update.get('$inc',{}).items():self.doc[key]=self.doc.get(key,0)+value
            self.writes+=1
            return deepcopy(self.doc)
    async def run():
        collection=Collection()
        cog=CosmeticsCog(SimpleNamespace(),store=CosmeticsStore(collection))
        def interaction():
            return SimpleNamespace(user=SimpleNamespace(id=42,display_name='Player'),guild_id=77,
                response=SimpleNamespace(defer=AsyncMock(),send_message=AsyncMock()),followup=SimpleNamespace(send=AsyncMock()),
                edit_original_response=AsyncMock())
        inter=interaction();await cog.open(inter,'shop')
        assert collection.writes==0
        await cog.handle(inter,current(inter),'select',selection='starter_style')
        assert collection.writes==0 and inter.edit_original_response.call_args.kwargs['attachments']
        await button(current(inter), 'Confirm free claim').callback(inter)
        assert collection.writes==1 and collection.doc['balance']==100
        assert set(current(inter).snapshot['owned'])==set(DEFAULTS.values())|set(OFFERS['starter_style'].item_ids)
        await cog.handle(inter,current(inter),'switch')
        await cog.handle(inter,current(inter),'select',selection='felt_midnight')
        await cog.handle(inter,current(inter),'equip')
        assert collection.writes==2
        reopened=CosmeticsCog(SimpleNamespace(),store=CosmeticsStore(collection))
        new_inter=interaction();await reopened.open(new_inter,'wardrobe')
        assert current(new_inter).snapshot['appearance'].felt=='midnight'
        assert collection.writes==2 and collection.doc['balance']==100
    asyncio.run(run())
