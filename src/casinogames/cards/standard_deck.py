###########################################################
# File: standard_deck.py
#
# Description: Shared helpers for a standard 52-card deck.
#              Provides shuffling/drawing plus blackjack-
#              friendly value helpers
###########################################################

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple


RANKS: Sequence[str] = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
SUITS: Sequence[str] = ["hearts", "diamonds", "clubs", "spades"]

# display helpers for different presentation styles
SUIT_EMOJIS = {
    "hearts": "♥️",
    "diamonds": "♦️",
    "clubs": "♣️",
    "spades": "♠️",
}

SUIT_GLYPHS = {
    "hearts": "H",
    "diamonds": "D",
    "clubs": "C",
    "spades": "S",
}


@dataclass(frozen=True)
class Card:
    rank: str
    suit: str

    def label(self, *, use_emoji: bool = True) -> str:
        """Compact string for UI or logging."""
        suit_icon = SUIT_EMOJIS[self.suit] if use_emoji else SUIT_GLYPHS[self.suit]
        return f"{self.rank}{suit_icon}"


def build_deck(*, shuffled: bool = True) -> List[Card]:
    """Create a fresh 52-card deck."""
    deck = [Card(rank=rank, suit=suit) for suit in SUITS for rank in RANKS]
    if shuffled:
        random.shuffle(deck)
    return deck


def draw_cards(deck: List[Card], count: int = 1) -> List[Card]:
    """Remove and return up to `count` cards from the top of the deck."""
    count = max(0, int(count))
    drawn: List[Card] = []
    for _ in range(count):
        if not deck:
            break
        drawn.append(deck.pop(0))
    return drawn


def blackjack_values(card: Card) -> Tuple[int, int]:
    """Return (low, high) values for blackjack scoring."""
    rank = card.rank
    if rank == "A":
        return 1, 11
    if rank in {"J", "Q", "K"}:
        return 10, 10
    try:
        value = int(rank)
    except ValueError:
        value = 0
    return value, value


def best_blackjack_total(hand: Iterable[Card]) -> Tuple[int, bool]:
    """
    Compute the best total <= 21 if possible.

    Returns (total, is_soft) where is_soft is True when an Ace counts as 11.
    """
    totals: List[Tuple[int, bool]] = [(0, False)]
    for card in hand:
        low, high = blackjack_values(card)
        next_totals: List[Tuple[int, bool]] = []
        for total, soft in totals:
            next_totals.append((total + low, soft))
            if high != low:
                next_totals.append((total + high, True))
        totals = next_totals

    # Prefer the highest total <= 21, otherwise the minimum total.
    valid_totals = [t for t in totals if t[0] <= 21]
    if valid_totals:
        best_total, is_soft = max(valid_totals, key=lambda pair: (pair[0], pair[1]))
    else:
        best_total, is_soft = min(totals, key=lambda pair: pair[0]) if totals else (0, False)

    return best_total, is_soft


def format_hand(hand: Sequence[Card], *, use_emoji: bool = True, separator: str = " ") -> str:
    """Render a hand as a single string (e.g., 'A♠️ 10♦️ 7♥️')."""
    return separator.join(card.label(use_emoji=use_emoji) for card in hand)
