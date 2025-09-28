class BaseGame:
    COLS = 0
    ROWS = 0
    CARD_W = 136
    CARD_H = 207
    GAP_X = 24
    GAP_Y = 24
    MARGIN_X = 32
    MARGIN_Y = 32

    def __init__(self, player_id: int):
        self.player_id = player_id
        self.board = []
        self.selected = []

    def pos_to_rc(self, pos: int):
        return divmod(pos, self.COLS)

    def get_slot_rect(self, index: int):
        row, col = divmod(index, self.COLS)
        x = self.MARGIN_X + col * (self.CARD_W + self.GAP_X)
        y = self.MARGIN_Y + row * (self.CARD_H + self.GAP_Y)
        return x, y, self.CARD_W, self.CARD_H

    # These are game-specific and overridden in children:
    def generate_board(self): raise NotImplementedError
    def select_card(self, pos: int): raise NotImplementedError
