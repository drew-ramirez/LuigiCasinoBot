"""Score-only advanced Luigi modes; no wallet calls or unverifiable memory prizes."""
from copy import deepcopy
import random
import secrets

SYMBOLS = ['cloud', 'mushroom', 'flower', 'star', 'luigi', 'mario', 'goomba', 'bowser', 'boo', 'yoshi']
MEMORY_RULES = ('Memory Master casual: 16/18/20 cards at 0/5/10 Stars; 4/6/8 opening hints. '
                'Five mistakes end a board. Clear +1 Star; failure -1 (floor zero). '
                'Free score-only play. Known cards remain available: GIFs and screenshots can be replayed. '
                'Pause saves the same board; Finish saves your personal score.')
ENDLESS_RULES = ('Pair-a-Gone and On — bot progression v1: remove matching immediate neighbours '
                 'horizontally, vertically or diagonally; survivors compact in row order, replacements enter at the end. '
                 'Two removed cards = 2 points; no legal pair ends the run. Free, no coin rewards. '
                 'Adaptation: expand the refill pool with Luigi, Goomba, Bowser, Boo, Yoshi every 50 cleared cards; consume the saved batch before using shuffled '
                 'four-of-each refill batches. Original unlock thresholds/distribution remain unverified. '
                 'Pause and resume preserve the exact draw order. Finish submits the score once.')


def _tuples(value):
    return tuple(_tuples(v) for v in value) if isinstance(value, list) else value


class SavedRandomGame:
    def to_dict(self):
        state = deepcopy({k: v for k, v in self.__dict__.items() if k != 'rng'})
        state['rng_state'] = self.rng.getstate()
        state['version'] = 1
        return state

    @classmethod
    def from_dict(cls, state):
        data = deepcopy(state)
        if data.pop('version') != 1:
            raise ValueError('Unsupported saved rules version')
        rng_state = data.pop('rng_state')
        game = cls.__new__(cls)
        game.__dict__.update(data)
        game.rng = random.Random()
        game.rng.setstate(_tuples(rng_state))
        return game


class MemoryMaster(SavedRandomGame):
    def __init__(self, *, stars=0, seed=None):
        self.rng = random.Random(seed if seed is not None else secrets.randbits(128))
        self.stars = max(0, int(stars))
        self.score = 0
        self.clears = 0
        self.finished = False
        self.new_board()

    def new_board(self):
        tier = min(2, self.stars // 5)
        self.cols, self.rows = [(4, 4), (6, 3), (5, 4)][tier]
        pairs = 8 + tier
        self.board = SYMBOLS[:pairs] * 2
        self.rng.shuffle(self.board)
        self.hints = sorted(self.rng.sample(range(len(self.board)), 4 + tier * 2))
        self.known = {str(i): self.board[i] for i in self.hints}
        self.matched = []
        self.selected = []
        self.last_reveal = []
        self.mistakes = 0
        self.attempts = 0
        self.status = 'playing'
        self.last = 'Opening hints are saved in Known cards.'
        self.opening = True

    def choose(self, pos):
        if self.finished or self.status != 'playing':
            raise ValueError('Choose Next board or Finish.')
        if type(pos) is not int or not 0 <= pos < len(self.board) or pos in self.matched or pos in self.selected:
            raise ValueError('Choose a different unmatched card.')
        self.opening = False
        self.last_reveal = []
        self.known[str(pos)] = self.board[pos]
        self.selected.append(pos)
        self.last = f'{coordinate(pos, self.cols)}: {self.board[pos].title()}'
        if len(self.selected) < 2:
            return
        a, b = self.selected
        self.attempts += 1
        self.last_reveal = [a, b]
        self.last = f'{coordinate(a, self.cols)} {self.board[a]} / {coordinate(b, self.cols)} {self.board[b]}'
        if self.board[a] == self.board[b]:
            self.matched.extend([a, b])
            self.score += 2
            self.last += ' — Match!'
            if len(self.matched) == len(self.board):
                self.stars += 1
                self.clears += 1
                self.status = 'cleared'
        else:
            self.mistakes += 1
            self.last += ' — Mismatch.'
            if self.mistakes == 5:
                self.stars = max(0, self.stars - 1)
                self.status = 'failed'
        self.selected = []

    def next_board(self):
        if self.finished or self.status == 'playing':
            raise ValueError('Complete this board first.')
        self.new_board()

    def finish(self):
        self.finished = True
        self.status = 'finished'

    def public_state(self):
        visible = set(self.selected + self.last_reveal + (self.hints if self.opening else []))
        return {'cards': [symbol if i in visible else '' if i in self.matched else None
                          for i, symbol in enumerate(self.board)],
                'cols': self.cols, 'rows': self.rows, 'selected': list(self.selected),
                'stars': self.stars, 'mistakes': self.mistakes, 'score': self.score,
                'attempts': self.attempts, 'status': self.status, 'last': self.last}


class EndlessPairs(SavedRandomGame):
    def __init__(self, *, seed=None):
        self.rng = random.Random(seed if seed is not None else secrets.randbits(128))
        self.score = 0
        self.cols, self.rows = 5, 4
        self.deck = []
        self.selected = []
        self.finished = False
        self.reason = ''
        self.removed = []
        self.last = 'Select matching neighbours, including diagonals.'
        self.board = [self.draw() for _ in range(20)]
        self.check_stuck()

    @property
    def symbols(self):
        base = ['mario', 'mushroom', 'flower', 'star', 'cloud']
        return base + ['luigi', 'goomba', 'bowser', 'boo', 'yoshi'][:min(5, self.score // 50)]

    def draw(self):
        if not self.deck:
            self.deck = self.symbols * 4
            self.rng.shuffle(self.deck)
        return self.deck.pop()

    def adjacent(self, a, b):
        ar, ac = divmod(a, 5)
        br, bc = divmod(b, 5)
        return a != b and max(abs(ar-br), abs(ac-bc)) == 1

    def moves(self):
        return [(a, b) for a in range(20) for b in range(a+1, 20)
                if self.board[a] == self.board[b] and self.adjacent(a, b)]

    def check_stuck(self):
        if not self.moves():
            self.finish('stuck')

    def choose(self, pos):
        if self.finished:
            raise ValueError('This run has ended.')
        if type(pos) is not int or not 0 <= pos < 20:
            raise ValueError('Choose a card on this board.')
        self.removed = []
        if not self.selected:
            self.selected = [pos]
            return
        a = self.selected[0]
        if a == pos:
            self.selected = []
            return
        if self.board[a] != self.board[pos] or not self.adjacent(a, pos):
            raise ValueError('Cards must match and touch horizontally, vertically or diagonally.')
        self.score += 2
        self.removed = [a, pos]
        self.board = [v for i, v in enumerate(self.board) if i not in (a, pos)] + [self.draw(), self.draw()]
        self.selected = []
        self.last = f'{self.score} cards cleared. ' + ('Consider a break — Pause saves your run.' if self.score % 50 == 0 else '+2 points.')
        self.check_stuck()

    def finish(self, reason='voluntary'):
        if not self.finished:
            self.finished = True
            self.reason = reason
            self.last = f'Run ended ({reason}). Final score: {self.score}.'

    def public_state(self):
        return {'cards': list(self.board), 'cols': 5, 'rows': 4, 'selected': list(self.selected),
                'removed': list(self.removed), 'score': self.score, 'status': 'finished' if self.finished else 'playing', 'last': self.last}


def coordinate(pos, cols):
    row, col = divmod(pos, cols)
    return f'{chr(65 + row)}{col+1}'
