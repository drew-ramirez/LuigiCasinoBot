"""Casino War, six-deck / three-burn practice adaptation of NYX rules.

Source: https://external-helpfiles.ext.nyxop.net/us-pa/500392_en_us.html
Only virtual practice stakes are used. No wallet side effects.
"""
from copy import deepcopy
import random

RANKS = ('2','3','4','5','6','7','8','9','10','J','Q','K','A')


class CasinoWar:
    RULES_VERSION = 'six-deck-practice-v1'
    RULES = ('Casino War practice: six fresh decks; Ace high, suits ignored. Higher card returns 2x stake. '
             'Tie: surrender returns half, or War adds one equal stake and burns three covered cards. '
             'War win returns 3x original stake, second tie 4x, loss zero. '
             'One hand, no side bets. These are virtual chips, not community coins.')

    def __init__(self, players=(1,0), seed=None, *, stake=20, deck=None):
        if len(players) != 2 or len(set(players)) != 2 or any(type(p) is not int or p < 0 for p in players):
            raise ValueError('Choose two distinct player IDs')
        if type(stake) is not int or stake <= 0 or stake % 2:
            raise ValueError('Practice stake must be a positive even integer')
        self.players = list(players)
        self.stake = stake
        self.committed = stake
        self.deck = list(deck) if deck is not None else [r+s for _ in range(6) for s in 'CDHS' for r in RANKS]
        if any(c[:-1] not in RANKS or c[-1:] not in 'CDHS' for c in self.deck) or len(self.deck)<2:
            raise ValueError('Invalid War deck')
        if deck is None:
            random.Random(seed).shuffle(self.deck)
        self.cards = self.deck[:2]; self.deck = self.deck[2:]
        self.turn = self.players[0]
        self.phase = 'tie'
        self.result = None
        self.finished = False
        self.burned = 0
        self.log = ['Cards dealt. Compare rank; suits do not break ties.']
        self._resolve(False)

    def _resolve(self, war):
        a,b = [RANKS.index(c[:-1]) for c in self.cards]
        if a==b and not war:
            self.log = ['Tie: surrender half or commit another stake for War.']
            return
        gross = (4 if a==b else 3 if a>b else 0)*self.stake if war else (2 if a>b else 0)*self.stake
        self._finish('war_tie' if a==b else 'win' if a>b else 'loss', gross)

    def _finish(self, outcome, gross):
        self.finished = True; self.phase = 'finished'; self.turn = None
        self.result = {'outcome':outcome,'winner':self.players[0] if gross>self.committed else self.players[1] if gross<self.committed else None,
                       'gross':gross,'committed':self.committed,'net':gross-self.committed,'practice_only':True}
        self.log = [f'{outcome}: committed {self.committed}, returned {gross}, net {gross-self.committed:+}.']

    def legal_actions(self, player_id):
        if self.finished or player_id != self.turn:
            return []
        return [{'id':'surrender','label':f'Surrender: return {self.stake//2}','group':'Tie decision'},
                {'id':'war','label':f'Go to War: add {self.stake}','group':'Tie decision'}]

    def act(self, player_id, action_id):
        if action_id not in {a['id'] for a in self.legal_actions(player_id)}:
            raise ValueError('That War decision is unavailable')
        if action_id=='surrender':
            self._finish('surrender',self.stake//2)
        else:
            if len(self.deck)<5:
                raise ValueError('The saved shoe cannot complete War')
            self.committed += self.stake
            self.burned = 3
            self.cards = self.deck[3:5]; self.deck = self.deck[5:]
            self._resolve(True)
        return self.view(player_id)

    def bot_action(self):
        return 'war' if not self.finished else None

    def view(self, viewer_id=None):
        return {'kind':'casino_war','players':list(self.players),'turn':self.turn,'phase':self.phase,
                'hands':{str(p):[self.cards[i]] for i,p in enumerate(self.players)},'table':list(self.cards),
                'scores':{str(self.players[0]): self.result['net'] if self.result else 0},
                'log':list(self.log),'result':deepcopy(self.result),'stake':self.stake,
                'committed':self.committed,'burned':self.burned,'rules_version':self.RULES_VERSION}

    def to_dict(self):
        return {'version':self.RULES_VERSION, **deepcopy(self.__dict__)}

    @classmethod
    def from_dict(cls, data):
        data=deepcopy(data)
        if data.pop('version',None)!=cls.RULES_VERSION:
            raise ValueError('Unsupported Casino War save')
        obj=cls.__new__(cls);obj.__dict__.update(data)
        return obj
