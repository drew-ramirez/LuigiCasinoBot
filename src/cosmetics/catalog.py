"""Server-owned cosmetic IDs and fixed bundles; no user-supplied asset paths."""
from dataclasses import dataclass
from hashlib import sha256
import json
import re
from types import MappingProxyType

SLOTS=('deck','dealer','felt','profile_frame','profile_effect')
ID_PATTERN=re.compile(r'^[a-z][a-z0-9_]{0,63}$')


@dataclass(frozen=True)
class Appearance:
    deck: str = 'mario'
    dealer: str = 'luigi'
    felt: str = 'classic'
    profile_frame: str = 'none'
    profile_effect: str = 'none'


@dataclass(frozen=True)
class Item:
    id: str
    name: str
    slot: str
    asset_key: str

    def __post_init__(self):
        if not ID_PATTERN.fullmatch(self.id) or self.slot not in SLOTS:
            raise ValueError('Invalid cosmetic identity or slot')
        if not ID_PATTERN.fullmatch(self.asset_key) or not self.name or len(self.name)>80:
            raise ValueError('Invalid cosmetic presentation')


@dataclass(frozen=True)
class Offer:
    id: str
    name: str
    item_ids: tuple[str, ...]
    price: int
    version: int = 1

    def __post_init__(self):
        if not ID_PATTERN.fullmatch(self.id) or not self.name or len(self.name)>80:
            raise ValueError('Invalid offer identity')
        if type(self.price) is not int or self.price<0 or type(self.version) is not int or self.version<1:
            raise ValueError('Offer price/version must be nonnegative/positive integers')
        if not isinstance(self.item_ids,tuple) or not self.item_ids or len(set(self.item_ids))!=len(self.item_ids):
            raise ValueError('Offers need unique, fixed item IDs')

    @property
    def quote_id(self):
        data=json.dumps([self.id,self.version,self.price,self.item_ids],separators=(',',':'))
        return sha256(data.encode()).hexdigest()


CATALOG=MappingProxyType({item.id:item for item in (
    Item('deck_mario','Mario Classic','deck','mario'),
    Item('dealer_luigi','Luigi','dealer','luigi'),
    Item('felt_classic','Classic Green','felt','classic'),
    Item('frame_none','No profile frame','profile_frame','none'),
    Item('effect_none','No profile effect','profile_effect','none'),
    Item('felt_midnight','Midnight Felt','felt','midnight'),
    Item('felt_rose','Rose Felt','felt','rose'),
    Item('frame_silver','Silver Profile Frame','profile_frame','silver'),
    Item('effect_sparkle','Profile Sparkles','profile_effect','sparkle'),
)})
DEFAULTS=MappingProxyType(dict(zip(SLOTS,('deck_mario','dealer_luigi','felt_classic','frame_none','effect_none'))))
OFFERS=MappingProxyType({'starter_style':Offer('starter_style','Starter Style Pack',
    ('felt_midnight','felt_rose','frame_silver','effect_sparkle'),0)})


def validate_catalog(items,offers):
    for key,item in items.items():
        if key!=item.id:raise ValueError('Catalog key must match item ID')
    for slot,item_id in DEFAULTS.items():
        if item_id not in items or items[item_id].slot!=slot:
            raise ValueError('Every slot needs its classic default')
    for key,offer in offers.items():
        if key!=offer.id or any(i not in items for i in offer.item_ids):
            raise ValueError('Offer references an unknown item')
        if any(i in DEFAULTS.values() for i in offer.item_ids):
            raise ValueError('Default cosmetics must remain free and automatically owned')


def equipped_ids(record,items=CATALOG):
    state=record.get('cosmetics') or {}
    if not isinstance(state,dict) or state.get('schema_version',1)!=1:state={}
    owned=state.get('owned',[])
    owned=set(i for i in owned if isinstance(i,str)) if isinstance(owned,list) else set()
    owned.update(DEFAULTS.values())
    equipped=state.get('equipped',{})
    if not isinstance(equipped,dict):equipped={}
    result=dict(DEFAULTS)
    for slot in SLOTS:
        candidate=equipped.get(slot)
        if isinstance(candidate,str) and candidate in owned and candidate in items and items[candidate].slot==slot:
            result[slot]=candidate
    return result


def appearance(record,items=CATALOG):
    return Appearance(**{slot:items[item_id].asset_key for slot,item_id in equipped_ids(record,items).items()})


validate_catalog(CATALOG,OFFERS)
