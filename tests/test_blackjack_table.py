"""Atomic single-document settlement, retries, and competing actions."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Barrier, Lock

import pytest

from casinogames.blackjack import Blackjack
from economy.blackjack_table import BlackjackTable


class AtomicUsers:
    """Small in-memory Mongo predicate/update model with a real mutex."""
    def __init__(self, balance=500):
        self.doc = {"_id": "user-42", "user_id": 42, "balance": balance}
        self.lock = Lock()
        self.barrier = None
        self.writes = 0

    @staticmethod
    def matches(doc, query):
        missing = object()
        for key, expected in query.items():
            actual = doc
            for part in key.split("."):
                actual = actual.get(part, missing) if isinstance(actual, dict) else missing
            if isinstance(expected, dict):
                if "$exists" in expected and (actual is not missing) != expected["$exists"]:
                    return False
                if "$gte" in expected and (actual is missing or actual < expected["$gte"]):
                    return False
            elif actual != expected:
                return False
        return True

    def find_one(self, query):
        with self.lock:
            return deepcopy(self.doc) if self.matches(self.doc, query) else None

    def find_one_and_update(self, query, update, return_document):
        if self.barrier:
            self.barrier.wait(timeout=5)
        with self.lock:
            if not self.matches(self.doc, query):
                return None
            self.doc.update(deepcopy(update.get("$set", {})))
            for key, amount in update.get("$inc", {}).items():
                self.doc[key] = self.doc.get(key, 0) + amount
            for key, amount in update.get("$max", {}).items():
                self.doc[key] = max(self.doc.get(key, 0), amount)
            self.writes += 1
            return deepcopy(self.doc)


def table(cards=("8S", "6H", "3D", "10C", "9S", "8H"), balance=500):
    users = AtomicUsers(balance)
    service = BlackjackTable(users, game_factory=lambda bet: Blackjack(bet, shoe=cards))
    return service, users


def test_start_debits_and_saves_together_then_resumes_without_charge():
    service, users = table()
    saved = service.start(42, 100)
    assert saved["balance"] == 400
    assert users.doc["games_played"] == 1
    assert users.doc["coins_lost"] == 100
    assert service.start(42, 200) == saved
    assert users.writes == 1


def test_double_and_payout_are_single_atomic_update():
    service, users = table()
    saved = service.start(42, 100)
    finished = service.act(42, saved["id"], saved["revision"], "double")
    assert finished["balance"] == 700
    assert finished["game"]["result"]["payout"] == 400
    assert users.doc["coins_lost"] == 200
    assert users.doc["coins_won"] == 400
    assert users.doc["biggest_cashout"] == 400
    assert users.doc["games_played"] == 1
    assert service.act(42, saved["id"], 0, "double") == finished
    assert users.writes == 2


def test_immediate_natural_is_settled_in_initial_write():
    service, users = table(("AS", "9H", "KD", "8C"))
    saved = service.start(42, 100)
    assert saved["balance"] == 650
    assert saved["game"]["result"]["payout"] == 250
    assert users.writes == 1
    assert service.start(42, 100) == saved
    assert users.writes == 1


def test_new_deal_requires_explicit_current_result_and_retries_do_not_buy_again():
    service, users = table(("AS", "9H", "KD", "8C"))
    first = service.start(42, 100)
    second = service.start(42, 100, expected_round_id=first["id"], expected_revision=0)
    assert second["id"] != first["id"]
    assert second["balance"] == 800
    retry = service.start(42, 100, expected_round_id=first["id"], expected_revision=0)
    assert retry == second
    assert users.writes == 2


def test_insufficient_extra_stake_does_not_change_deal_or_wallet():
    service, users = table(balance=100)
    saved = service.start(42, 100)
    with pytest.raises(ValueError, match="Insufficient"):
        service.act(42, saved["id"], 0, "double")
    assert service.get(42) == saved
    assert users.writes == 1
    finished = service.act(42, saved["id"], 0, "stand")
    assert finished["game"]["result"] is not None


def test_unfunded_start_never_deals_or_writes():
    service, users = table(balance=99)
    service.game_factory = lambda bet: pytest.fail("An unfunded deal was created")
    with pytest.raises(ValueError, match="Insufficient"):
        service.start(42, 100)
    assert service.get(42) is None
    assert users.writes == 0


def test_timeout_stands_every_split_hand_and_settles_once_after_restart():
    service, users = table(("8S", "10H", "8D", "7C", "10S", "9H"))
    saved = service.start(42, 100)
    split = service.act(42, saved["id"], 0, "split")
    restarted = BlackjackTable(users)
    finished = restarted.act(42, saved["id"], split["revision"], "timeout")
    assert finished["balance"] == 600
    assert restarted.act(42, saved["id"], split["revision"], "timeout") == finished
    assert users.writes == 3


def test_competing_starts_debit_only_the_winning_saved_round():
    service, users = table()
    users.barrier = Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: service.start(42, 100), range(2)))
    assert results[0] == results[1]
    assert users.doc["balance"] == 400
    assert users.writes == 1


def test_competing_double_callbacks_accept_exactly_one_action():
    service, users = table()
    saved = service.start(42, 100)
    users.barrier = Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: service.act(42, saved["id"], 0, "double"), range(2)))
    assert results[0] == results[1]
    assert users.doc["balance"] == 700
    assert users.writes == 2


def test_wallet_change_between_read_and_write_is_rechecked():
    service, users = table(balance=200)
    saved = service.start(42, 100)
    atomic_update = users.find_one_and_update
    def spend_before_update(query, update, return_document):
        users.doc["balance"] = 99
        return atomic_update(query, update, return_document)
    users.find_one_and_update = spend_before_update
    with pytest.raises(ValueError, match="Insufficient"):
        service.act(42, saved["id"], 0, "double")
    assert service.get(42)["game"] == saved["game"]
    assert users.doc["balance"] == 99
    assert users.writes == 1


def test_render_failure_retry_reads_same_saved_outcome():
    service, users = table()
    saved = service.start(42, 100)
    result = service.act(42, saved["id"], 0, "double")
    # A restarted Discord callback sees the settled state without rendering first.
    resumed = BlackjackTable(users).get(42)
    assert resumed == result
    assert users.writes == 2
