"""First-use account creation grants one wallet under concurrent commands."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Barrier, Lock
from unittest.mock import MagicMock

from bson import ObjectId
from pymongo.errors import DuplicateKeyError
import pytest


class Accounts:
    def __init__(self, *documents):
        self.documents = {doc['_id']: deepcopy(doc) for doc in documents}
        self.lock = Lock()
        self.barrier = None
        self.inserts = 0

    def find_one(self, query):
        with self.lock:
            return next((deepcopy(doc) for doc in self.documents.values()
                         if all(doc.get(key) == value for key, value in query.items())), None)

    def insert_one(self, document):
        if self.barrier:
            self.barrier.wait(timeout=5)
        with self.lock:
            if document['_id'] in self.documents:
                raise DuplicateKeyError('duplicate _id')
            self.documents[document['_id']] = deepcopy(document)
            self.inserts += 1


@pytest.fixture
def economy(monkeypatch):
    import pymongo
    monkeypatch.setattr(pymongo, 'MongoClient', MagicMock())
    from economy.EconomyManager import EconomyManager
    users = Accounts()
    monkeypatch.setattr(EconomyManager, 'COLLECTION', users)
    return EconomyManager, users


def test_new_account_has_stable_identity_and_one_default_grant(economy):
    manager, users = economy
    first = manager.ensure_user(42, 'Player')
    assert first['_id'] == 'discord:42'
    assert first['balance'] == 500
    assert first['animations_enabled'] is True
    assert manager.ensure_user(42, 'Renamed') == first
    assert users.inserts == 1


def test_concurrent_first_commands_share_one_wallet(economy):
    manager, users = economy
    users.barrier = Barrier(4)
    with ThreadPoolExecutor(max_workers=4) as pool:
        records = list(pool.map(lambda _: manager.ensure_user(42, 'Player'), range(4)))
    assert all(record == records[0] for record in records)
    assert len(users.documents) == users.inserts == 1
    assert sum(record['balance'] for record in users.documents.values()) == 500


def test_existing_objectid_wallet_and_saved_round_are_preserved(economy):
    manager, users = economy
    legacy = {'_id': ObjectId(), 'user_id': 42, 'balance': 91,
              'blackjack_round': {'id': 'saved-round', 'revision': 3}}
    users.documents[legacy['_id']] = deepcopy(legacy)
    assert manager.ensure_user(42, 'Player') == legacy
    assert users.inserts == 0
    assert set(users.documents) == {legacy['_id']}


def test_losing_insert_reads_winners_spent_balance_not_default_template(economy):
    manager, users = economy
    def insert_after_other_command(document):
        users.documents[document['_id']] = {**document, 'balance': 300,
                                            'blackjack_round': {'id': 'funded', 'revision': 0}}
        raise DuplicateKeyError('other interaction inserted and funded a game')
    users.insert_one = insert_after_other_command
    record = manager.ensure_user(42)
    assert record['balance'] == 300
    assert record['blackjack_round']['id'] == 'funded'


def test_unrelated_id_collision_is_not_treated_as_another_users_wallet(economy):
    manager, users = economy
    users.documents['discord:42'] = {'_id': 'discord:42', 'user_id': 99, 'balance': 700}
    with pytest.raises(DuplicateKeyError):
        manager.ensure_user(42)
    assert users.documents['discord:42']['balance'] == 700


def test_unexplained_duplicate_failure_is_not_hidden(economy):
    manager, users = economy
    users.insert_one = MagicMock(side_effect=DuplicateKeyError('unrelated unique index'))
    with pytest.raises(DuplicateKeyError):
        manager.ensure_user(42)
    assert users.documents == {}
