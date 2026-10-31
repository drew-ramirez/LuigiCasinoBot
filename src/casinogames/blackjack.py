"""House Blackjack v1: six decks, S17, 3:2 naturals, one split, DAS.

This is the explicit bot adaptation described in the research handoff, not a
recreation of Ni no Kuni. Money is handled by the session service: debit the
initial bet and each ``extra_stake`` before accepting an action; ``payout`` is
the gross return, including any returned stake. Rendering uses public_state.
"""
from copy import deepcopy
import random


RANKS = ("A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K")
SUITS = ("S", "H", "D", "C")
RULES = "House v1 · 6 decks · stands on soft 17 · blackjack 3:2 · one split · double after split"


def card_rank(card):
    if not isinstance(card, str) or card[-1:] not in SUITS or card[:-1] not in RANKS:
        raise ValueError("Invalid standard card")
    return card[:-1]


def hand_total(cards):
    """Return (best total, soft), counting only an unconverted Ace as soft."""
    ranks = [card_rank(card) for card in cards]
    total = sum(11 if rank == "A" else 10 if rank in ("J", "Q", "K") else int(rank)
                for rank in ranks)
    aces = ranks.count("A")
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total, bool(aces)


class Blackjack:
    GAME_KEY = "blackjack"
    RULES_VERSION = 1

    def __init__(self, bet, rng=None, shoe=None):
        if type(bet) is not int or bet <= 0 or bet % 2:
            raise ValueError("Blackjack requires a positive even wager for exact 3:2 returns")
        self.bet = bet
        self.shoe = list(shoe) if shoe is not None else [r + s for _ in range(6) for s in SUITS for r in RANKS]
        for card in self.shoe:
            card_rank(card)
        if shoe is None:
            (rng or random.SystemRandom()).shuffle(self.shoe)
        if len(self.shoe) < 4:
            raise ValueError("At least four cards are needed")
        self.hands = [{"cards": [], "bet": bet, "done": False}]
        self.dealer = []
        self.active_hand = 0
        self.split = False
        self.result = None
        self.revision = 0
        # Conventional alternating deal; caller-supplied shoes are draw order.
        self.hands[0]["cards"].append(self._draw())
        self.dealer.append(self._draw())
        self.hands[0]["cards"].append(self._draw())
        self.dealer.append(self._draw())
        if self._natural(self.hands[0]["cards"]) or self._natural(self.dealer):
            self._settle()

    @staticmethod
    def _natural(cards):
        return len(cards) == 2 and hand_total(cards)[0] == 21

    def _draw(self):
        if not self.shoe:
            raise ValueError("Shoe exhausted")
        return self.shoe.pop(0)

    @property
    def total_committed(self):
        return sum(hand["bet"] for hand in self.hands)

    def allowed_actions(self):
        if self.result is not None:
            return ()
        hand = self.hands[self.active_hand]
        actions = ["hit", "stand"]
        if len(hand["cards"]) == 2:
            actions.append("double")
            if not self.split and card_rank(hand["cards"][0]) == card_rank(hand["cards"][1]):
                actions.append("split")
        return tuple(actions)

    def extra_stake(self, action):
        if action not in self.allowed_actions():
            raise ValueError("That action is not available")
        return self.hands[self.active_hand]["bet"] if action in ("double", "split") else 0

    def act(self, action):
        """Accept one funded action; errors restore the complete prior state.

        Session code must lock and validate its saved revision before funding;
        repeating a *different* legal hit is a real additional decision.
        """
        self.extra_stake(action)
        before = self.to_dict()
        try:
            hand = self.hands[self.active_hand]
            if action == "split":
                first, second = hand["cards"]
                self.split = True
                self.hands = [{"cards": [card], "bet": self.bet, "done": False}
                              for card in (first, second)]
                self.hands[0]["cards"].append(self._draw())
                if card_rank(first) == "A":
                    self.hands[1]["cards"].append(self._draw())
                    for split_hand in self.hands:
                        split_hand["done"] = True
                elif hand_total(self.hands[0]["cards"])[0] == 21:
                    self.hands[0]["done"] = True
            elif action == "stand":
                hand["done"] = True
            else:
                if action == "double":
                    hand["bet"] *= 2
                hand["cards"].append(self._draw())
                hand["done"] = action == "double" or hand_total(hand["cards"])[0] >= 21
            self._advance()
            self.revision += 1
        except Exception:
            self.__dict__.update(self.from_dict(before).__dict__)
            raise
        return self.result

    def _advance(self):
        while self.active_hand < len(self.hands) and self.hands[self.active_hand]["done"]:
            self.active_hand += 1
            if self.active_hand < len(self.hands):
                hand = self.hands[self.active_hand]
                if len(hand["cards"]) == 1:
                    hand["cards"].append(self._draw())
                if hand_total(hand["cards"])[0] == 21:
                    hand["done"] = True
        if self.active_hand == len(self.hands):
            # A player bust needs no further dealer draws, including all-bust splits.
            if any(hand_total(hand["cards"])[0] <= 21 for hand in self.hands):
                while hand_total(self.dealer)[0] < 17:
                    self.dealer.append(self._draw())
            self._settle()

    def _settle(self):
        dealer_total = hand_total(self.dealer)[0]
        dealer_natural = self._natural(self.dealer)
        outcomes = []
        for hand in self.hands:
            total = hand_total(hand["cards"])[0]
            natural = not self.split and self._natural(hand["cards"])
            if total > 21:
                outcome, payout = "bust", 0
            elif dealer_natural:
                outcome, payout = ("push", hand["bet"]) if natural else ("loss", 0)
            elif natural:
                outcome, payout = "blackjack", hand["bet"] * 5 // 2
            elif dealer_total > 21 or total > dealer_total:
                outcome, payout = "win", hand["bet"] * 2
            elif total == dealer_total:
                outcome, payout = "push", hand["bet"]
            else:
                outcome, payout = "loss", 0
            hand["done"] = True
            outcomes.append({"outcome": outcome, "bet": hand["bet"], "total": total, "payout": payout})
        payout = sum(item["payout"] for item in outcomes)
        self.active_hand = len(self.hands)
        self.result = {"hands": outcomes, "dealer_total": dealer_total,
                       "payout": payout, "committed": self.total_committed,
                       "profit": payout - self.total_committed}

    def timeout(self):
        """Stand every unfinished hand; never refund or draw a replacement deal."""
        while self.result is None:
            self.act("stand")
        return deepcopy(self.result)

    def public_state(self):
        """Only information legal for an image, spectator, or player response."""
        revealed = self.result is not None
        return {"rules": RULES, "hands": deepcopy(self.hands),
                "dealer": list(self.dealer) if revealed else [self.dealer[0], None],
                "dealer_total": hand_total(self.dealer)[0] if revealed else None,
                "active_hand": self.active_hand, "total_committed": self.total_committed,
                "result": deepcopy(self.result), "actions": self.allowed_actions(),
                "revision": self.revision}

    def to_dict(self):
        """Private persistence payload. Never put this object in a Discord response."""
        return deepcopy({"version": self.RULES_VERSION, "bet": self.bet, "shoe": self.shoe,
                         "hands": self.hands, "dealer": self.dealer, "active_hand": self.active_hand,
                         "split": self.split, "result": self.result, "revision": self.revision})

    @classmethod
    def from_dict(cls, data):
        """Restore a trusted saved engine snapshot without dealing or shuffling."""
        if data.get("version") != cls.RULES_VERSION:
            raise ValueError("Unsupported Blackjack save version")
        obj = cls.__new__(cls)
        for key in ("bet", "shoe", "hands", "dealer", "active_hand", "split", "result", "revision"):
            setattr(obj, key, deepcopy(data[key]))
        if type(obj.bet) is not int or obj.bet <= 0 or obj.bet % 2:
            raise ValueError("Invalid saved wager")
        if type(obj.revision) is not int or obj.revision < 0 or type(obj.split) is not bool:
            raise ValueError("Invalid saved state")
        if len(obj.hands) != (2 if obj.split else 1) or len(obj.dealer) < 2:
            raise ValueError("Invalid saved hands")
        for card in obj.shoe + obj.dealer:
            card_rank(card)
        for hand in obj.hands:
            if not hand["cards"] or hand["bet"] not in (obj.bet, obj.bet * 2) or type(hand["done"]) is not bool:
                raise ValueError("Invalid saved hand")
            for card in hand["cards"]:
                card_rank(card)
        if type(obj.active_hand) is not int or not 0 <= obj.active_hand <= len(obj.hands):
            raise ValueError("Invalid saved turn")
        if obj.result is None and (obj.active_hand == len(obj.hands) or obj.hands[obj.active_hand]["done"]):
            raise ValueError("Invalid active hand")
        return obj
