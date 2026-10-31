"""One score-only Platoon campaign with explicit deck/edge conventions.

Ni no Kuni mechanics follow the supplied research handoff. Standard deck plus
2 Wizards, at most one Wizard/pile, redraw tied opening cards and challenger
loses drawn battles are declared practice conventions; no original chip ladder.
"""
from copy import deepcopy
import random

RANKS=('2','3','4','5','6','7','8','9','10','J','Q','K','A')


def rank(card):
    return 'X' if card.startswith('X') else card[:-1]


def value(card):
    r=rank(card)
    return 0 if r=='X' else 1 if r=='A' else 10 if r in ('J','Q','K') else int(r)


def valid_pile(cards):
    ranks=[rank(c) for c in cards]
    return bool(cards) and not ('K' in ranks and 'A' in ranks) and ranks.count('X')<=1 and ranks!=['X']


def compare_piles(left,right):
    """Exchange once, then compare effects and totals. Return original-side sign."""
    a,b=list(left),list(right)
    exchange=any(rank(c)=='X' for c in a) != any(rank(c)=='X' for c in b)
    if exchange: a,b=b,a
    def category(cards):
        ranks={rank(c) for c in cards}
        return 'King' if 'K' in ranks else 'Bishop' if 'A' in ranks else 'ordinary'
    ca,cb=category(a),category(b)
    if ca==cb:
        ta,tb=sum(map(value,a)),sum(map(value,b))
        sign=(ta>tb)-(ta<tb)
        reason=f'{ca} totals {ta} vs {tb}'
    else:
        sign=1 if (ca,cb) in (('King','ordinary'),('ordinary','Bishop'),('Bishop','King')) else -1
        reason=f'{ca} vs {cb}'
    return sign, {'left':a,'right':b,'exchange':exchange,'reason':('Wizard exchange; ' if exchange else '')+reason}


class Platoon:
    RULES_VERSION='single-campaign-practice-v1'
    RULES=('Platoon practice: arrange ten private cards into five nonempty formations. Move cards freely before Lock. '
           'No King+Bishop together, at most one Wizard per formation, and a Wizard cannot stand alone. '
           'King beats ordinary; ordinary beats Bishop; Bishop beats King. Matching types compare totals: '
           'number cards are face value, J/Q/K are 10, Bishop (Ace) is 1, Wizard is 0. '
           'A lone-side Wizard swaps both formations once before comparison; two Wizards cancel. '
           'Predict any slot, then alternate choosing your formation and an opposing target. First side to three battle credits wins; '
           'a drawn battle is visibly a draw but counts against the first player/challenger. Predictions score accuracy only. '
           'Declared bot conventions: standard 52 plus 2 Wizards, equal-rank opener redraw, single campaign, no chip ladder or coins.')

    def __init__(self, players=(1,0), seed=None, *, deck=None, hands=None):
        if len(players)!=2 or len(set(players))!=2 or any(type(p) is not int or p<0 for p in players):
            raise ValueError('Choose two distinct players')
        self.players=list(players)
        cards=list(deck) if deck is not None else [r+s for s in 'CDHS' for r in RANKS]+['X1','X2']
        if any(c not in [r+s for s in 'CDHS' for r in RANKS]+['X1','X2'] for c in cards):
            raise ValueError('Invalid Platoon card')
        if deck is None: random.Random(seed).shuffle(cards)
        if hands is None:
            if len(cards)<22: raise ValueError('Platoon needs twenty cards and an opening draw')
            self.hands={str(p):cards[i*10:(i+1)*10] for i,p in enumerate(players)}
            self.deck=cards[20:]
        else:
            self.hands={str(p):list(hands.get(str(p),hands.get(p,[]))) for p in players}
            if any(len(h)!=10 for h in self.hands.values()): raise ValueError('Each hand needs ten cards')
            if any(c not in [r+s for s in 'CDHS' for r in RANKS]+['X1','X2'] for h in self.hands.values() for c in h):
                raise ValueError('Invalid hand')
            self.deck=cards
        self.assignments={str(p):[None]*10 for p in players}
        self.locked=[];self.predictions={};self.prediction_results={str(p):None for p in players}
        self.spent={str(p):[] for p in players}
        self.scores={str(p):0 for p in players}
        self.history=[];self.opening=[]
        self.phase='formation';self.turn=players[0];self.finished=False;self.result=None
        self.log=['Arrange all ten cards into five legal formations.']

    def piles(self, player):
        key=str(player)
        return [[c for i,c in enumerate(self.hands[key]) if self.assignments[key][i]==pile] for pile in range(5)]

    def legal_actions(self, player_id):
        if self.finished or player_id!=self.turn: return []
        key=str(player_id)
        if self.phase=='formation':
            actions=[]
            for i,card in enumerate(self.hands[key]):
                for pile in range(5):
                    if self.assignments[key][i]!=pile:
                        actions.append({'id':f'assign:{i}:{pile}','label':f'Card {i+1} {card} → formation {chr(65+pile)}',
                                        'group':f'Card {i+1}'})
                if self.assignments[key][i] is not None:
                    actions.append({'id':f'undo:{i}','label':f'Unassign card {i+1} {card}','group':f'Card {i+1}'})
            if None not in self.assignments[key] and all(valid_pile(p) for p in self.piles(player_id)):
                actions.append({'id':'lock','label':'Lock all five formations','group':'Ready'})
            return actions
        if self.phase=='prediction':
            return [{'id':f'predict:{seat}:{pile}','label':f'Predict seat {seat+1}, formation {chr(65+pile)} wins',
                     'group':'Prediction'} for seat in range(2) for pile in range(5)]
        other=self.players[1-self.players.index(player_id)]
        return [{'id':f'battle:{a}:{b}','label':f'Your {chr(65+a)} attacks opposing {chr(65+b)}',
                 'group':f'Attack with {chr(65+a)}'}
                for a in range(5) if a not in self.spent[key]
                for b in range(5) if b not in self.spent[str(other)]]

    def act(self, player_id, action_id):
        if action_id not in {a['id'] for a in self.legal_actions(player_id)}:
            raise ValueError('That Platoon action is unavailable')
        before=self.to_dict()
        try: self._act(player_id,action_id)
        except Exception:
            self.__dict__.update(self.from_dict(before).__dict__);raise
        return self.view(player_id)

    def _act(self, player, action):
        key=str(player)
        if action.startswith('assign:'):
            _,card,pile=action.split(':');self.assignments[key][int(card)]=int(pile)
            self.log=[f'Player {player} adjusted a private formation.'];return
        if action.startswith('undo:'):
            self.assignments[key][int(action.split(':')[1])]=None;return
        if action=='lock':
            self.locked.append(player)
            if len(self.locked)==1: self.turn=self.players[1]
            else: self.phase='prediction';self.turn=self.players[0]
            self.log=[f'Player {player} locked five formations.'];return
        if action.startswith('predict:'):
            _,seat,pile=action.split(':');self.predictions[key]=[self.players[int(seat)],int(pile)]
            if len(self.predictions)==1: self.turn=self.players[1]
            else: self._opening_draw()
            return
        _,own,target=action.split(':');own,target=int(own),int(target)
        other=self.players[1-self.players.index(player)]
        a,b=self.piles(player)[own],self.piles(other)[target]
        sign,detail=compare_piles(a,b)
        winner=player if sign>0 else other if sign<0 else None
        credited=self.players[1] if winner is None else winner
        self.scores[str(credited)]+=1
        self.spent[key].append(own);self.spent[str(other)].append(target)
        event={'attacker':player,'own':own,'target':target,'defender':other,
               'before':[list(a),list(b)],'winner':winner,'credited':credited,**detail}
        self.history.append(event)
        for predictor,(side,pile) in self.predictions.items():
            if (side,pile) in ((player,own),(other,target)):
                self.prediction_results[predictor]=winner==side
        self.log=[('Draw; house/challenger-opponent credit. ' if winner is None else f'Player {winner} wins. ')+detail['reason']]
        if self.scores[str(credited)]==3:
            self.finished=True;self.phase='finished';self.turn=None
            self.result={'winner':credited,'outcome':'campaign_win','reason':'three battle credits','scores':dict(self.scores),
                         'prediction_accuracy':dict(self.prediction_results),'practice_only':True}
        else: self.turn=other

    def _opening_draw(self):
        while len(self.deck)>=2:
            pair=self.deck[:2];self.deck=self.deck[2:]
            if any(rank(c)=='X' for c in pair): continue
            ra,rb=[RANKS.index(rank(c)) for c in pair]
            self.opening.append(list(pair))
            if ra!=rb:
                self.turn=self.players[0 if ra>rb else 1]
                self.phase='battle';self.log=[f'Opening draw {pair[0]} vs {pair[1]}; player {self.turn} attacks first.'];return
        raise ValueError('Opening draw could not resolve from this saved deck')

    def _bot_partition(self, player):
        cards=self.hands[str(player)];piles=[[] for _ in range(5)];assignment=[0]*10
        def solve(i):
            if i==10: return all(valid_pile(p) for p in piles)
            if sum(not p for p in piles)>10-i: return False
            for j,pile in enumerate(piles):
                ranks=[rank(c) for c in pile]+[rank(cards[i])]
                if 'K' in ranks and 'A' in ranks or ranks.count('X')>1: continue
                empty=not pile
                pile.append(cards[i]);assignment[i]=j
                if solve(i+1): return True
                pile.pop()
                if empty: break
            return False
        if not solve(0): raise ValueError('No legal formation allocation')
        return assignment

    def bot_action(self):
        if self.finished: return None
        player=self.turn;key=str(player)
        if self.phase=='formation':
            target=self._bot_partition(player)
            for i,pile in enumerate(target):
                if self.assignments[key][i]!=pile: return f'assign:{i}:{pile}'
            return 'lock'
        own=self.piles(player)
        def strength(pile):
            ranks={rank(c) for c in pile}
            return sum(map(value,pile))+(30 if 'K' in ranks else -10 if 'A' in ranks else 0)
        if self.phase=='prediction':
            pile=max(range(5),key=lambda i:strength(own[i]))
            return f'predict:{self.players.index(player)}:{pile}'
        other=self.players[1-self.players.index(player)]
        live=[i for i in range(5) if i not in self.spent[key]]
        targets=[i for i in range(5) if i not in self.spent[str(other)]]
        attack=max(live,key=lambda i:strength(own[i]))
        # The opposing *count* is public; no concealed rank/total is consulted.
        public_formations=self.view(player)['formations'][str(other)]
        target=min(targets,key=lambda i:public_formations[i]['count'])
        return f'battle:{attack}:{target}'

    def view(self, viewer_id=None):
        formations={}
        for player in self.players:
            key=str(player)
            formations[key]=[{'label':chr(65+i),'cards':list(pile) if viewer_id==player or i in self.spent[key] else [None]*len(pile),
                              'count':len(pile),'spent':i in self.spent[key]} for i,pile in enumerate(self.piles(player))]
        return {'kind':'platoon','players':list(self.players),'turn':self.turn,'phase':self.phase,
                'hands':{str(p):list(self.hands[str(p)]) if viewer_id==p else [None]*10 for p in self.players},
                'table':deepcopy(self.history[-1]['left']+self.history[-1]['right']) if self.history else [],
                'formations':formations,'scores':dict(self.scores),'predictions':deepcopy(self.predictions),
                'assignments':list(self.assignments[str(viewer_id)]) if viewer_id in self.players else None,
                'history':deepcopy(self.history),'opening':deepcopy(self.opening),'log':list(self.log),
                'result':deepcopy(self.result),'rules_version':self.RULES_VERSION}

    def to_dict(self):
        return {'version':self.RULES_VERSION,**deepcopy(self.__dict__)}

    @classmethod
    def from_dict(cls,data):
        data=deepcopy(data)
        if data.pop('version',None)!=cls.RULES_VERSION: raise ValueError('Unsupported Platoon save')
        obj=cls.__new__(cls);obj.__dict__.update(data);return obj
