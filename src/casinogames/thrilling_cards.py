"""Bounded, practice-chip adaptation of Luigi's Thrilling Cards.

Verified identity: 2–4 players see everyone else's card, never their own;
rank wins first, then clubs < diamonds < hearts < spades. Ante, two-raise
cap, maximum 15-unit commitment and five-hand rotation are Discord house
rules from the research handoff, not claims about Nintendo's exact rules.

Only ``view`` is safe for rendering. ``to_dict`` contains secret cards and
is exclusively for trusted persistence. This module never touches money.
"""
from copy import deepcopy
import random

RANKS = tuple(str(n) for n in range(2, 11)) + ('J', 'Q', 'K', 'A')
SUITS = ('C', 'D', 'H', 'S')
DECK = tuple(rank + suit for rank in RANKS for suit in SUITS)


def card_strength(card):
    if card not in DECK:
        raise ValueError('Invalid standard card')
    return (RANKS.index(card[:-1]), SUITS.index(card[-1]))


class ThrillingCards:
    """One hand; ``amount`` for open/raise is a number of stake units.

    Commands may supply ``expected_revision`` to reject stale controls.
    ``fold`` also handles departures and timeouts outside the active turn.
    """
    GAME_KEY = 'thrilling_cards'
    MAX_RAISES = 2
    MAX_COMMITMENT_UNITS = 15

    def __init__(self, players, unit=1, cards=None, opener=0, rng=None):
        self.players = tuple(players)
        if not 2 <= len(self.players) <= 4 or len(set(self.players)) != len(self.players):
            raise ValueError('A table needs 2–4 distinct players')
        if any(type(p) is not int or p <= 0 for p in self.players):
            raise ValueError('Player IDs must be positive integers')
        if type(unit) is not int or unit <= 0:
            raise ValueError('Stake unit must be a positive integer')
        if type(opener) is not int or not 0 <= opener < len(self.players):
            raise ValueError('Invalid opening seat')
        self.unit = unit
        self.opener = opener
        if cards is None:
            cards = (rng or random.SystemRandom()).sample(DECK, len(self.players))
        if isinstance(cards, dict):
            if set(cards) != set(self.players):
                raise ValueError('Each player must have exactly one card')
            cards = [cards[p] for p in self.players]
        cards = tuple(cards)
        if len(cards) != len(self.players) or len(set(cards)) != len(cards):
            raise ValueError('Deal one unique card per player')
        for card in cards:
            card_strength(card)
        self.cards = dict(zip(self.players, cards))
        self.commitments = {p: unit for p in self.players}
        self.folded = set()
        self.pending = set(self.players)
        self.target = unit
        self.raises = 0
        self.opened = False
        self.turn = self.players[opener]
        self.result = None
        self.revision = 0
        self._events = []

    @property
    def pot(self):
        return sum(self.commitments.values())

    @property
    def active(self):
        return tuple(p for p in self.players if p not in self.folded)

    def legal_actions(self, player_id):
        if self.result is not None or player_id != self.turn:
            return ()
        if not self.opened:
            return ('open', 'fold')
        return ('call', 'fold', 'raise') if self.raises < self.MAX_RAISES else ('call', 'fold')

    def _check_revision(self, expected_revision):
        if expected_revision is not None and expected_revision != self.revision:
            raise ValueError('This table has changed; refresh before acting')

    def act(self, player_id, action, amount=None, *, expected_revision=None):
        self._check_revision(expected_revision)
        if action not in self.legal_actions(player_id):
            raise ValueError('This action is not available for this player')
        if action == 'fold':
            if amount is not None:
                raise ValueError('Fold does not accept an amount')
            return self.fold(player_id, expected_revision=expected_revision)
        if action in ('open', 'raise'):
            if type(amount) is not int or not 1 <= amount <= 5:
                raise ValueError('Choose 1–5 stake units')
        elif amount is not None:
            raise ValueError('Call does not accept an amount')
        if action == 'open':
            self.target = amount * self.unit
            self.opened = True
        elif action == 'raise':
            self.target += amount * self.unit
            self.raises += 1
            self.pending = set(self.active)
        self.commitments[player_id] = self.target
        self.pending.discard(player_id)
        self._record(player_id, action, amount)
        self._advance(player_id)
        return self.view()

    def fold(self, player_id, *, expected_revision=None):
        """Fold a dealt player, even out of turn, on leave or timeout."""
        self._check_revision(expected_revision)
        if self.result is not None or player_id not in self.active:
            raise ValueError('Player has already folded or hand has ended')
        previous_turn = self.turn
        self.folded.add(player_id)
        self.pending.discard(player_id)
        self._record(player_id, 'fold', None)
        if len(self.active) == 1:
            self._settle('fold')
        elif self.opened and not self.pending:
            self._settle('showdown')
        elif player_id == previous_turn:
            self._advance(player_id)
        return self.view()

    def _record(self, player_id, action, amount):
        self._events.append({'player_id': player_id, 'action': action, 'amount': amount})
        self.revision += 1

    def _advance(self, previous):
        if len(self.active) == 1:
            self._settle('fold')
            return
        if self.opened and not self.pending:
            self._settle('showdown')
            return
        start = self.players.index(previous)
        for offset in range(1, len(self.players) + 1):
            candidate = self.players[(start + offset) % len(self.players)]
            if candidate in self.pending and candidate not in self.folded:
                self.turn = candidate
                return
        raise RuntimeError('No eligible next player')

    def _settle(self, reason):
        winner = max(self.active, key=lambda p: card_strength(self.cards[p]))
        self.result = {
            'reason': reason, 'winner': winner, 'pot': self.pot,
            'gross': {p: self.pot if p == winner else 0 for p in self.players},
            'net': {p: (self.pot if p == winner else 0) - self.commitments[p]
                    for p in self.players},
            'revealed': ({p: self.cards[p] for p in self.active}
                         if reason == 'showdown' else {}),
        }
        self.turn = None
        self.pending.clear()

    def view(self, viewer_id=None):
        """Project state BEFORE rendering; spectators receive only backs.

        Authenticate a private viewer against the interaction user first.
        Even a forged nonparticipant ID never receives another seat's view.
        """
        private = viewer_id in self.players
        revealed = self.result['revealed'] if self.result else {}
        seats = []
        for p in self.players:
            card = revealed.get(p)
            if private and p != viewer_id:
                card = self.cards[p]
            seats.append({'player_id': p, 'card': card,
                          'committed': self.commitments[p], 'folded': p in self.folded})
        return {
            'game': self.GAME_KEY, 'unit': self.unit, 'seats': seats,
            'pot': self.pot, 'target': self.target, 'turn': self.turn,
            'raises_left': self.MAX_RAISES - self.raises,
            'max_commitment': self.MAX_COMMITMENT_UNITS * self.unit,
            'opened': self.opened, 'revision': self.revision,
            'actions': self.legal_actions(viewer_id) if private else (),
            'call_cost': self.target - self.commitments[viewer_id] if private else None,
            'result': deepcopy(self.result),
        }

    def to_dict(self):
        """Trusted storage only. Replay accepted events to recover exactly."""
        return {'version': 1, 'players': list(self.players), 'unit': self.unit,
                'cards': [self.cards[p] for p in self.players], 'opener': self.opener,
                'events': deepcopy(self._events)}

    @classmethod
    def from_dict(cls, data):
        if data.get('version') != 1:
            raise ValueError('Unsupported Thrilling Cards save version')
        events = data.get('events', [])
        if not isinstance(events, list) or len(events) > 32:
            raise ValueError('Invalid saved action log')
        game = cls(data['players'], data['unit'], data['cards'], data['opener'])
        for event in events:
            if event['action'] == 'fold':
                if event['amount'] is not None:
                    raise ValueError('Invalid saved fold')
                game.fold(event['player_id'])
            else:
                game.act(event['player_id'], event['action'], event['amount'])
        return game


class ThrillingMatch:
    """Up to five practice hands, rotating opener and conserved standings.

    Each seat starts with 75 units and must afford the 15-unit maximum
    before every deal. No side pots or separate winner rewards are created.
    Lobby consent/readiness and storage locking belong to the caller.
    """
    MAX_HANDS = 5

    def __init__(self, players, unit=1):
        # Validate without allocating a random deal.
        checked = ThrillingCards(players, unit, DECK[:len(players)])
        self.players = checked.players
        self.unit = unit
        self.chips = {p: self.MAX_HANDS * 15 * unit for p in self.players}
        self.departed = set()
        self.hands = []
        self.hand = None

    @property
    def finished(self):
        return (len(self.hands) >= self.MAX_HANDS or
                len(self._eligible()) < 2) and (self.hand is None or self.hand.result is not None)

    def _eligible(self):
        return tuple(p for p in self.players if p not in self.departed
                     and self.chips[p] >= 15 * self.unit)

    def next_hand(self, *, cards=None, rng=None):
        if self.hand is not None and self.hand.result is None:
            raise ValueError('Finish the current hand first')
        if self.hand is not None:
            self.settle_hand()
        if self.finished:
            raise ValueError('This match has ended')
        eligible = self._eligible()
        # Rotate through original seats, skipping departed or short stacks.
        start = len(self.hands) % len(self.players)
        opener_id = next(self.players[(start + n) % len(self.players)]
                         for n in range(len(self.players))
                         if self.players[(start + n) % len(self.players)] in eligible)
        self.hand = ThrillingCards(eligible, self.unit, cards, eligible.index(opener_id), rng)
        return self.hand

    def settle_hand(self):
        if self.hand is None or self.hand.result is None:
            raise ValueError('No completed hand to settle')
        if self.hands and self.hands[-1] is self.hand:
            return deepcopy(self.hand.result)
        for p, net in self.hand.result['net'].items():
            self.chips[p] += net
        self.hands.append(self.hand)
        return deepcopy(self.hand.result)

    def leave(self, player_id):
        if player_id not in self.players or player_id in self.departed:
            raise ValueError('Player is not at this table')
        self.departed.add(player_id)
        if self.hand is not None and self.hand.result is None and player_id in self.hand.active:
            self.hand.fold(player_id)

    def standings(self):
        totals = sorted(set(self.chips.values()), reverse=True)
        initial = self.MAX_HANDS * 15 * self.unit
        return [{'player_id': p, 'net': self.chips[p] - initial,
                 'chips': self.chips[p], 'place': totals.index(self.chips[p]) + 1}
                for p in sorted(self.players, key=lambda p: -self.chips[p])]

    def to_dict(self):
        """Trusted storage; completed results are derived again on restore."""
        current = self.hand
        if self.hands and current is self.hands[-1]:
            current = None
        return {'version': 1, 'players': list(self.players), 'unit': self.unit,
                'departed': sorted(self.departed),
                'hands': [hand.to_dict() for hand in self.hands],
                'current': current.to_dict() if current is not None else None}

    @classmethod
    def from_dict(cls, data):
        if data.get('version') != 1:
            raise ValueError('Unsupported Thrilling match save version')
        match = cls(data['players'], data['unit'])
        histories = data.get('hands', [])
        if not isinstance(histories, list) or len(histories) > cls.MAX_HANDS:
            raise ValueError('Invalid saved hand count')
        for saved in histories:
            hand = ThrillingCards.from_dict(saved)
            if (hand.result is None or hand.unit != match.unit or
                    not set(hand.players).issubset(match.players)):
                raise ValueError('Invalid completed hand')
            if any(match.chips[p] < 15 * match.unit for p in hand.players):
                raise ValueError('Insufficient chips for saved hand')
            match.hand = hand
            match.settle_hand()
        departed = set(data.get('departed', []))
        if not departed.issubset(match.players):
            raise ValueError('Invalid departed player')
        match.departed = departed
        if data.get('current') is not None:
            if len(histories) >= cls.MAX_HANDS:
                raise ValueError('Too many saved hands')
            hand = ThrillingCards.from_dict(data['current'])
            if (hand.unit != match.unit or not set(hand.players).issubset(match.players)
                    or any(match.chips[p] < 15 * match.unit for p in hand.players)):
                raise ValueError('Invalid current hand')
            match.hand = hand
        return match
