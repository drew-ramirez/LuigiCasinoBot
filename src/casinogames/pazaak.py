"""Pazaak core with declared practice conventions and configurable side decks.

Reference: official KOTOR I manual, printed pp34–35. Nine-card safe win,
random first opener/alternating set openers and free shared card catalogue
are explicit bot conventions, not asserted exact original edge rules.
"""
from copy import deepcopy
import random

CATALOG = tuple(sign+str(n) for sign in ('+','-','±') for n in range(1,7))
DEFAULT_SIDE = ['+1','+2','+3','+4','+5','-1','-2','-3','±1','±2']


def _tuple(value):
    return tuple(_tuple(v) for v in value) if isinstance(value,list) else value


class Pazaak:
    RULES_VERSION = 'kotor-core-practice-v1'
    RULES = ('Pazaak practice: configure ten side cards, at most two copies of a kind, from the free +/−/±1–6 catalogue; '
             'draw four modifiers for the entire match. Target 20; one optional modifier each turn. '
             'A negative card can rescue a bust before End turn. Stand keeps the total; first to three set wins wins. '
             'Tied sets award nothing. Bot conventions: random initial opener, alternating subsequent sets, '
             'main draws uniform 1–10 with replacement, and filling nine table slots at 20 or less immediately wins that set. '
             'No KOTOR II special cards, collection purchases, or community-coin wagers.')

    def __init__(self, players=(1,0), seed=None, *, side_decks=None, draws=None):
        if len(players)!=2 or len(set(players))!=2 or any(type(p) is not int or p<0 for p in players):
            raise ValueError('Choose two distinct players')
        self.players=list(players)
        self.rng=random.Random(seed)
        self.side_decks={str(p):list((side_decks or {}).get(str(p),(side_decks or {}).get(p,DEFAULT_SIDE))) for p in players}
        for cards in self.side_decks.values():
            self._validate_deck(cards)
        self.hands={str(p):[] for p in players}
        self.boards={str(p):[] for p in players}
        self.standing={str(p):False for p in players}
        self.scores={str(p):0 for p in players}
        self.phase='side_deck';self.turn=players[0]
        self.ready=[];self.opener=self.rng.randrange(2);self.set_number=0
        self.used_side=False;self.result=None;self.finished=False;self.last_set=None
        self.draws=list(draws) if draws is not None else None
        if self.draws is not None and any(type(v) is not int or not 1<=v<=10 for v in self.draws):
            raise ValueError('Main cards must be 1–10')
        self.log=['Configure ten side cards, then confirm your deck.']

    @staticmethod
    def _validate_deck(cards):
        if len(cards)!=10 or any(c not in CATALOG or cards.count(c)>2 for c in cards):
            raise ValueError('Side deck needs ten valid cards, maximum two of each kind')

    def total(self, player):
        return sum(self.boards[str(player)])

    def legal_actions(self, player_id):
        if self.finished or player_id!=self.turn:
            return []
        key=str(player_id)
        if self.phase=='side_deck':
            deck=self.side_decks[key]
            actions=[{'id':'ready','label':'Confirm ten-card side deck','group':'Ready'}]
            for i,card in enumerate(deck):
                for replacement in CATALOG:
                    if replacement!=card and deck.count(replacement)<2:
                        actions.append({'id':f'replace:{i}:{replacement}', 'label':f'Slot {i+1}: {card} → {replacement}',
                                        'group':f'Side deck slot {i+1}'})
            return actions
        if self.phase=='set_end':
            return [{'id':'next','label':'Start next set','group':'Set result'}]
        actions=[{'id':'end','label':'End turn' if self.total(player_id)<=20 else 'End turn: accept bust','group':'Turn'}]
        if self.total(player_id)<=20:
            actions.append({'id':'stand','label':f'Stand on {self.total(player_id)}','group':'Turn'})
        if not self.used_side and len(self.boards[key])<9:
            for i,card in enumerate(self.hands[key]):
                if card is None: continue
                signs=('+','-') if card[0]=='±' else (card[0],)
                for sign in signs:
                    value=int(card[1:])*(1 if sign=='+' else -1)
                    actions.append({'id':f'side:{i}:{sign}','label':f'Play {sign}{card[1:]} → total {self.total(player_id)+value}',
                                    'group':'Play modifier'})
        return actions

    def act(self, player_id, action_id):
        if action_id not in {a['id'] for a in self.legal_actions(player_id)}:
            raise ValueError('That Pazaak action is unavailable')
        before=self.to_dict()
        try:
            self._act(player_id,action_id)
        except Exception:
            self.__dict__.update(self.from_dict(before).__dict__)
            raise
        return self.view(player_id)

    def _act(self, player, action):
        key=str(player)
        if action.startswith('replace:'):
            _,i,card=action.split(':')
            self.side_decks[key][int(i)]=card
            self.log=['A player changed a private side-deck choice.']
            return
        if action=='ready':
            self.ready.append(player)
            if len(self.ready)==1:
                self.turn=self.players[1]
            else:
                for p in self.players:
                    deck=list(self.side_decks[str(p)]);self.rng.shuffle(deck)
                    self.hands[str(p)]=deck[:4]
                self._new_set()
            return
        if action=='next':
            self._new_set();return
        if action.startswith('side:'):
            _,i,sign=action.split(':');i=int(i)
            card=self.hands[key][i]
            value=int(card[1:])*(1 if sign=='+' else -1)
            self.hands[key][i]=None
            self.boards[key].append(value);self.used_side=True
            self.log=[f'Player {player} played {value:+}; total {self.total(player)}.']
            if len(self.boards[key])==9 and self.total(player)<=20:
                self._finish_set(player,'nine-card safe win')
            return
        total=self.total(player)
        if total>20:
            self._finish_set(self.other(player),'bust');return
        if action=='stand' or total==20:
            self.standing[key]=True
        opponent=self.other(player)
        if self.standing[key] and self.standing[str(opponent)]:
            other_total=self.total(opponent)
            self._finish_set(player if total>other_total else opponent if total<other_total else None,'comparison')
            return
        self.turn=opponent if not self.standing[str(opponent)] else player
        self._draw_turn()

    def other(self, player):
        return self.players[1-self.players.index(player)]

    def _new_set(self):
        self.set_number+=1
        self.boards={str(p):[] for p in self.players}
        self.standing={str(p):False for p in self.players}
        self.phase='playing';self.last_set=None
        self.turn=self.players[(self.opener+self.set_number-1)%2]
        self._draw_turn()

    def _draw_turn(self):
        if self.draws is not None:
            if not self.draws:
                raise ValueError('The scripted main deck is exhausted')
            value=self.draws.pop(0)
        else:
            value=self.rng.randint(1,10)
        self.used_side=False
        self.boards[str(self.turn)].append(value)
        self.log=[f'Player {self.turn} drew {value}; total {self.total(self.turn)}.']
        if len(self.boards[str(self.turn)])==9 and self.total(self.turn)<=20:
            self._finish_set(self.turn,'nine-card safe win')

    def _finish_set(self, winner, reason):
        self.last_set={'winner':winner,'reason':reason,'totals':{str(p):self.total(p) for p in self.players}}
        if winner is not None:
            self.scores[str(winner)]+=1
        self.log=[f'Set {self.set_number}: '+('draw' if winner is None else f'player {winner} wins')+f' ({reason}).']
        self.phase='set_end';self.turn=self.players[0]
        if winner is not None and self.scores[str(winner)]==3:
            self.finished=True;self.phase='finished';self.turn=None
            self.result={'winner':winner,'outcome':'match_win','reason':'three set wins',
                         'scores':dict(self.scores),'sets':self.set_number,'practice_only':True}

    def bot_action(self):
        legal=self.legal_actions(self.turn)
        if not legal: return None
        if self.phase=='side_deck': return 'ready'
        if self.phase=='set_end': return 'next'
        total=self.total(self.turn)
        side=[a for a in legal if a['id'].startswith('side:')]
        candidates=[]
        for action in side:
            _,index,sign=action['id'].split(':')
            value=int(self.hands[str(self.turn)][int(index)][1:])*(1 if sign=='+' else -1)
            candidates.append((total+value,action['id']))
        exact=next((a for t,a in candidates if t==20),None)
        if exact: return exact
        safe=[(t,a) for t,a in candidates if t<=20]
        if total>20 and safe: return max(safe)[1]
        opponent=self.other(self.turn)
        if total<=20 and (total>=18 or self.standing[str(opponent)] and total>self.total(opponent)):
            return 'stand'
        return 'end'

    def view(self, viewer_id=None):
        source=self.side_decks if self.phase=='side_deck' else self.hands
        hands={str(p):deepcopy(source[str(p)]) if viewer_id==p else [None]*len(source[str(p)]) for p in self.players}
        return {'kind':'pazaak','players':list(self.players),'turn':self.turn,'phase':self.phase,'hands':hands,
                'table':[v for p in self.players for v in self.boards[str(p)]],
                'boards':deepcopy(self.boards),'totals':{str(p):self.total(p) for p in self.players},
                'standing':dict(self.standing),'scores':dict(self.scores),'log':list(self.log),
                'result':deepcopy(self.result),'last_set':deepcopy(self.last_set),'set_number':self.set_number,
                'side_decks':{str(viewer_id):list(self.side_decks[str(viewer_id)])} if viewer_id in self.players else {},
                'rules_version':self.RULES_VERSION}

    def to_dict(self):
        return {'version':self.RULES_VERSION,'rng_state':self.rng.getstate(),
                **deepcopy({k:v for k,v in self.__dict__.items() if k!='rng'})}

    @classmethod
    def from_dict(cls, data):
        data=deepcopy(data)
        if data.pop('version',None)!=cls.RULES_VERSION: raise ValueError('Unsupported Pazaak save')
        state=data.pop('rng_state');obj=cls.__new__(cls);obj.__dict__.update(data)
        obj.rng=random.Random();obj.rng.setstate(_tuple(state))
        return obj
