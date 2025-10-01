###########################################################
# File: LuckyStars.py
#
# Description: Game logic for Luigi’s Casino Lucky Stars
###########################################################

import random

class LuckyStars:
    CARD_W = 136
    CARD_H = 207
    GAP_X = 80
    GAP_Y = 24
    MARGIN_X = 32
    MARGIN_Y = 32

    def __init__(self, starting_coins: int = 10):
        self.starting_coins = starting_coins
        self.reset()

    def reset(self):
        #Reset game state for a fresh session.
        self.coins = self.starting_coins
        self.round = 0
        self.last_result = None
        self.left_card = None
        self.right_card = None
        self.picked = None   # 0 = left, 1 = right
        self.finished = False


    def deal_round(self):
        
        #Deal two different cards by drawing from a 1–5 deck
        #shuffling [1,2,3,4,5] and picking the first two
        
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
        #Player picks a card: 0 = left, 1 = right.
        if pos not in (0, 1):
            raise ValueError("pos must be 0 or 1 ")
        if self.left_card is None or self.right_card is None:
            raise RuntimeError("Must call deal_round() before pick_card().")
        self.picked = pos

    def resolve_round(self):
        
        #Reveal both cards, update coins, and return outcome.
        #Returns a dict with details: player_val, dealer_val, coins, outcome
        
        if self.picked is None:
            raise RuntimeError("Player must pick a card before resolving.")

        # Determine values
        player_val = self.left_card if self.picked == 0 else self.right_card
        dealer_val = self.right_card if self.picked == 0 else self.left_card

        # Compare and update coins
        if player_val > dealer_val:
            self.coins += 2
            self.last_result = "win"
        else:
            self.coins -= 2
            self.last_result = "lose"

        if self.coins <= 0:
            self.finished = True

        return {
            "player_val": player_val,
            "dealer_val": dealer_val,
            "coins": self.coins,
            "outcome": self.last_result,
            "finished": self.finished,
        }

    def get_coins(self) -> int:
        return self.coins

    def is_over(self) -> bool:
        return self.finished
