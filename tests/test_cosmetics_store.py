"""Cosmetic ownership and wallet transactions against an atomic Mongo-shaped fake."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Barrier, RLock
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from cosmetics.catalog import Appearance, CATALOG, DEFAULTS, OFFERS, Item, Offer, appearance
from cosmetics.store import CosmeticsStore

USER = 4321
MISSING = object()


def dotted(document, path):
    value = document
    for part in path.split('.'):
        if not isinstance(value, dict) or part not in value:
            return MISSING
        value = value[part]
    return value


def matches(document, query):
    for key, expected in query.items():
        value = dotted(document, key)
        if isinstance(expected, dict):
            for op, operand in expected.items():
                if op == '$exists':
                    if (value is not MISSING) != operand:
                        return False
                elif op == '$gte':
                    if value is MISSING or value < operand:
                        return False
                else:
                    raise AssertionError(f'Unsupported query operator {op}')
        elif value is MISSING or value != expected:
            return False
    return True


class Users:
    """Locks filter+mutation together; optional first-write barrier forces races."""
    def __init__(self, balance=100):
        self.document = {'_id': 'legacy-account-9', 'user_id': USER, 'username': 'Mario',
                         'balance': balance, 'games_played': 4, 'career_stars_total': 6,
                         'animations_enabled': False, 'private_token': 'DO_NOT_EXPOSE'}
        self.lock = RLock()
        self.write_calls = 0
        self.successful_writes = 0
        self.barrier = None
        self.barrier_calls = 0
        self.before_write = None
        self.fail_write = False

    def race(self, writers):
        self.barrier = Barrier(writers)
        self.barrier_calls = writers

    def find_one(self, query):
        with self.lock:
            return deepcopy(self.document) if matches(self.document, query) else None

    def _update(self, query, update):
        with self.lock:
            self.write_calls += 1
            gate = self.barrier if self.barrier_calls else None
            self.barrier_calls = max(0, self.barrier_calls - 1)
        if gate is not None:
            gate.wait(timeout=5)
        with self.lock:
            if self.before_write:
                hook, self.before_write = self.before_write, None
                hook(self.document)
            if self.fail_write:
                raise RuntimeError('simulated database write failure')
            if not matches(self.document, query):
                return None
            updated = deepcopy(self.document)
            for operator, fields in update.items():
                assert operator in ('$set', '$inc')
                for path, value in fields.items():
                    parts = path.split('.')
                    target = updated
                    for part in parts[:-1]:
                        target = target.setdefault(part, {})
                    target[parts[-1]] = deepcopy(value) if operator == '$set' else target.get(parts[-1], 0) + value
            self.document = updated
            self.successful_writes += 1
            return deepcopy(updated)

    def find_one_and_update(self, query, update, return_document):
        assert return_document is True
        return self._update(query, update)

    def update_one(self, query, update):
        updated = self._update(query, update)
        return SimpleNamespace(matched_count=int(updated is not None))


def configured(users, prices=(30, 40)):
    items = dict(CATALOG)
    items.update({'felt_gold': Item('felt_gold', 'Gold felt', 'felt', 'gold'),
                  'deck_night': Item('deck_night', 'Night deck', 'deck', 'night')})
    offers = dict(OFFERS)
    offers.update({'gold_pack': Offer('gold_pack', 'Gold pack', ('felt_gold',), prices[0]),
                   'night_pack': Offer('night_pack', 'Night pack', ('deck_night',), prices[1])})
    return CosmeticsStore(users, items=items, offers=offers)


def buy(store, offer='starter_style', request='request_1'):
    return store.purchase(USER, offer, store.offers[offer].quote_id, request)


def inventory(users):
    return users.document.get('cosmetics', {})


def test_legacy_defaults_are_virtual_without_migrating_account_and_snapshot_is_safe():
    users = Users()
    before = deepcopy(users.document)
    store = CosmeticsStore(users)
    snapshot = store.get(USER)
    assert set(snapshot['owned']) == set(DEFAULTS.values())
    assert snapshot['equipped'] == dict(DEFAULTS)
    assert snapshot['appearance'] == Appearance()
    assert snapshot['revision'] == 0 and snapshot['animations_enabled'] is False
    assert snapshot['profile'] == {'name': 'Mario', 'balance': 100, 'games_played': 4, 'career_stars': 6}
    assert 'DO_NOT_EXPOSE' not in repr(snapshot)
    assert not {'_id', 'receipts', 'private_token', 'cosmetics'} & snapshot.keys()
    snapshot['owned'].clear()
    snapshot['equipped']['felt'] = 'fake'
    assert users.document == before and users.write_calls == 0
    assert store.get(USER)['equipped']['felt'] == 'felt_classic'


def test_owned_equipment_uses_catalog_slot_and_stale_revision_cannot_overwrite():
    users = Users()
    store = CosmeticsStore(users)
    with pytest.raises(ValueError, match='own'):
        store.equip(USER, 'felt_rose', 0)
    snapshot, applied = store.equip(USER, 'deck_mario', 0)
    assert applied and users.write_calls == 0  # Already-equipped virtual default.
    buy(store)
    equipped, applied = store.equip(USER, 'frame_silver', 1)
    assert applied and equipped['revision'] == 2
    assert equipped['equipped']['profile_frame'] == 'frame_silver'
    assert equipped['equipped']['felt'] == 'felt_classic'
    stale, applied = store.equip(USER, 'felt_rose', 1)
    assert not applied and stale['revision'] == 2
    equipped, applied = store.equip(USER, 'felt_rose', 2)
    assert applied and equipped['appearance'].felt == 'rose'
    assert CosmeticsStore(users).get(USER)['equipped'] == equipped['equipped']
    assert users.document['balance'] == 100


def test_free_pack_grants_once_and_replay_never_increments_revision_or_adds_receipt():
    users = Users()
    store = CosmeticsStore(users)
    first = buy(store)
    assert first['status'] == 'purchased'
    assert buy(store)['status'] == 'replayed'
    assert buy(store, request='another_click')['status'] == 'already_owned'
    assert users.document['balance'] == 100 and users.document['cosmetics_spent'] == 0
    assert inventory(users)['revision'] == 1 and len(inventory(users)['receipts']) == 1
    assert users.successful_writes == 1
    assert set(inventory(users)['owned']) == set(OFFERS['starter_style'].item_ids)


@pytest.mark.parametrize('same_request', [False, True])
def test_concurrent_paid_confirmation_grants_and_charges_exactly_once(same_request):
    users = Users()
    store = configured(users)
    users.race(2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [pool.submit(buy, store, 'gold_pack', 'same' if same_request else f'click_{i}') for i in range(2)]
        statuses = [job.result(timeout=10)['status'] for job in jobs]
    assert sorted(statuses) == sorted(['purchased', 'replayed' if same_request else 'already_owned'])
    assert users.document['balance'] == 70 and users.document['cosmetics_spent'] == 30
    assert inventory(users)['owned'] == ['felt_gold']
    assert inventory(users)['revision'] == 1 and len(inventory(users)['receipts']) == 1
    receipt = next(iter(inventory(users)['receipts'].values()))
    assert receipt['price'] == 30 and receipt['item_ids'] == ['felt_gold']
    assert buy(configured(users), 'gold_pack', next(iter(inventory(users)['receipts'])))['status'] == 'replayed'


def test_rejected_insufficient_changed_and_reused_confirmation_have_no_side_effects():
    users = Users(balance=20)
    store = configured(users)
    before = deepcopy(users.document)
    with pytest.raises(ValueError, match='Insufficient'):
        buy(store, 'gold_pack')
    assert users.document == before
    users.document['balance'] = 100
    old_quote = store.offers['gold_pack'].quote_id
    changed = configured(users, prices=(60, 40))
    before = deepcopy(users.document)
    with pytest.raises(ValueError, match='changed'):
        changed.purchase(USER, 'gold_pack', old_quote, 'stale_price')
    assert users.document == before
    buy(store, 'gold_pack')
    before = deepcopy(users.document)
    with pytest.raises(ValueError, match='another purchase'):
        buy(store, 'night_pack')
    assert users.document == before


def test_partial_bundle_and_storage_error_do_not_charge_or_grant():
    users = Users()
    store = configured(users)
    buy(store, 'gold_pack')
    offers = dict(store.offers)
    offers['mixed_pack'] = Offer('mixed_pack', 'Mixed pack', ('felt_gold', 'deck_night'), 50)
    partial = CosmeticsStore(users, items=store.items, offers=offers)
    before = deepcopy(users.document)
    with pytest.raises(ValueError, match='already owned'):
        buy(partial, 'mixed_pack', 'partial')
    assert users.document == before
    users.fail_write = True
    with pytest.raises(RuntimeError, match='database'):
        buy(store, 'night_pack', 'failure')
    assert users.document == before


def test_distinct_purchases_and_equip_race_preserve_all_inventory_and_wallet_updates():
    users = Users()
    store = configured(users)
    buy(store)
    users.race(3)
    with ThreadPoolExecutor(max_workers=3) as pool:
        gold = pool.submit(buy, store, 'gold_pack', 'gold')
        night = pool.submit(buy, store, 'night_pack', 'night')
        equipment = pool.submit(store.equip, USER, 'frame_silver', 1)
        assert gold.result(timeout=10)['status'] == 'purchased'
        assert night.result(timeout=10)['status'] == 'purchased'
        snapshot, equipped = equipment.result(timeout=10)
    if not equipped:
        current = store.get(USER)
        _, equipped = store.equip(USER, 'frame_silver', current['revision'])
    assert equipped
    snapshot = configured(users).get(USER)
    assert set(snapshot['owned']) >= set(OFFERS['starter_style'].item_ids) | {'felt_gold', 'deck_night'}
    assert snapshot['equipped']['profile_frame'] == 'frame_silver'
    assert users.document['balance'] == 30 and users.document['cosmetics_spent'] == 70
    assert len(inventory(users)['receipts']) == 3 and snapshot['revision'] == 4


@pytest.mark.parametrize('balance', [100, 200])
def test_purchase_and_real_wager_share_one_atomic_wallet(monkeypatch, balance):
    import pymongo
    monkeypatch.setattr(pymongo, 'MongoClient', MagicMock())
    from economy.EconomyManager import EconomyManager
    users = Users(balance=balance)
    store = configured(users, prices=(80, 40))
    monkeypatch.setattr(EconomyManager, 'COLLECTION', users)
    monkeypatch.setattr(EconomyManager, 'ensure_user', lambda uid, username='Unknown': users.find_one({'user_id': uid}))
    users.race(2)
    def purchase():
        try:
            return buy(store, 'gold_pack')['status'] == 'purchased'
        except ValueError as error:
            assert 'Insufficient' in str(error)
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        bought = pool.submit(purchase)
        wagered = pool.submit(EconomyManager.wager, USER, 70)
        bought, wagered = bought.result(timeout=10), wagered.result(timeout=10)
    assert int(bought) + int(wagered) == (1 if balance == 100 else 2)
    assert users.document['balance'] == balance - 80 * bought - 70 * wagered >= 0
    assert ('felt_gold' in store.get(USER)['owned']) == bought
    assert users.document.get('cosmetics_spent', 0) == 80 * bought
    assert users.document['games_played'] == 4 + wagered
    assert users.document.get('coins_lost', 0) == 70 * wagered


def test_retired_equipped_item_falls_back_without_removing_inventory():
    users = Users()
    store = configured(users)
    buy(store, 'gold_pack')
    store.equip(USER, 'felt_gold', 1)
    before = deepcopy(users.document)
    retired = CosmeticsStore(users)
    assert retired.get(USER)['appearance'].felt == 'classic'
    assert retired.appearance_for(USER).felt == 'classic'
    assert 'felt_gold' in retired.get(USER)['owned']
    assert users.document == before


def test_future_schema_is_readable_as_defaults_but_never_rewritten():
    users = Users()
    users.document['cosmetics'] = {'schema_version': 99, 'revision': 12, 'owned': ['felt_rose'],
                                   'equipped': {'felt': 'felt_rose'}, 'receipts': {}, 'future': 'PRESERVE'}
    before = deepcopy(users.document)
    store = CosmeticsStore(users)
    assert store.get(USER)['appearance'] == Appearance()
    assert store.appearance_for(USER) == Appearance()
    for mutation in [lambda: buy(store), lambda: store.equip(USER, 'felt_rose', 12)]:
        with pytest.raises(ValueError, match='version'):
            mutation()
    assert users.document == before and users.write_calls == 0


@pytest.mark.parametrize('invalid_field, value', [
    ('revision', 'bad'), ('revision', -1), ('revision', True),
    ('owned', None), ('owned', ['felt_rose', None]), ('equipped', None),
    ('receipts', None), ('schema_version', 99),
])
def test_malformed_inventory_has_one_read_fallback_and_cannot_be_written(invalid_field, value):
    users = Users()
    users.document['cosmetics'] = {'schema_version': 1, 'revision': 1, 'owned': ['felt_rose'],
                                   'equipped': {'felt': 'felt_rose'}, 'receipts': {}}
    users.document['cosmetics'][invalid_field] = value
    before = deepcopy(users.document)
    store = CosmeticsStore(users)
    assert store.get(USER)['appearance'] == store.appearance_for(USER) == appearance(before) == Appearance()
    for mutation in (lambda: buy(store), lambda: store.equip(USER, 'felt_rose', 1)):
        with pytest.raises(ValueError, match='version'):
            mutation()
    assert users.document == before and users.write_calls == 0


@pytest.mark.parametrize('operation', ['purchase', 'equip'])
def test_concurrent_future_schema_migration_cannot_be_clobbered(operation):
    users = Users()
    store = configured(users)
    buy(store)
    def migrate(document):
        document['cosmetics']['schema_version'] = 99
        document['cosmetics']['future'] = 'PRESERVE'
    users.before_write = migrate
    if operation == 'purchase':
        with pytest.raises(ValueError, match='version'):
            buy(store, 'gold_pack', 'racing_migration')
    else:
        _, applied = store.equip(USER, 'felt_rose', 1)
        assert not applied
    assert inventory(users)['schema_version'] == 99
    assert inventory(users)['future'] == 'PRESERVE'
    assert users.document['balance'] == 100


def test_appearance_lookup_never_calls_account_creation_or_writes():
    users = Users()
    ensure = MagicMock(side_effect=AssertionError('Rendering must not create accounts'))
    store = CosmeticsStore(users, ensure_user=ensure)
    for user in [USER, 9999, 0, -1, '4321', True, None]:
        assert store.appearance_for(user) == Appearance()
    ensure.assert_not_called()
    assert users.write_calls == 0


@pytest.mark.parametrize('receipt_id', ['', '../secret', 'a.b', '$request', 'a' * 81, 5, None])
def test_invalid_receipt_identifiers_cannot_address_mongo_fields(receipt_id):
    users = Users()
    store = CosmeticsStore(users)
    before = deepcopy(users.document)
    with pytest.raises(ValueError, match='request'):
        buy(store, request=receipt_id)
    assert users.document == before and users.write_calls == 0
