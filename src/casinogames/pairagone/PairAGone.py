###########################################################
# File: PairAGone.py
#
# Description: Game logic for Luigi's Casino Pair-a-Gone
###########################################################

import random


class PairAGone:
    GAME_KEY = "pairagone"
    COLS = 5
    ROWS = 4

    BASE_SYMBOLS = ["mario", "luigi", "mushroom", "flower", "star", "cloud"]
    EXTRA_SYMBOLS = ["goomba", "bowser", "boo", "yoshi"]
    STAR_THRESHOLDS = [1, 3, 5, 7]  # star milestones to unlock extra symbols

    def __init__(
        self,
        bet: int,
        *,
        initial_stars: int = 0,
    ):
        self.bet = max(1, bet)

        # progression state
        self.stars = max(0, int(initial_stars))
        self.session_stars = 0
        self.level = 1
        self.unlocked = set(self.BASE_SYMBOLS)
        self._sync_unlocks()

        # round state
        self.deck = []
        self.board = []
        self.selected = []
        self.total_slots = self.COLS * self.ROWS  # 20 visible

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

    def _deal_board(self):
        draw_count = min(self.total_slots, len(self.deck))
        self.board = [self.deck.pop() for _ in range(draw_count)]

        # pad with None if deck < 20
        while len(self.board) < self.total_slots:
            self.board.append(None)

    def pos_to_rc(self, pos: int):
        return divmod(pos, self.COLS)

    def is_match(self, a: int, b: int) -> bool:
        symbol = self.board[a]
        if symbol is None or symbol != self.board[b]:
            return False
        ra, ca = self.pos_to_rc(a)
        rb, cb = self.pos_to_rc(b)
        return abs(ra - rb) <= 1 and abs(ca - cb) <= 1

    def check_match(self, a: int, b: int):
        if not self.is_match(a, b):
            return False
        self.remove_and_fall([a, b])
        return True

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

    def is_board_cleared(self):
        return all(v is None for v in self.board) and not self.deck

    def has_possible_moves(self) -> bool:
        return any(
            symbol and self._has_matching_neighbor(i, symbol)
            for i, symbol in enumerate(self.board)
        )

    def _has_matching_neighbor(self, index, symbol):
        row, col = self.pos_to_rc(index)
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                nr, nc = row + dr, col + dc
                if (dr or dc) and 0 <= nr < self.ROWS and 0 <= nc < self.COLS:
                    if self.board[nr * self.COLS + nc] == symbol:
                        return True
        return False

    ###########################################################
    # Progression system
    ###########################################################
    def handle_game_end(self, won: bool):
        if won:
            self.stars += 1
            self.session_stars += 1
        else:
            self.stars = max(0, self.stars - 1)
            self.session_stars = max(0, self.session_stars - 1)
        self._sync_unlocks()

    def _sync_unlocks(self):
        previous_unlocked = getattr(self, "unlocked", set()).copy()
        self.unlocked = set(self.BASE_SYMBOLS)
        self.level = 1
        for idx, threshold in enumerate(self.STAR_THRESHOLDS):
            symbol = self.EXTRA_SYMBOLS[idx]
            if self.session_stars >= threshold:
                self.unlocked.add(symbol)
                if symbol not in previous_unlocked:
                    print(f"[PairAGone] unlocked new symbol this session: {symbol}")
                self.level += 1
