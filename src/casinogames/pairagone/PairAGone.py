import random

class PairAGone:
    COLS = 5
    ROWS = 4
    CARD_W = 136
    CARD_H = 207
    GAP_X = 24
    GAP_Y = 24
    MARGIN_X = 32
    MARGIN_Y = 32

    def __init__(self, player_id: int, symbols=None):
        self.player_id = player_id
        self.symbols = symbols or ["cloud", "mushroom", "flower", "star", "luigi", "mario", "goomba", "bowser"]
        self.board = []   # 2D list of symbols
        self.selected = []  # currently selected positions
        self.generate_board()

    def generate_board(self):
        self.board = [
            [random.choice(self.symbols) for _ in range(self.COLS)]
            for _ in range(self.ROWS)
        ]

    def pos_to_rc(self, pos: int):
        return divmod(pos, self.COLS)

    def get_symbol(self, pos: int):
        r, c = self.pos_to_rc(pos)
        return self.board[r][c]

    def select_card(self, pos: int):
        self.selected.append(pos)
        if len(self.selected) == 2:
            a, b = self.selected
            self.selected = []
            return self.check_match(a, b)
        return None

    def check_match(self, a: int, b: int):
        ra, ca = self.pos_to_rc(a)
        rb, cb = self.pos_to_rc(b)
        if self.board[ra][ca] != self.board[rb][cb]:
            return False
        if abs(ra - rb) <= 1 and abs(ca - cb) <= 1:
            self.remove_and_fall([a, b])
            return True
        return False

    def remove_and_fall(self, positions: list[int]):
        # set to None
        for pos in positions:
            r, c = self.pos_to_rc(pos)
            self.board[r][c] = None
        # collapse per column
        for c in range(self.COLS):
            col_vals = [self.board[r][c] for r in range(self.ROWS) if self.board[r][c] is not None]
            while len(col_vals) < self.ROWS:
                col_vals.insert(0, random.choice(self.symbols))
            for r in range(self.ROWS):
                self.board[r][c] = col_vals[r]

    def is_board_cleared(self):
        return all(self.board[r][c] is None for r in range(self.ROWS) for c in range(self.COLS))

    def get_slot_rect(self, index: int) -> tuple[int, int, int, int]:
        row, col = divmod(index, self.COLS)
        x = self.MARGIN_X + col * (self.CARD_W + self.GAP_X)
        y = self.MARGIN_Y + row * (self.CARD_H + self.GAP_Y)
        return x, y, self.CARD_W, self.CARD_H
