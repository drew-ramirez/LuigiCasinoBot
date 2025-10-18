###########################################################
# File: LuckyStars.py
#
# Description: Game logic for Luigi's Casino Lucky Stars
###########################################################

import random
from typing import Optional


class LuckyStars:
    GAME_KEY = "luckystars"
    CARD_W = 136
    CARD_H = 207
    GAP_X = 80
    GAP_Y = 24
    MARGIN_X = 32
    MARGIN_Y = 32

    def __init__(self, bet: int, *, initial_stars: int = 0):
        self.bet = max(1, bet)
        self.stars = max(0, int(initial_stars))
        self.round = 0
        self.left_card: Optional[int] = None
        self.right_card: Optional[int] = None
        self.picked: Optional[int] = None
        self.finished = False

    def deal_round(self):
        if self.finished:
            return None, None

        self.round += 1
        deck = [1, 2, 3, 4, 5]
        random.shuffle(deck)

        self.left_card = deck[0]
        self.right_card = deck[1]
        self.picked = None

        return self.left_card, self.right_card

    def pick_card(self, pos: int):
        if pos not in (0, 1):
            raise ValueError("pos must be 0 or 1")
        if self.left_card is None or self.right_card is None:
            raise RuntimeError("Must call deal_round() before pick_card().")
        self.picked = pos

    def resolve_round(self):
        if self.picked is None:
            raise RuntimeError("Player must pick a card before resolving.")

        player_val = self.left_card if self.picked == 0 else self.right_card
        dealer_val = self.right_card if self.picked == 0 else self.left_card

        outcome = "win" if player_val > dealer_val else "lose"
        self.finished = True

        return {
            "player_val": player_val,
            "dealer_val": dealer_val,
            "bet": self.bet,
            "outcome": outcome,
        }

    def is_over(self) -> bool:
        return self.finished
