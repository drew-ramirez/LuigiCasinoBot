import random
from casinogames.core.BaseGame import BaseGame

class PairAGone(BaseGame):
    COLS = 5
    ROWS = 4

    def __init__(self, player_id: int, symbols=None):
        super().__init__(player_id)
        self.symbols = symbols or [
            "cloud", "mushroom", "flower", "star",
            "luigi", "mario", "goomba", "bowser"
        ]
        self.board = []     # flat list of symbols (len = ROWS * COLS)
        self.selected = []
        self.generate_board()

    def generate_board(self):
        self.board = [random.choice(self.symbols) for _ in range(self.COLS * self.ROWS)]

    def pos_to_rc(self, pos: int):
        return divmod(pos, self.COLS)

    def get_symbol(self, pos: int):
        return self.board[pos]

    def select_card(self, pos: int):
        self.selected.append(pos)
        if len(self.selected) == 2:
            a, b = self.selected
            self.selected = []
            return self.check_match(a, b)
        return None

    def check_match(self, a: int, b: int):
        if self.board[a] != self.board[b]:
            return False
        ra, ca = self.pos_to_rc(a)
        rb, cb = self.pos_to_rc(b)
        if abs(ra - rb) <= 1 and abs(ca - cb) <= 1:
            self.remove_and_fall([a, b])
            return True
        return False

    def remove_and_fall(self, positions: list[int]):
        # mark positions as None
        for pos in positions:
            self.board[pos] = None

        # compact board (remove None)
        compacted = [card for card in self.board if card is not None]

        # refill with new random cards at the end
        while len(compacted) < self.COLS * self.ROWS:
            compacted.append(random.choice(self.symbols))

        self.board = compacted

    def is_board_cleared(self):
        return all(v is None for v in self.board)

#Game lost checker
def has_possible_moves(self) -> bool:
    #Check if any adjacent pair is still possible.
    for i in range(len(self.board)):
        symbol = self.board[i]
        if not symbol:
            continue
        r, c = self.pos_to_rc(i)
        # look at neighbors
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr == 0 and dc == 0:
                    continue
                nr, nc = r + dr, c + dc
                if 0 <= nr < self.ROWS and 0 <= nc < self.COLS:
                    neighbor_index = nr * self.COLS + nc
                    if self.board[neighbor_index] == symbol:
                        return True
    return False