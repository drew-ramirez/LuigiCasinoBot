"""Server-owned cosmetic IDs and fixed bundles; no user-supplied asset paths."""
from copy import deepcopy
from dataclasses import dataclass, fields, replace
from hashlib import sha256
import json
import re
from types import MappingProxyType

ID_PATTERN=re.compile(r'^[a-z][a-z0-9_]{0,63}$')


@dataclass(frozen=True)
class Appearance:
    deck: str = 'mario'
    dealer: str = 'luigi'
    felt: str = 'classic'
    profile_frame: str = 'none'
    profile_effect: str = 'none'


SLOTS = tuple(field.name for field in fields(Appearance))


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
DEFAULTS=MappingProxyType({'deck':'deck_mario', 'dealer':'dealer_luigi', 'felt':'felt_classic',
                           'profile_frame':'frame_none', 'profile_effect':'effect_none'})
OFFERS=MappingProxyType({'starter_style':Offer('starter_style','Starter Style Pack',
    ('felt_midnight','felt_rose','frame_silver','effect_sparkle'),0)})


def validate_catalog(items,offers):
    for key,item in items.items():
        if key!=item.id:raise ValueError('Catalog key must match item ID')
    if set(DEFAULTS) != set(SLOTS):
        raise ValueError('Every appearance slot needs a default')
    classic = Appearance()
    for slot,item_id in DEFAULTS.items():
        if item_id not in items or items[item_id].slot!=slot or items[item_id].asset_key != getattr(classic, slot):
            raise ValueError('Every slot needs its classic default')
    for key,offer in offers.items():
        if key!=offer.id or any(i not in items for i in offer.item_ids):
            raise ValueError('Offer references an unknown item')
        if any(i in DEFAULTS.values() for i in offer.item_ids):
            raise ValueError('Default cosmetics must remain free and automatically owned')


def public_profile(record, name=None):
    """Project only the fields used by the public profile artwork."""
    return {'name': str(record.get('username', 'Player')) if name is None else name,
            'balance': record.get('balance', 0), 'games_played': record.get('games_played', 0),
            'career_stars': record.get('career_stars_total', 0)}


def inventory_state(record,*,writing=False):
    state=record.get('cosmetics')
    if state is None and 'cosmetics' not in record:
        return {'schema_version':1,'revision':0,'owned':[],'equipped':{},'receipts':{}}
    valid=(isinstance(state,dict) and state.get('schema_version')==1
           and type(state.get('revision')) is int and state['revision']>=0
           and isinstance(state.get('owned'),list) and all(isinstance(i,str) for i in state['owned'])
           and isinstance(state.get('equipped'),dict) and isinstance(state.get('receipts'),dict))
    if not valid:
        if writing:raise ValueError('This cosmetic inventory version cannot be updated safely')
        return {'schema_version':1,'revision':0,'owned':[],'equipped':{},'receipts':{}}
    return deepcopy(state)


def owned_ids(state):
    owned = state.get('owned', [])
    return set(i for i in owned if isinstance(i, str)) | set(DEFAULTS.values()) if isinstance(owned, list) else set(DEFAULTS.values())


class CosmeticCatalog:
    """Catalog-backed selection and preview rules shared by storage and menus."""
    def __init__(self, items, offers):
        self.items, self.offers = dict(items), dict(offers)

    def entries(self, snapshot, mode):
        if mode == 'wardrobe':
            return [item for item in self.items.values() if item.id in snapshot['owned']]
        return list(self.offers.values())

    def selectable(self, snapshot, mode, selected):
        if mode == 'wardrobe':
            return selected in self.items and selected in snapshot['owned']
        return selected in self.offers

    def offer_owned(self, snapshot, offer):
        return all(item in snapshot['owned'] for item in offer.item_ids)

    def preview(self, snapshot, mode, selected):
        look = snapshot['appearance']
        if not selected:
            return look
        if mode == 'wardrobe':
            if not self.selectable(snapshot, mode, selected):
                raise ValueError('That owned item is no longer available.')
            chosen = [self.items[selected]]
        else:
            offer = self.offers.get(selected)
            if offer is None:
                raise ValueError('That offer is no longer available.')
            chosen = [self.items[item_id] for item_id in offer.item_ids]
        return replace(look, **{item.slot: item.asset_key for item in chosen})


def equipped_ids(record,items=CATALOG):
    state=inventory_state(record)
    owned=owned_ids(state)
    equipped=state.get('equipped',{})
    result=dict(DEFAULTS)
    for slot in SLOTS:
        candidate=equipped.get(slot)
        if isinstance(candidate,str) and candidate in owned and candidate in items and items[candidate].slot==slot:
            result[slot]=candidate
    return result


def appearance(record,items=CATALOG):
    return Appearance(**{slot:items[item_id].asset_key for slot,item_id in equipped_ids(record,items).items()})


validate_catalog(CATALOG,OFFERS)
