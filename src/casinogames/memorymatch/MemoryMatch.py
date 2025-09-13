# casinogames/memorymatch/MemoryMatch.py

import random
from typing import List, Tuple

class MemoryMatch:
    def __init__(self, player_id: int):
        self.player_id = player_id
        self.stars = 0
        self.bet_coins = 3
        self.remaining_coins = 3
        self.board = []           # cards as [(symbol, is_flipped, is_matched)]
        self.symbols = []
        self.revealed = []        # positions currently flipped
        self.generate_board()

    def get_difficulty(self) -> Tuple[int, List[str]]:
        #Decide number of cards + symbols based on stars earned.
        if self.stars < 5:
            return 8, ["cloud", "mushroom", "flower", "star"]
        elif self.stars < 10:
            return 12, ["cloud", "mushroom", "flower", "star", "luigi", "mario"]
        elif self.stars < 15:
            return 16, ["cloud", "mushroom", "flower", "star", "luigi", "mario", "goomba", "bowser"]
        else:
            return 20, ["cloud", "mushroom", "flower", "star", "luigi", "mario", "goomba", "bowser", "boo", "yoshi"]

    def generate_board(self):
        num_cards, symbols = self.get_difficulty()
        self.symbols = symbols

        # Choose pairs
        selected = symbols.copy()
        while len(selected) * 2 > num_cards:
            selected.pop()  # trim if too many

        cards = selected * 2
        random.shuffle(cards)

        self.board = [(s, False, False) for s in cards]
        self.revealed = []

    def flip_card(self, pos: int) -> bool:
        #Flip a card at pos. Returns True if valid flip, False otherwise.
        if pos < 0 or pos >= len(self.board):
            return False
        symbol, flipped, matched = self.board[pos]
        if flipped or matched:
            return False

        # Flip
        self.board[pos] = (symbol, True, matched)
        self.revealed.append(pos)
        return True

    def check_match(self) -> bool:
        #Check if two revealed cards match.
        if len(self.revealed) < 2:
            return None

        a, b = self.revealed[-2], self.revealed[-1]
        sa, _, _ = self.board[a]
        sb, _, _ = self.board[b]

        if sa == sb:
            # Mark matched
            self.board[a] = (sa, True, True)
            self.board[b] = (sb, True, True)
            return True
        else:
            # Cost 1 coin
            self.remaining_coins -= 1
            return False

    def hide_unmatched(self):
        #Turn unmatched revealed cards back face down.
        for pos in self.revealed[-2:]:
            sym, flipped, matched = self.board[pos]
            if not matched:
                self.board[pos] = (sym, False, matched)

    def is_game_over(self) -> bool:
        return self.remaining_coins <= 0 or all(m for _, _, m in self.board)

    def award_star(self):
        self.stars += 1
        # Refill coins based on rules
        self.remaining_coins = self.bet_coins * 2
