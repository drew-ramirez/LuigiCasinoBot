"""Fortune's Tower: Diamond-deck, score-only practice rules.

The Fable II official guide (printed pp. 226-227) establishes the deck,
parent matches, row-wide Heroes, Gate rescue, sets and final-row jackpot.
The following *house conventions* make underspecified cases deterministic:
resolve hazards left-to-right; a Hero Gate protects its replacement row;
keep the largest set multiplier; include an unused Gate in the jackpot.
These conventions are not a claim of exact Fable payout fidelity. Practice
points never enter the community wallet. No renderer may draw cards.
"""
from __future__ import annotations

from copy import deepcopy
import random


class FortuneTower:
    GAME_KEY = "fortune_tower"
    RULES_VERSION = "diamond-practice-v1"
    HERO = 0
    MAX_ROW = 8
    PRACTICE_ONLY = True
    RULES = (
        "Practice points only; no community coins. Diamond deck: eight each "
        "of 1-7 and four Heroes. Match either touching parent and the Gate "
        "replaces the first dangerous card; another match busts. A Hero "
        "protects its whole row, including a Hero revealed as the Gate. "
        "Bank the current offer or deal again; later offers can be lower. "
        "A matching set keeps the highest row-size multiplier. Complete "
        "row eight with an unused Gate for a whole-tower jackpot. "
        "Gross points = stake / 15 x value x multiplier; net = gross - stake. "
        "Inactivity banks the current offer. Exceptional rules are house conventions."
    )

    def __init__(self, stake=30, rng=None, deck=None):
        if type(stake) is not int or stake <= 0 or stake % 15:
            raise ValueError("Practice stake must be a positive multiple of 15")
        cards = list(deck) if deck is not None else self.make_deck()
        if len(cards) < 36 or any(type(c) is not int or c not in range(8) for c in cards):
            raise ValueError("A deck needs at least 36 cards numbered 0 (Hero) through 7")
        if deck is None:
            (rng or random.SystemRandom()).shuffle(cards)
        self.stake = stake
        self.deck = cards
        self.gate = self.deck.pop(0)
        self.gate_used = False
        self.rows = []
        self.multiplier = 1
        self.offer = 0
        self.result = None
        self.last_event = {}
        self.deal_next()

    @staticmethod
    def make_deck():
        return [value for value in range(1, 8) for _ in range(8)] + [0] * 4

    @property
    def bet(self):
        return self.stake

    @property
    def finished(self):
        return self.result is not None

    @property
    def row_number(self):
        return len(self.rows[-1]) if self.rows else 1

    @property
    def net(self):
        return self.offer - self.stake

    @staticmethod
    def _hazards(row, parents):
        """Outside cards have one parent; inner cards touch two parents."""
        if not parents or FortuneTower.HERO in row:
            return []
        return [i for i, value in enumerate(row)
                if any(0 <= parent < len(parents) and parents[parent] == value
                       for parent in (i - 1, i))]

    def deal_next(self):
        if self.finished:
            raise ValueError("The tower is finished")
        width = self.row_number + 1
        if width > self.MAX_ROW or len(self.deck) < width:
            raise ValueError("Cannot deal another complete row")
        previous_offer = self.offer
        row, self.deck = self.deck[:width], self.deck[width:]
        parents = self.rows[-1] if self.rows else []
        raw_row = row.copy()
        # Record pre-protection dangers for animation without exposing the Gate.
        hazards = [i for i, value in enumerate(row) if value != self.HERO
                   and any(0 <= p < len(parents) and parents[p] == value
                           for p in (i - 1, i))]
        protected = self.HERO in row
        replacement = None
        if hazards and not protected and not self.gate_used:
            index = hazards[0]
            replacement = {"index": index, "discarded": row[index], "card": self.gate}
            row[index] = self.gate
            self.gate_used = True
            protected = self.HERO in row
        remaining = self._hazards(row, parents)
        self.rows.append(row)
        self.last_event = {
            "kind": "deal", "row": width, "dealt": raw_row,
            "hazards": hazards, "protected": protected,
            "replacement": replacement, "remaining_hazards": remaining,
            "previous_offer": previous_offer,
        }
        if remaining:
            self.offer = 0
            self._finish("bust")
        else:
            if len(set(row)) == 1:
                self.multiplier = max(self.multiplier, width)
            jackpot = width == self.MAX_ROW and not self.gate_used
            value = sum(map(sum, self.rows)) + self.gate if jackpot else sum(row)
            self.offer = (self.stake // 15) * value * self.multiplier
            if width == self.MAX_ROW:
                self._finish("jackpot" if jackpot else "complete")
        self.last_event["offer"] = self.offer
        self.last_event["multiplier"] = self.multiplier
        return deepcopy(self.last_event)

    def _finish(self, outcome):
        self.result = {
            "outcome": outcome, "gross": self.offer, "net": self.net,
            "score": self.offer, "row": self.row_number,
            "multiplier": self.multiplier, "practice_only": True,
        }

    def bank(self):
        """Idempotently finalize the saved offer, without redrawing a card."""
        if not self.finished:
            self._finish("banked")
            self.last_event = {"kind": "bank", "offer": self.offer}
        return deepcopy(self.result)

    def expire(self):
        """The published solo timeout policy accepts the existing offer."""
        return self.bank()

    def public_state(self):
        """Only safe data for public text/images; never includes future cards."""
        return {
            "rules_version": self.RULES_VERSION, "practice_only": True,
            "stake": self.stake, "rows": deepcopy(self.rows),
            "row_number": self.row_number,
            "gate": self.gate if self.gate_used or self.finished else None,
            "gate_used": self.gate_used, "multiplier": self.multiplier,
            "offer": self.offer, "net": self.net, "finished": self.finished,
            "result": deepcopy(self.result), "event": deepcopy(self.last_event),
        }

    def to_dict(self):
        """Private durable snapshot. This is never a public rendering payload."""
        return {"rules_version": self.RULES_VERSION,
                **deepcopy({key: getattr(self, key) for key in (
                    "stake", "deck", "gate", "gate_used", "rows", "multiplier",
                    "offer", "result", "last_event")})}

    @classmethod
    def from_dict(cls, state):
        if state.get("rules_version") != cls.RULES_VERSION:
            raise ValueError("Unsupported Fortune's Tower rules version")
        game = cls.__new__(cls)
        for key in ("stake", "deck", "gate", "gate_used", "rows", "multiplier",
                    "offer", "result", "last_event"):
            setattr(game, key, deepcopy(state[key]))
        if (type(game.stake) is not int or game.stake <= 0 or game.stake % 15
                or type(game.gate) is not int or game.gate not in range(8)
                or not game.rows or len(game.rows) > 7
                or any(len(row) != i + 2 for i, row in enumerate(game.rows))
                or any(type(c) is not int or c not in range(8)
                       for c in game.deck + [c for row in game.rows for c in row])
                or type(game.multiplier) is not int or game.multiplier not in range(1, 9)
                or type(game.offer) is not int or game.offer < 0
                or type(game.gate_used) is not bool):
            raise ValueError("Invalid Fortune's Tower snapshot")
        return game
