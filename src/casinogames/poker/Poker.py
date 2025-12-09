##############################################################
# File: Poker.py
#
# Description: Core 5-card draw poker model.
# single discard/redraw, dealer draw logic, evaluates
# standard hand ranking with tie-breakers, and round resolvers
################################################################

from __future__ import annotations

from collections import Counter
from typing import List, Sequence, Tuple

from casinogames.cards.standard_deck import Card, build_deck, draw_cards


RANK_ORDER = {
    "2": 2,
    "3": 3,
    "4": 4,
    "5": 5,
    "6": 6,
    "7": 7,
    "8": 8,
    "9": 9,
    "10": 10,
    "J": 11,
    "Q": 12,
    "K": 13,
    "A": 14,
}


class Poker:
    GAME_KEY = "poker"

    def __init__(self, bet: int):
        self.bet = max(1, int(bet))
        self.deck: List[Card] = []
        self.player_hand: List[Card] = []
        self.dealer_hand: List[Card] = []
        self.player_discarded = False
        self.dealer_discarded = False
        self.result = None
        self.start_round()

    # -----------------------------------------------------
    # Round setup
    # -----------------------------------------------------
    def start_round(self):
        self.deck = build_deck()
        self.player_hand = draw_cards(self.deck, 5)
        self.dealer_hand = draw_cards(self.deck, 5)
        self.player_discarded = False
        self.dealer_discarded = False
        self.result = None

    # -----------------------------------------------------
    # Discards
    # -----------------------------------------------------
    def player_discard(self, indices: Sequence[int]):
        if self.player_discarded:
            return
        indices = sorted(set(i for i in indices if 0 <= i < len(self.player_hand)))
        for idx in indices:
            self.player_hand[idx] = draw_cards(self.deck, 1)[0]
        self.player_discarded = True

    def dealer_discard(self):
        if self.dealer_discarded:
            return
        keep_mask = self._dealer_keep_mask(self.dealer_hand)
        for i, keep in enumerate(keep_mask):
            if keep:
                continue
            replacement = draw_cards(self.deck, 1)
            if replacement:
                self.dealer_hand[i] = replacement[0]
        self.dealer_discarded = True

    # Simple heuristic: keep pairs or better, keep four-to-a-flush,
    # keep open-ended four-to-a-straight, else keep high cards (J+)
    def _dealer_keep_mask(self, hand: List[Card]) -> List[bool]:
        ranks = [c.rank for c in hand]
        suits = [c.suit for c in hand]
        rank_counts = Counter(ranks)
        suit_counts = Counter(suits)
        keep = [False] * len(hand)

        # Keep any part of pairs/trips/quads
        for i, c in enumerate(hand):
            if rank_counts[c.rank] >= 2:
                keep[i] = True

        # Keep four to a flush
        flush_suit = next((s for s, cnt in suit_counts.items() if cnt >= 4), None)
        if flush_suit:
            for i, c in enumerate(hand):
                if c.suit == flush_suit:
                    keep[i] = True

        # Keep high cards if nothing else
        if not any(keep):
            for i, c in enumerate(hand):
                if RANK_ORDER.get(c.rank, 0) >= 11:
                    keep[i] = True

        return keep

    # -----------------------------------------------------
    # Hand evaluation
    # -----------------------------------------------------
    @staticmethod
    def _is_straight(values: List[int]) -> Tuple[bool, int]:
        """Return (is_straight, high_card_value). Handles wheel (A-5)."""
        uniq = sorted(set(values))
        if len(uniq) < 5:
            return False, 0
        # normal
        if max(uniq) - min(uniq) == 4 and len(uniq) == 5:
            return True, max(uniq)
        # wheel straight (A-2-3-4-5)
        if set(uniq) == {14, 2, 3, 4, 5}:
            return True, 5
        return False, 0

    @classmethod
    def _evaluate_hand(cls, hand: List[Card]) -> Tuple[int, List[int], List[int]]:
        ranks = [c.rank for c in hand]
        suits = [c.suit for c in hand]
        values = [RANK_ORDER[r] for r in ranks]
        rank_counts = Counter(values)
        suit_counts = Counter(suits)

        is_flush = max(suit_counts.values()) == 5
        is_straight, straight_high = cls._is_straight(values)

        # group by count then value desc
        groups = sorted(
            rank_counts.items(),
            key=lambda item: (-item[1], -item[0]),
        )
        ordered_values = [val for val, _ in groups for _ in range(rank_counts[val])]

        if is_straight and is_flush:
            return 8, [straight_high], ordered_values
        if 4 in rank_counts.values():
            four_val = next(v for v, c in rank_counts.items() if c == 4)
            kicker = [v for v in ordered_values if v != four_val]
            return 7, [four_val], kicker
        if sorted(rank_counts.values()) == [2, 3]:
            three_val = next(v for v, c in rank_counts.items() if c == 3)
            pair_val = next(v for v, c in rank_counts.items() if c == 2)
            return 6, [three_val, pair_val], ordered_values
        if is_flush:
            return 5, sorted(values, reverse=True), ordered_values
        if is_straight:
            return 4, [straight_high], ordered_values
        if 3 in rank_counts.values():
            three_val = next(v for v, c in rank_counts.items() if c == 3)
            kickers = sorted([v for v in values if v != three_val], reverse=True)
            return 3, [three_val] + kickers, ordered_values
        pairs = [v for v, c in rank_counts.items() if c == 2]
        if len(pairs) == 2:
            high_pair, low_pair = sorted(pairs, reverse=True)
            kicker = max(v for v in values if v not in pairs)
            return 2, [high_pair, low_pair, kicker], ordered_values
        if len(pairs) == 1:
            pair_val = pairs[0]
            kickers = sorted([v for v in values if v != pair_val], reverse=True)
            return 1, [pair_val] + kickers, ordered_values
        return 0, sorted(values, reverse=True), ordered_values

    # -----------------------------------------------------
    # Resolution
    # -----------------------------------------------------
    def resolve_round(self) -> dict:
        self.dealer_discard()

        p_rank, p_primary, p_kickers = self._evaluate_hand(self.player_hand)
        d_rank, d_primary, d_kickers = self._evaluate_hand(self.dealer_hand)

        player_sig = (p_rank, p_primary, p_kickers)
        dealer_sig = (d_rank, d_primary, d_kickers)

        if player_sig > dealer_sig:
            outcome = "win"
            payout = self.bet * 2
            net = self.bet
        elif player_sig < dealer_sig:
            outcome = "lose"
            payout = 0
            net = -self.bet
        else:
            outcome = "push"
            payout = self.bet
            net = 0

        self.result = {
            "outcome": outcome,
            "payout": int(payout),
            "net": int(net),
            "bet": self.bet,
            "player_rank": p_rank,
            "dealer_rank": d_rank,
            "player_hand": list(self.player_hand),
            "dealer_hand": list(self.dealer_hand),
        }
        return self.result
