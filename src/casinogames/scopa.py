"""Two-player basic Scopa, one complete deal (casual score adaptation).

Rules: https://www.pagat.com/fishing/scopa.html . French-suited 40-card
representation: diamonds are coins; J/Q/K capture as 8/9/10. No wallet effects.
"""
from copy import deepcopy
import random

RANKS = ('A', '2', '3', '4', '5', '6', '7', 'J', 'Q', 'K')
SUITS = ('C', 'D', 'H', 'S')
DECK = [rank + suit for suit in SUITS for rank in RANKS]
PRIME = {'A': 16, '2': 12, '3': 13, '4': 14, '5': 15, '6': 18,
         '7': 21, 'J': 10, 'Q': 10, 'K': 10}


def value(card):
    return RANKS.index(card[:-1]) + 1


class Scopa:
    RULES_VERSION = 'basic-two-player-single-deal-v1'
    RULES = ('Scopa, one-deal practice: 40 cards; diamonds are coins, J=8/Q=9/K=10. '
             'Play one card. An equal single MUST be captured before a summing set; '
             'choose among legal captures. No capture leaves the card on the table. '
             'Hands refill to three after both empty. Sweeps score one, except the last play. '
             'Last capturer receives leftovers. Most cards, most coins, seven of coins and '
             'best primiera each score one; tied categories score neither. Primiera needs '
             'all four suits (7:21,6:18,A:16,5:15,4:14,3:13,2:12,faces:10). '
             'This casual game ends after one deal, rather than a match to 11. No coins wagered.')

    def __init__(self, players=(1, 0), seed=None):
        self.players = list(players)
        if len(self.players) != 2 or len(set(self.players)) != 2 or any(type(p) is not int or p < 0 for p in self.players):
            raise ValueError('Scopa needs two distinct player IDs')
        rng = random.Random(seed)
        while True:
            self.deck = list(DECK)
            rng.shuffle(self.deck)
            self.hands = {str(p): [] for p in self.players}
            self._deal()
            self.table = [self.deck.pop() for _ in range(4)]
            if sum(c[:-1] == 'K' for c in self.table) < 3:
                break
        self.turn = self.players[0]
        self.captured = {str(p): [] for p in self.players}
        self.sweeps = {str(p): 0 for p in self.players}
        self.last_capture = None
        self.log = ['Three cards each; four cards face up. Non-dealer plays first.']
        self.result = None
        self.phase = 'play'

    @property
    def finished(self):
        return self.result is not None

    def _deal(self):
        for _ in range(3):
            for p in self.players:
                self.hands[str(p)].append(self.deck.pop())

    def _captures(self, card):
        target = value(card)
        singles = [(c,) for c in self.table if value(c) == target]
        if singles:
            return singles
        # Positive card values prune long subsets before enumeration.
        candidates = [c for c in self.table if value(c) < target]
        found = []
        def search(start, remaining, chosen):
            if remaining == 0:
                found.append(tuple(chosen))
                return
            for i in range(start, len(candidates)):
                v = value(candidates[i])
                if v <= remaining:
                    search(i + 1, remaining - v, chosen + [candidates[i]])
        search(0, target, [])
        return found or [()]

    def legal_actions(self, player_id):
        if self.finished or player_id != self.turn:
            return []
        result = []
        for card in self.hands[str(player_id)]:
            for capture in self._captures(card):
                label = f'{card}: capture ' + ', '.join(capture) if capture else f'{card}: leave on table'
                result.append({'id': f'play:{card}:{",".join(capture)}', 'label': label[:100],
                               'group': card, 'description': f'Capture value {value(card)}; diamonds are coins.'})
        return result

    def act(self, player_id, action_id):
        if action_id not in {a['id'] for a in self.legal_actions(player_id)}:
            raise ValueError('Choose a legal capture from the current hand.')
        _, card, raw = action_id.split(':')
        capture = raw.split(',') if raw else []
        self.hands[str(player_id)].remove(card)
        if capture:
            self.captured[str(player_id)].extend([card] + capture)
            self.table = [c for c in self.table if c not in capture]
            self.last_capture = player_id
            final = not self.deck and not any(self.hands.values())
            sweep = not self.table and not final
            self.sweeps[str(player_id)] += int(sweep)
            message = f'{player_id} played {card}, captured {", ".join(capture)}' + (' — Scopa!' if sweep else '.')
        else:
            self.table.append(card)
            message = f'{player_id} left {card} on the table.'
        self.log = (self.log + [message])[-6:]
        self.turn = self.players[1 - self.players.index(player_id)]
        if not any(self.hands.values()):
            if self.deck:
                self._deal()
            else:
                self._finish()
        return self.view(player_id)

    def _finish(self):
        if self.last_capture is not None:
            self.captured[str(self.last_capture)].extend(self.table)
            self.table = []
        detail = {}
        for p in self.players:
            cards = self.captured[str(p)]
            prime = [max((PRIME[c[:-1]] for c in cards if c[-1] == suit), default=0) for suit in SUITS]
            detail[str(p)] = {'cards': len(cards), 'coins': sum(c.endswith('D') for c in cards),
                              'settebello': int('7D' in cards), 'primiera': sum(prime) if all(prime) else 0,
                              'sweeps': self.sweeps[str(p)]}
        scores = {str(p): self.sweeps[str(p)] + detail[str(p)]['settebello'] for p in self.players}
        for category in ('cards', 'coins', 'primiera'):
            a, b = map(str, self.players)
            if detail[a][category] != detail[b][category]:
                scores[a if detail[a][category] > detail[b][category] else b] += 1
        best = max(scores.values())
        winners = [p for p in self.players if scores[str(p)] == best]
        self.result = {'winner': winners[0] if len(winners) == 1 else None, 'scores': scores,
                       'breakdown': detail, 'reason': 'single deal completed', 'practice_only': True}
        self.phase = 'finished'
        self.turn = None

    def concede(self, player_id):
        if player_id not in self.players or self.finished:
            raise ValueError('No active seat to concede.')
        self.result = {'winner': self.players[1-self.players.index(player_id)], 'reason': 'conceded', 'practice_only': True}
        self.phase, self.turn = 'finished', None

    def bot_action(self):
        actions = self.legal_actions(self.turn)
        if not actions:
            raise ValueError('No legal move')
        def merit(action):
            raw = action['id'].split(':')[2]
            cards = raw.split(',') if raw else []
            return (len(cards) == len(self.table) and bool(cards), '7D' in cards,
                    len(cards) + sum(c.endswith('D') for c in cards), len(raw))
        return max(actions, key=merit)['id']

    def view(self, viewer_id=None):
        return {'kind': 'scopa', 'players': list(self.players), 'turn': self.turn, 'phase': self.phase,
                'hands': {str(p): list(self.hands[str(p)]) if p == viewer_id else [None]*len(self.hands[str(p)]) for p in self.players},
                'table': list(self.table), 'scores': deepcopy(self.result.get('scores', {})) if self.result else dict(self.sweeps),
                'captured_counts': {p: len(cards) for p, cards in self.captured.items()},
                'remaining_deck': len(self.deck), 'log': list(self.log), 'result': deepcopy(self.result)}

    def to_dict(self):
        return {'version': self.RULES_VERSION, **deepcopy(self.__dict__)}

    @classmethod
    def from_dict(cls, state):
        data = deepcopy(state)
        if data.pop('version') != cls.RULES_VERSION:
            raise ValueError('Unsupported Scopa rules version')
        game = cls.__new__(cls)
        game.__dict__.update(data)
        return game
