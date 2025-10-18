###########################################################
# File: PairAGone.py
#
# Description: Game logic for Luigi's Casino Pair-a-Gone
###########################################################

import random
from casinogames.core.BaseGame import BaseGame


class PairAGone(BaseGame):
    GAME_KEY = "pairagone"
    COLS = 5
    ROWS = 4

    BASE_SYMBOLS = ["mario", "luigi", "mushroom", "flower", "star", "cloud"]
    EXTRA_SYMBOLS = ["goomba", "bowser", "boo", "yoshi"]
    STAR_THRESHOLDS = [1, 3, 5, 7]  # star milestones to unlock extra symbols

    def __init__(
        self,
        player_id: int,
        bet: int,
        *,
        initial_stars: int = 0,
    ):
        super().__init__(player_id)
        self.bet = max(1, bet)

        # progression state
        self.stars = max(0, int(initial_stars))
        self.session_stars = 0
        self.level = 1
        self.unlocked = set(self.BASE_SYMBOLS)
        self._apply_initial_unlocks()

        # round state
        self.deck = []
        self.board = []
        self.selected = []
        self.total_slots = self.COLS * self.ROWS  # 20 visible
        self.total_cards = 0

        self._build_deck()
        self._deal_board()

    ###########################################################
    # Deck & board generation (finite 36-card model)
    ###########################################################
    def _build_deck(self):
        cards_per_symbol = 6
        self.deck = []
        for sym in sorted(self.unlocked):
            self.deck.extend([sym] * cards_per_symbol)

        random.shuffle(self.deck)
        self.total_cards = len(self.deck)

    def _deal_board(self):
        draw_count = min(self.total_slots, len(self.deck))
        self.board = [self.deck.pop() for _ in range(draw_count)]

        # pad with None if deck < 20
        while len(self.board) < self.total_slots:
            self.board.append(None)

    def prepare_next_round(self):
        self.selected.clear()
        self._build_deck()
        self._deal_board()

    ###########################################################
    # Core logic
    ###########################################################
    def pos_to_rc(self, pos: int):
        return divmod(pos, self.COLS)

    def get_symbol(self, pos: int):
        return self.board[pos]

    def select_card(self, pos: int):
        if pos < 0 or pos >= len(self.board) or self.board[pos] is None:
            return None
        self.selected.append(pos)
        if len(self.selected) == 2:
            a, b = self.selected
            self.selected = []
            return self.check_match(a, b)
        return None

    def check_match(self, a: int, b: int):
        if self.board[a] is None or self.board[b] is None:
            return False
        if self.board[a] != self.board[b]:
            return False

        ra, ca = self.pos_to_rc(a)
        rb, cb = self.pos_to_rc(b)
        if abs(ra - rb) <= 1 and abs(ca - cb) <= 1:
            self.remove_and_fall([a, b])
            return True
        return False

    ###########################################################
    # Removal, gravity, and refill
    ###########################################################
    def remove_and_fall(self, positions: list[int]):
        # Remove matched cards
        for pos in positions:
            if 0 <= pos < len(self.board):
                self.board[pos] = None

        # Collapse remaining non-empty slots (top to bottom)
        compacted = [card for card in self.board if card is not None]

        new_cards = []

        # Fill until board is full OR deck runs out
        while len(compacted) < self.total_slots and self.deck:
            sym = self.deck.pop()
            new_idx = len(compacted)
            compacted.append(sym)
            new_cards.append((new_idx, sym))

        # Finalize board: pad with None if deck ran out
        self.board = compacted + [None] * (self.total_slots - len(compacted))

        # Only return actual new cards that were dealt (may be empty)
        return new_cards

    ###########################################################
    # State helpers
    ###########################################################
    def remaining_in_deck(self) -> int:
        return len(self.deck)

    def remaining_total(self) -> int:
        on_board = sum(1 for c in self.board if c is not None)
        return on_board + len(self.deck)

    def is_board_cleared(self):
        return all(v is None for v in self.board) and not self.deck

    def has_possible_moves(self) -> bool:
        for i in range(len(self.board)):
            symbol = self.board[i]
            if not symbol:
                continue
            r, c = self.pos_to_rc(i)
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if dr == 0 and dc == 0:
                        continue
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < self.ROWS and 0 <= nc < self.COLS:
                        idx = nr * self.COLS + nc
                        if self.board[idx] == symbol:
                            return True
        return False

    ###########################################################
    # Progression system
    ###########################################################
    def handle_game_end(self, won: bool):
        if won:
            self.stars += 1
            self.session_stars += 1
            self._check_unlock_progression()
        else:
            self.stars = max(0, self.stars - 1)
            self.session_stars = max(0, self.session_stars - 1)

    def _apply_initial_unlocks(self):
        """
        Unlock symbols based on any carry-over stars so the deck reflects the current progression.
        """
        self.level = 1
        for idx, threshold in enumerate(self.STAR_THRESHOLDS):
            if self.stars >= threshold:
                self.unlocked.add(self.EXTRA_SYMBOLS[idx])
                self.level += 1

    def _check_unlock_progression(self):
        for i, threshold in enumerate(self.STAR_THRESHOLDS):
            sym = self.EXTRA_SYMBOLS[i]
            if self.stars >= threshold and sym not in self.unlocked:
                self.unlocked.add(sym)
                print(f"[PairAGone] unlocked new symbol: {sym}")
                self.level += 1
