"""Basic/Open Triple Triad with equal original card sets and no trading.

Shared capture rules: Square Enix's official Triple Triad play guide.
Fixed cards and score-only matches are this bot's adaptation, not FFVIII's
collection or regional-rule system. All cards are public under Open.
"""
from copy import deepcopy
import random

CARDS = (
    {'id': 'cloud', 'name': 'Cloud', 'north': 5, 'east': 2, 'south': 4, 'west': 5},
    {'id': 'flower', 'name': 'Flower', 'north': 2, 'east': 6, 'south': 3, 'west': 5},
    {'id': 'mushroom', 'name': 'Mushroom', 'north': 4, 'east': 4, 'south': 6, 'west': 2},
    {'id': 'star', 'name': 'Star', 'north': 6, 'east': 3, 'south': 2, 'west': 5},
    {'id': 'luigi', 'name': 'Luigi', 'north': 3, 'east': 5, 'south': 5, 'west': 3},
)
DIRECTIONS = ((-1, 0, 'north', 'south'), (0, 1, 'east', 'west'),
              (1, 0, 'south', 'north'), (0, -1, 'west', 'east'))


def coordinate(slot):
    row, col = divmod(slot, 3)
    return f'{chr(65+row)}{col+1}'


class TripleTriad:
    KIND = 'triple_triad'
    RULES_VERSION = 'basic-open-equal-v1'
    RULES = ('Triple Triad Basic/Open practice: alternate placing cards on a 3x3 grid. '
             'A strictly stronger touching edge captures an opposing card; equal edges do not. '
             'Captures do not chain. After nine placements, count owned board cards AND the '
             'unplayed tenth card; 5-5 is a draw. Both hands are open. This bot uses identical '
             'original five-card sets and a random starter; no trading, Same, Plus, Combo, '
             'Elemental or Sudden Death. No community coins.')

    def __init__(self, players=(1, 0), seed=None):
        self.players = list(players)
        if (len(self.players) != 2 or len(set(self.players)) != 2
                or any(type(p) is not int or p < 0 for p in self.players)):
            raise ValueError('Two distinct nonnegative player IDs are required')
        self.hands = {str(p): deepcopy(list(CARDS)) for p in self.players}
        self.table = [None] * 9
        self.turn = random.Random(seed).choice(self.players)
        self.result = None
        self.log = ['Basic/Open: both identical hands are visible.']
        self.captures = []

    @property
    def finished(self):
        return self.result is not None

    def scores(self):
        return {str(p): len(self.hands[str(p)]) + sum(
            slot is not None and slot['owner'] == p for slot in self.table) for p in self.players}

    def legal_actions(self, player_id):
        if self.finished or player_id != self.turn or player_id not in self.players:
            return []
        actions = []
        for card in self.hands[str(player_id)]:
            for slot, value in enumerate(self.table):
                if value is None:
                    actions.append({'id': f"place:{card['id']}:{slot}",
                        'label': f"{card['name']} at {coordinate(slot)}", 'group': card['name'],
                        'description': f"N{card['north']} E{card['east']} S{card['south']} W{card['west']}"})
        return actions + [{'id': 'concede', 'label': 'Concede match', 'group': 'Concede'}]

    def _captured(self, player_id, card, position):
        row, col = divmod(position, 3)
        captured = []
        for dr, dc, attack, defend in DIRECTIONS:
            nr, nc = row+dr, col+dc
            if not 0 <= nr < 3 or not 0 <= nc < 3:
                continue
            target = nr*3+nc
            other = self.table[target]
            if other is not None and other['owner'] != player_id and card[attack] > other['card'][defend]:
                captured.append({'slot': target, 'edge': attack, 'attack': card[attack],
                                 'defend': other['card'][defend]})
        return captured

    def act(self, player_id, action_id):
        if action_id not in {a['id'] for a in self.legal_actions(player_id)}:
            raise ValueError('That action is unavailable; refresh the current turn')
        if action_id == 'concede':
            return self.concede(player_id)
        _, card_id, position = action_id.split(':')
        position = int(position)
        hand = self.hands[str(player_id)]
        card = next(c for c in hand if c['id'] == card_id)
        captures = self._captured(player_id, card, position)
        hand.remove(card)
        self.table[position] = {'card': card, 'owner': player_id}
        for capture in captures:
            self.table[capture['slot']]['owner'] = player_id
        self.captures = captures
        self.log = [f"Seat {self.players.index(player_id)+1}: {card['name']} at {coordinate(position)}."]
        self.log += [f"Captured {coordinate(c['slot'])}: {c['edge']} {c['attack']} > {c['defend']}." for c in captures]
        if all(slot is not None for slot in self.table):
            scores = self.scores()
            winner = None if len(set(scores.values())) == 1 else max(self.players, key=lambda p: scores[str(p)])
            self.result = {'winner': winner, 'reason': 'draw' if winner is None else 'board_complete', 'scores': scores}
            self.turn = None
        else:
            self.turn = next(p for p in self.players if p != player_id)
        return self.view(player_id)

    def concede(self, player_id):
        if self.finished or player_id not in self.players:
            raise ValueError('This player cannot concede this match')
        self.result = {'winner': next(p for p in self.players if p != player_id),
                       'reason': 'concession', 'scores': self.scores()}
        self.turn = None
        self.log = [f'Seat {self.players.index(player_id)+1} conceded.']
        return self.view(player_id)

    def bot_action(self):
        """Greedy captures with a tie preference for protected board edges; Open."""
        actions = [a for a in self.legal_actions(self.turn) if a['id'] != 'concede']
        if not actions:
            raise ValueError('No active turn')
        def strength(action):
            _, card_id, position = action['id'].split(':'); position = int(position)
            card = next(c for c in self.hands[str(self.turn)] if c['id'] == card_id)
            count = len(self._captured(self.turn, card, position))
            row, col = divmod(position, 3)
            exposed = [card[edge] for dr, dc, edge, _ in DIRECTIONS
                       if 0 <= row+dr < 3 and 0 <= col+dc < 3 and self.table[(row+dr)*3+col+dc] is None]
            return (count, min(exposed, default=10), -len(exposed))
        return max(actions, key=strength)['id']

    def view(self, viewer_id=None):
        return deepcopy({'kind': self.KIND, 'players': self.players, 'turn': self.turn,
            'phase': 'finished' if self.finished else 'place', 'hands': self.hands,
            'table': self.table, 'scores': self.scores(), 'log': self.log,
            'result': self.result, 'captures': self.captures, 'rules_version': self.RULES_VERSION})

    def to_dict(self):
        return deepcopy({'version': self.RULES_VERSION, 'players': self.players, 'hands': self.hands,
                         'table': self.table, 'turn': self.turn, 'result': self.result,
                         'log': self.log, 'captures': self.captures})

    @classmethod
    def from_dict(cls, state):
        if state.get('version') != cls.RULES_VERSION:
            raise ValueError('Unsupported Triple Triad save version')
        game = cls.__new__(cls)
        for name in ('players', 'hands', 'table', 'turn', 'result', 'log', 'captures'):
            setattr(game, name, deepcopy(state[name]))
        return game
