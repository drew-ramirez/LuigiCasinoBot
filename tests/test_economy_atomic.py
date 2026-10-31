"""Wallet debits remain funded when legacy games and Blackjack compete."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Barrier, Lock
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from casinogames.blackjack import Blackjack
from economy.blackjack_table import BlackjackTable


class Wallet:
    def __init__(self, balance=100):
        self.doc = {"_id": "wallet-42", "user_id": 42, "balance": balance}
        self.lock = Lock()
        self.barrier = None

    def find_one(self, query):
        with self.lock:
            return deepcopy(self.doc)

    def _write(self, query, update):
        if self.barrier:
            self.barrier.wait(timeout=5)
        with self.lock:
            for key, expected in query.items():
                actual = self.doc
                for part in key.split("."):
                    actual = actual.get(part) if isinstance(actual, dict) else None
                if isinstance(expected, dict):
                    if "$gte" in expected and (actual is None or actual < expected["$gte"]):
                        return None
                    if "$exists" in expected and (actual is not None) != expected["$exists"]:
                        return None
                elif actual != expected:
                    return None
            self.doc.update(deepcopy(update.get("$set", {})))
            for key, amount in update.get("$inc", {}).items():
                self.doc[key] = self.doc.get(key, 0) + amount
            for key, amount in update.get("$max", {}).items():
                self.doc[key] = max(self.doc.get(key, 0), amount)
            return deepcopy(self.doc)

    def update_one(self, query, update):
        return SimpleNamespace(matched_count=int(self._write(query, update) is not None))

    def find_one_and_update(self, query, update, return_document):
        return self._write(query, update)


@pytest.fixture
def economy(monkeypatch):
    import pymongo
    monkeypatch.setattr(pymongo, "MongoClient", MagicMock())
    from economy.EconomyManager import EconomyManager
    users = Wallet()
    monkeypatch.setattr(EconomyManager, "COLLECTION", users)
    monkeypatch.setattr(EconomyManager, "ensure_user", lambda uid, username="Unknown": users.find_one({"user_id": uid}))
    return EconomyManager, users


@pytest.mark.parametrize("amount", [0, -1, 1.5, "10", True, None])
def test_invalid_wagers_cannot_credit_balance(economy, amount):
    manager, users = economy
    before = deepcopy(users.doc)
    with pytest.raises(ValueError, match="positive integer"):
        manager.wager(42, amount)
    assert users.doc == before


def test_unfunded_wager_changes_no_counters(economy):
    manager, users = economy
    before = deepcopy(users.doc)
    assert not manager.wager(42, 101)
    assert users.doc == before


def test_funded_wager_records_existing_gross_counters(economy):
    manager, users = economy
    assert manager.wager(42, 75)
    assert users.doc["balance"] == 25
    assert users.doc["coins_lost"] == 75
    assert users.doc["games_played"] == 1


def test_concurrent_legacy_games_cannot_spend_same_balance(economy):
    manager, users = economy
    users.barrier = Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: manager.wager(42, 75), range(2)))
    assert sorted(results) == [False, True]
    assert users.doc["balance"] == 25
    assert users.doc["coins_lost"] == 75
    assert users.doc["games_played"] == 1


def test_legacy_wager_and_blackjack_double_share_atomic_funding(economy):
    manager, users = economy
    users.doc["balance"] = 300
    table = BlackjackTable(users, game_factory=lambda bet: Blackjack(
        bet, shoe=["8S", "10H", "3D", "9C", "5S"]))
    saved = table.start(42, 100)
    users.barrier = Barrier(2)
    def double():
        try:
            table.act(42, saved["id"], 0, "double")
            return True
        except ValueError as exc:
            assert "Insufficient" in str(exc)
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        wager = pool.submit(manager.wager, 42, 150)
        doubled = pool.submit(double)
        results = [wager.result(), doubled.result()]
    assert results.count(True) == 1
    assert users.doc["balance"] in (50, 100)
    assert users.doc["balance"] + users.doc["coins_lost"] == 300
