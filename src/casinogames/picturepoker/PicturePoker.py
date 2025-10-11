###########################################################
# File: PicturePoker.py
#
# Description: Game logic for Luigi's Casino Picture Poker
###########################################################

import random
from collections import Counter


class PicturePoker:
    CARD_W = 136
    CARD_H = 207
    GAP_X = 24
    GAP_Y = 24
    MARGIN_X = 32
    MARGIN_Y = 32

    SYMBOLS = ["cloud", "mushroom", "flower", "luigi", "mario", "star"]

    # best to worst ordering for tie resolution.
    SYMBOL_ORDER = {
        "cloud": 0,
        "mushroom": 1,
        "flower": 2,
        "luigi": 3,
        "mario": 4,
        "star": 5,
    }

    HAND_RANKS = {
        "junk": 0,
        "one_pair": 1,
        "two_pair": 2,
        "three_kind": 3,
        "full_house": 4,
        "four_kind": 5,
        "five_kind": 6,
    }

    HAND_NAMES = {
        "junk": "Junk",
        "one_pair": "One Pair",
        "two_pair": "Two Pair",
        "three_kind": "Three of a Kind",
        "full_house": "Full House",
        "four_kind": "Four of a Kind",
        "five_kind": "Five of a Kind",
    }

    MULTIPLIER = {
        "one_pair": 2,
        "two_pair": 3,
        "three_kind": 4,
        "full_house": 6,
        "four_kind": 8,
        "five_kind": 16,
    }

    def __init__(self, starting_coins: int = 0, starting_stars: int = 0):
        # starting_coins kept for backwards compatibility
        # real balance lives in EconomyManager
        # If we want to use stars for auto betting in some we can later
        self.starting_coins = starting_coins
        self.starting_stars = starting_stars
        self.reset()

    def reset(self):
        self.stars = self.starting_stars
        self.round = 0
        self.deck = []
        self.player_hand = []
        self.luigi_hand = []
        self.bet = 0
        self.result = None

    def _build_deck(self):
        self.deck = []
        for sym in self.SYMBOLS:
            self.deck.extend([sym] * 5)
        random.shuffle(self.deck)

    def _draw_cards(self, n: int) -> list[str]:
        drawn = self.deck[:n]
        self.deck = self.deck[n:]
        return drawn

    def start_round(self, forced_bet: int | None = None):
        self.round += 1
        self._build_deck()
        if forced_bet is not None:
            self.bet = forced_bet
        elif self.bet <= 0:
            self.bet = self._min_bet()
        self.player_hand = self._draw_cards(5)
        self.luigi_hand = self._draw_cards(5)
        self.result = None

    def _min_bet(self) -> int:
        return min(1 + self.stars // 5, 4)

    def player_discard(self, indices: list[int]):
        if not indices:
            return
        for i in indices:
            if 0 <= i < len(self.player_hand):
                self.player_hand[i] = self._draw_cards(1)[0]

    def luigi_discard(self):
        counts = Counter(self.luigi_hand)
        keep = {sym for sym, cnt in counts.items() if cnt > 1}

        new_hand = []
        for card in self.luigi_hand:
            if card in keep:
                new_hand.append(card)
            else:
                new_hand.append(self._draw_cards(1)[0])
        self.luigi_hand = new_hand

    def _hand_signature(self, hand: list[str]) -> tuple[int, ...]:
        """Build a tie break signature: group by count, then by Luigi's ranking order."""
        counts = Counter(hand)
        sorted_symbols = sorted(
            counts.items(),
            key=lambda item: (-item[1], self.SYMBOL_ORDER[item[0]]),
        )

        signature: list[int] = []
        for symbol, count in sorted_symbols:
            symbol_value = self.SYMBOL_ORDER[symbol]
            signature.extend([symbol_value] * count)
        return tuple(signature)

    def evaluate_hand(self, hand: list[str]) -> tuple[int, str]:
        counts = Counter(hand).values()
        count_sorted = sorted(counts, reverse=True)

        if 5 in count_sorted:
            return self.HAND_RANKS["five_kind"], "five_kind"
        if 4 in count_sorted:
            return self.HAND_RANKS["four_kind"], "four_kind"
        if 3 in count_sorted and 2 in count_sorted:
            return self.HAND_RANKS["full_house"], "full_house"
        if 3 in count_sorted:
            return self.HAND_RANKS["three_kind"], "three_kind"
        if count_sorted.count(2) == 2:
            return self.HAND_RANKS["two_pair"], "two_pair"
        if 2 in count_sorted:
            return self.HAND_RANKS["one_pair"], "one_pair"
        return self.HAND_RANKS["junk"], "junk"

    def resolve_round(self):
        p_val, p_rank = self.evaluate_hand(self.player_hand)
        l_val, l_rank = self.evaluate_hand(self.luigi_hand)

        if p_val > l_val:
            mult = self.MULTIPLIER.get(p_rank, 0)
            winnings = self.bet * mult
            self.stars += 1
            self.result = {
                "outcome": "win",
                "player_rank": p_rank,
                "luigi_rank": l_rank,
                "coins": winnings,
                "stars": self.stars,
                "bet": self.bet,
            }

        elif p_val < l_val:
            if self.stars > 0:
                self.stars -= 1
            self.result = {
                "outcome": "lose",
                "player_rank": p_rank,
                "luigi_rank": l_rank,
                "coins": self.bet,
                "stars": self.stars,
                "bet": self.bet,
            }

        else:
            p_signature = self._hand_signature(self.player_hand)
            l_signature = self._hand_signature(self.luigi_hand)

            if p_signature < l_signature:
                mult = self.MULTIPLIER.get(p_rank, 0)
                winnings = self.bet * mult
                self.stars += 1
                self.result = {
                    "outcome": "win",
                    "player_rank": p_rank,
                    "luigi_rank": l_rank,
                    "coins": winnings,
                    "stars": self.stars,
                    "bet": self.bet,
                }
            elif p_signature > l_signature:
                if self.stars > 0:
                    self.stars -= 1
                self.result = {
                    "outcome": "lose",
                    "player_rank": p_rank,
                    "luigi_rank": l_rank,
                    "coins": self.bet,
                    "stars": self.stars,
                    "bet": self.bet,
                }
            else:
                self.result = {
                    "outcome": "tie",
                    "player_rank": p_rank,
                    "luigi_rank": l_rank,
                    "coins": 0,
                    "stars": self.stars,
                    "bet": self.bet,
                }

        return self.result

    def get_slot_rect(self, pos: int, dealer: bool = False) -> tuple[int, int, int, int]:
        x = self.MARGIN_X + pos * (self.CARD_W + self.GAP_X)
        if dealer:
            y = self.MARGIN_Y
        else:
            y = self.MARGIN_Y + self.CARD_H + (self.GAP_Y * 2)
        return x, y, self.CARD_W, self.CARD_H