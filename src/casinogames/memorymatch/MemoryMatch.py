import random
from typing import List, Tuple
from casinogames.core.BaseGame import BaseGame

class MemoryMatch(BaseGame):
    # Board layout constants
    COLS = 4
    ROWS = 2
    CARD_W = 136
    CARD_H = 207
    GAP_X = 24
    GAP_Y = 24
    MARGIN_X = 32
    MARGIN_Y = 32

    def __init__(self, player_id: int, bet: int, base_attempts: int = 3):
        self.player_id = player_id
        self.bet = max(1, bet)
        self.base_attempts = max(1, base_attempts)
        self.remaining_attempts = self.base_attempts
        self.stars = 0
        self.board = []           # [(symbol, is_flipped, is_matched)]
        self.symbols = []
        self.revealed = []        # positions currently flipped
        self.generate_board()

    def get_difficulty(self) -> Tuple[int, List[str]]:
        # Decide number of cards + symbols based on stars earned
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
        # Flip a card at pos. Returns True if valid flip, False otherwise
        if pos < 0 or pos >= len(self.board):
            return False
        symbol, flipped, matched = self.board[pos]
        if flipped or matched:
            return False

        self.board[pos] = (symbol, True, matched)
        self.revealed.append(pos)
        return True

    def check_match(self) -> bool:
        # Check if two revealed cards match
        if len(self.revealed) < 2:
            return None

        a, b = self.revealed[-2], self.revealed[-1]
        sa, _, _ = self.board[a]
        sb, _, _ = self.board[b]

        # Mark matched
        if sa == sb:
            self.board[a] = (sa, True, True)
            self.board[b] = (sb, True, True)
            return True
        else:
            self.remaining_attempts -= 1
            return False

    def hide_unmatched(self):
        # Turn unmatched revealed cards back face down
        for pos in self.revealed[-2:]:
            sym, flipped, matched = self.board[pos]
            if not matched:
                self.board[pos] = (sym, False, matched)

    def is_game_over(self) -> bool:
        return self.remaining_attempts <= 0 or all(m for _, _, m in self.board)

    def award_star(self):
        self.stars += 1
        self.remaining_attempts = self.base_attempts * 2

    def is_board_cleared(self) -> bool:
        # True if all cards matched
        return all(m for _, _, m in self.board)

    def next_level(self):
        # Award star and generate a next board
        self.award_star()
        self.generate_board()