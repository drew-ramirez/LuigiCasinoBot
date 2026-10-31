"""Pure game rules. Rendering never draws or changes a game outcome."""
import random

SYMBOLS = ('star', 'mario', 'luigi', 'flower', 'mushroom', 'cloud')
POCKETS = tuple((color, symbol) for color in ('red', 'black') for symbol in SYMBOLS)
# Betting-board row order: red star/Mario/Luigi, red flower/mushroom/cloud,
# then the same two rows in black.
BET_GROUPS = {f'{c} {s}': (i,) for i, (c, s) in enumerate(POCKETS)}
BET_GROUPS.update({c: tuple(range(i * 6, i * 6 + 6)) for i, c in enumerate(('red', 'black'))})
for row in range(4):
    for col in range(2):
        a = row * 3 + col
        BET_GROUPS[f'split {a + 1}-{a + 2}'] = (a, a + 1)
for row in range(3):
    for col in range(3):
        a = row * 3 + col
        BET_GROUPS[f'split {a + 1}-{a + 4}'] = (a, a + 3)
for row in range(3):
    for col in range(2):
        a = row * 3 + col
        BET_GROUPS[f'corner {a + 1}/{a + 2}/{a + 4}/{a + 5}'] = (a, a + 1, a + 3, a + 4)

class Roulette:
    def __init__(self, bet, rng=None):
        if bet <= 0:
            raise ValueError('Wager must be positive')
        self.bet = bet
        self.rng = rng or random.SystemRandom()
        self.selection = 'red'
        self.result = None
        # The wager is a fixed budget, divided into at most five visible chips.
        # Every chip is placed before spinning; editing placements never charges again.
        count = min(5, bet)
        self.chips = [bet // count + (i < bet % count) for i in range(count)]
        self.placements = []
        self.balance_after_wager = None

    @property
    def ready(self):
        return len(self.placements) == len(self.chips)

    def place(self, selection):
        if self.result is not None or selection not in BET_GROUPS or self.ready:
            raise ValueError('No chip available or invalid placement')
        self.selection = selection
        self.placements.append(selection)

    def undo(self):
        if self.result is not None:
            raise ValueError('Round already finished')
        if self.placements:
            self.placements.pop()

    def clear(self):
        if self.result is not None:
            raise ValueError('Round already finished')
        self.placements.clear()

    def choose(self, selection):
        if self.result is not None or selection not in BET_GROUPS:
            raise ValueError('Invalid or finished bet')
        self.selection = selection
        self.placements = [selection] * len(self.chips)

    def spin(self):
        if self.result is None:
            if not self.ready:
                raise ValueError('Place all chips before spinning')
            pocket = self.rng.randrange(12)
            payout = sum(amount * (12 // len(BET_GROUPS[selection]))
                         for amount, selection in zip(self.chips, self.placements)
                         if pocket in BET_GROUPS[selection])
            self.result = {'pocket': pocket, 'payout': payout}
        return self.result

class Slots:
    SYMBOLS = ('mushroom', 'flower', 'star', 'feather', 'egg', 'superstar')
    PAYTABLE = dict(mushroom=10, flower=10, star=15, feather=5, egg=5, superstar=20)

    def __init__(self, bet, rng=None):
        if bet <= 0:
            raise ValueError('Wager must be positive')
        self.bet = bet
        self.rng = rng or random.SystemRandom()
        self.reels = [None, None, None]
        self.result = None

    @classmethod
    def multiplier(cls, reels):
        if len(reels) != 3 or any(s not in cls.SYMBOLS for s in reels):
            raise ValueError('Three stopped reels required')
        wilds = reels.count('superstar')
        ordinary = set(reels) - {'superstar'}
        if wilds == 3:
            return 20
        if wilds == 2:
            return 4
        if len(ordinary) == 1:
            return cls.PAYTABLE[ordinary.pop()]
        return {0: 0, 1: 2, 2: 4}[wilds]

    def stop(self, index):
        if index not in range(3):
            raise ValueError('Invalid reel')
        if self.reels[index] is None:
            self.reels[index] = self.rng.choice(self.SYMBOLS)
        if all(self.reels) and self.result is None:
            self.result = {'payout': self.bet * self.multiplier(self.reels)}
        return self.result
