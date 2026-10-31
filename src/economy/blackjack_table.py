"""Atomic Blackjack wallet + round updates in one existing Mongo user document.

No payout worker or multi-document transaction is needed. A successful write
contains both the accepted private game state and its complete balance change.
Discord delivery and rendering happen afterwards and may be retried freely.
"""
from copy import deepcopy
from uuid import uuid4

from casinogames.blackjack import Blackjack


class BlackjackTable:
    FIELD = "blackjack_round"

    def __init__(self, collection=None, ensure_user=None, game_factory=Blackjack):
        if collection is None:
            from economy.EconomyManager import EconomyManager
            collection = EconomyManager.COLLECTION
            ensure_user = ensure_user or EconomyManager.ensure_user
        self.collection = collection
        self.ensure_user = ensure_user
        self.game_factory = game_factory

    @classmethod
    def _snapshot(cls, record):
        if not record or cls.FIELD not in record:
            return None
        saved = deepcopy(record[cls.FIELD])
        saved["balance"] = record.get("balance", 0)
        return saved

    def get(self, user_id):
        """Private server snapshot; render its game via Blackjack.public_state()."""
        return self._snapshot(self.collection.find_one({"user_id": user_id}))

    @classmethod
    def _matches(cls, record, round_id, revision):
        saved = record.get(cls.FIELD) if record else None
        return saved and saved["id"] == round_id and saved["revision"] == revision

    @classmethod
    def _query(cls, record, cost):
        query = {"_id": record["_id"], "balance": {"$gte": cost}}
        saved = record.get(cls.FIELD)
        if saved is None:
            query[cls.FIELD] = {"$exists": False}
        else:
            query[f"{cls.FIELD}.id"] = saved["id"]
            query[f"{cls.FIELD}.revision"] = saved["revision"]
        return query

    def _commit(self, record, saved, cost, payout, *, new_round=False):
        increments = {"balance": payout - cost, "coins_lost": cost, "coins_won": payout}
        if new_round:
            increments["games_played"] = 1
        update = {"$set": {self.FIELD: saved}, "$inc": increments}
        if saved["game"]["result"] is not None:
            update["$max"] = {"biggest_cashout": payout}
        updated = self.collection.find_one_and_update(
            self._query(record, cost), update, return_document=True)
        if updated is not None:
            return self._snapshot(updated)
        # Another interaction may have advanced the table. Return its authoritative
        # state without replaying this action or applying another debit/payout.
        latest = self.collection.find_one({"_id": record["_id"]})
        previous = record.get(self.FIELD)
        current = latest.get(self.FIELD) if latest else None
        if previous != current:
            return self._snapshot(latest)
        raise ValueError("Insufficient balance; the table is unchanged")

    def start(self, user_id, bet, username="Unknown", *, expected_round_id=None, expected_revision=None):
        """Deal once, or resume the existing round.

        Starting again after a result requires the exact previous id/revision.
        Consequently a duplicated initial command cannot silently buy two deals.
        """
        if type(bet) is not int or bet <= 0 or bet % 2:
            raise ValueError("Blackjack requires a positive even wager")
        record = (self.ensure_user(user_id, username) if self.ensure_user
                  else self.collection.find_one({"user_id": user_id}))
        if not record or "_id" not in record:
            raise ValueError("An existing economy account is required")
        previous = record.get(self.FIELD)
        if previous is not None:
            if previous["game"]["result"] is None:
                return self._snapshot(record)
            if not self._matches(record, expected_round_id, expected_revision):
                return self._snapshot(record)
        elif expected_round_id is not None or expected_revision is not None:
            raise ValueError("The requested previous round does not exist")
        if record.get("balance", 0) < bet:
            raise ValueError("Insufficient balance; no cards dealt")
        game = self.game_factory(bet)
        saved = {"id": uuid4().hex, "revision": 0, "game": game.to_dict()}
        payout = game.result["payout"] if game.result is not None else 0
        return self._commit(record, saved, bet, payout, new_round=True)

    def act(self, user_id, round_id, revision, action):
        """Apply a funded action once; stale callbacks return current saved state.

        ``timeout`` uses the published stand-all rule. Additional split/double
        funds and any resulting payout are committed together with the state.
        """
        record = self.collection.find_one({"user_id": user_id})
        if not record or self.FIELD not in record:
            raise ValueError("There is no saved Blackjack round")
        if not self._matches(record, round_id, revision):
            return self._snapshot(record)
        previous = record[self.FIELD]
        game = Blackjack.from_dict(previous["game"])
        if game.result is not None:
            return self._snapshot(record)
        cost = 0 if action == "timeout" else game.extra_stake(action)
        if record.get("balance", 0) < cost:
            raise ValueError("Insufficient balance for that action; hit and stand remain available")
        if action == "timeout":
            game.timeout()
        else:
            game.act(action)
        saved = {"id": round_id, "revision": revision + 1, "game": game.to_dict()}
        payout = game.result["payout"] if game.result is not None else 0
        return self._commit(record, saved, cost, payout)
