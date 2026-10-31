"""Basic Red7 v1.2, one practice round, no advanced draws/scoring/odd powers.

Source: https://asmadigames.com/rules/Red7_Rules.pdf (Basic rules).
Cards use a color initial followed by rank: R7, O6, Y5, G4, B3, I2, V1.
"""
from copy import deepcopy
import random

COLORS = ('violet', 'indigo', 'blue', 'green', 'yellow', 'orange', 'red')
CODES = ('V', 'I', 'B', 'G', 'Y', 'O', 'R')
RULE_NAMES = {'red': 'Highest card', 'orange': 'Most of one number',
              'yellow': 'Most of one color', 'green': 'Most even cards',
              'blue': 'Most different colors', 'indigo': 'Longest run',
              'violet': 'Most cards below four'}
DECK = tuple(c+str(n) for c in CODES for n in range(1, 8))


def card_key(card):
    if card not in DECK:
        raise ValueError('Invalid Red7 card')
    return int(card[1]), CODES.index(card[0])


def color(card):
    card_key(card)
    return COLORS[CODES.index(card[0])]


def label(card):
    return f'{color(card).title()} {card[1]}'


def qualifying(palette, rule):
    """Select the best qualifying subset; the highest qualifying card breaks ties."""
    def strength(cards):
        return (len(cards), max((card_key(c) for c in cards), default=(0, -1)))
    if rule not in RULE_NAMES:
        raise ValueError('Invalid Red7 rule')
    if not palette:
        return []
    if rule == 'red':
        return [max(palette, key=card_key)]
    if rule == 'orange':
        groups = [[c for c in palette if c[1] == str(n)] for n in range(1, 8)]
    elif rule == 'yellow':
        groups = [[c for c in palette if c[0] == code] for code in CODES]
    elif rule == 'green':
        return sorted([c for c in palette if int(c[1]) % 2 == 0], key=card_key)
    elif rule == 'violet':
        return sorted([c for c in palette if int(c[1]) < 4], key=card_key)
    elif rule == 'blue':
        return sorted([max((c for c in palette if c[0] == code), key=card_key)
                       for code in CODES if any(c[0] == code for c in palette)], key=card_key)
    else:
        best_by_rank = {n: max((c for c in palette if int(c[1]) == n), key=card_key)
                        for n in range(1, 8) if any(int(c[1]) == n for c in palette)}
        groups, run = [], []
        for n in range(1, 8):
            if n in best_by_rank:
                run.append(best_by_rank[n])
            elif run:
                groups.append(run); run = []
        if run:
            groups.append(run)
    return sorted(max(groups, key=strength), key=card_key)


def palette_score(palette, rule):
    subset = qualifying(palette, rule)
    return (len(subset), max((card_key(c) for c in subset), default=(0, -1)))


class Red7:
    KIND = 'red7'
    RULES_VERSION = 'basic-v1.2-single-round'
    RULES = ('Red7 Basic v1.2 practice: seven private hand cards and one public palette '
             'card per player. Start under Red; the player after the initial leader goes first. '
             'Play one card to your palette, discard one to change the Canvas rule, or '
             'play then discard two distinct cards atomically. You must lead at turn end. '
             'Ties use the highest qualifying card, number before color: Red > Orange > '
             'Yellow > Green > Blue > Indigo > Violet. Green/Violet need at least one '
             'qualifying card. No hand means elimination. Concede is always available; '
             'the menu lists winning complete turns. Single round; no advanced draws, '
             'odd-card powers, scoring between rounds or community coins.')

    def __init__(self, players=(1, 0), seed=None):
        self.players = list(players)
        if (len(self.players) != 2 or len(set(self.players)) != 2
                or any(type(p) is not int or p < 0 for p in self.players)):
            raise ValueError('Two distinct nonnegative player IDs are required')
        self.deck = list(DECK)
        random.Random(seed).shuffle(self.deck)
        self.hands = {str(p): [self.deck.pop() for _ in range(7)] for p in self.players}
        self.palettes = {str(p): [self.deck.pop()] for p in self.players}
        self.canvas = []
        self.rule = 'red'
        initial_leader = max(self.players, key=lambda p: card_key(self.palettes[str(p)][0]))
        self.turn = next(p for p in self.players if p != initial_leader)
        self.result = None
        self.log = ['Start under Red: highest card. The player after the leader acts first.']

    @property
    def finished(self):
        return self.result is not None

    def _leads(self, player_id, palette, rule):
        score = palette_score(palette, rule)
        return score[0] > 0 and all(score > palette_score(self.palettes[str(p)], rule)
                                   for p in self.players if p != player_id)

    def _candidate(self, player_id, play=None, discard=None):
        palette = self.palettes[str(player_id)] + ([play] if play else [])
        rule = color(discard) if discard else self.rule
        return self._leads(player_id, palette, rule)

    def legal_actions(self, player_id):
        if self.finished or player_id != self.turn or player_id not in self.players:
            return []
        hand = self.hands[str(player_id)]
        actions = []
        for card in hand:
            if self._candidate(player_id, play=card):
                actions.append({'id': f'play:{card}', 'label': f'Play {label(card)}',
                                'group': 'Play a card', 'description': RULE_NAMES[self.rule]})
            if self._candidate(player_id, discard=card):
                actions.append({'id': f'rule:{card}', 'label': f'Change rule with {label(card)}',
                                'group': 'Change rule', 'description': RULE_NAMES[color(card)]})
            for discard in hand:
                if card != discard and self._candidate(player_id, play=card, discard=discard):
                    actions.append({'id': f'both:{card}:{discard}',
                        'label': f'Play {label(card)}; rule {label(discard)}', 'group': 'Play + change rule',
                        'description': RULE_NAMES[color(discard)]})
        return actions + [{'id': 'concede', 'label': 'Concede round', 'group': 'Concede',
                           'description': 'You lose this round; no community coins are involved.'}]

    def act(self, player_id, action_id):
        if action_id not in {a['id'] for a in self.legal_actions(player_id)}:
            raise ValueError('Choose a winning complete turn or concede; this action is unavailable')
        if action_id == 'concede':
            return self.concede(player_id)
        parts = action_id.split(':')
        play = parts[1] if parts[0] in ('play', 'both') else None
        discard = parts[-1] if parts[0] in ('rule', 'both') else None
        hand = self.hands[str(player_id)]
        self.log = []
        if play:
            hand.remove(play); self.palettes[str(player_id)].append(play)
            self.log.append(f'Seat {self.players.index(player_id)+1} played {label(play)}.')
        if discard:
            hand.remove(discard); self.canvas.append(discard); self.rule = color(discard)
            self.log.append(f'Canvas changed to {self.rule.title()}: {RULE_NAMES[self.rule]}.')
        subset = qualifying(self.palettes[str(player_id)], self.rule)
        self.log.append('Leading subset: ' + ', '.join(label(c) for c in subset) + '.')
        self.turn = next(p for p in self.players if p != player_id)
        if not self.hands[str(self.turn)]:
            self.concede(self.turn, reason='empty_hand')
        return self.view(player_id)

    def concede(self, player_id, reason='concession'):
        if self.finished or player_id not in self.players:
            raise ValueError('This player cannot concede this round')
        winner = next(p for p in self.players if p != player_id)
        self.result = {'winner': winner, 'reason': reason,
                       'scores': {str(p): int(p == winner) for p in self.players}}
        self.turn = None
        self.log.append(f'Seat {self.players.index(player_id)+1} eliminated ({reason}).')
        return self.view(player_id)

    def bot_action(self):
        """Only own hand and public palettes inform the deterministic policy."""
        actions = [a for a in self.legal_actions(self.turn) if a['id'] != 'concede']
        if not actions:
            return 'concede'
        def strength(action):
            parts = action['id'].split(':')
            play = parts[1] if parts[0] in ('play', 'both') else None
            discard = parts[-1] if parts[0] in ('rule', 'both') else None
            palette = self.palettes[str(self.turn)] + ([play] if play else [])
            rule = color(discard) if discard else self.rule
            # Preserve hand resources before maximizing the publicly visible score.
            return (parts[0] != 'both', palette_score(palette, rule))
        return max(actions, key=strength)['id']

    def view(self, viewer_id=None):
        return deepcopy({'kind': self.KIND, 'players': self.players, 'turn': self.turn,
            'phase': 'finished' if self.finished else 'turn',
            'hands': {str(p): self.hands[str(p)] if viewer_id == p else [None]*len(self.hands[str(p)])
                      for p in self.players},
            'table': [{'owner': p, 'cards': self.palettes[str(p)]} for p in self.players],
            'palettes': self.palettes, 'canvas': self.canvas, 'rule': self.rule,
            'rule_name': RULE_NAMES[self.rule],
            'qualifying': {str(p): qualifying(self.palettes[str(p)], self.rule) for p in self.players},
            'scores': {str(p): len(qualifying(self.palettes[str(p)], self.rule)) for p in self.players},
            'log': self.log, 'result': self.result, 'rules_version': self.RULES_VERSION})

    def to_dict(self):
        return deepcopy({'version': self.RULES_VERSION, 'players': self.players, 'hands': self.hands,
                         'palettes': self.palettes, 'deck': self.deck, 'canvas': self.canvas,
                         'rule': self.rule, 'turn': self.turn, 'result': self.result, 'log': self.log})

    @classmethod
    def from_dict(cls, state):
        if state.get('version') != cls.RULES_VERSION:
            raise ValueError('Unsupported Red7 save version')
        game = cls.__new__(cls)
        for name in ('players', 'hands', 'palettes', 'deck', 'canvas', 'rule', 'turn', 'result', 'log'):
            setattr(game, name, deepcopy(state[name]))
        return game
