"""Classic Pagat / Richard Sipie Cuttle, not the incompatible Cuttle.cards variant.

https://www.pagat.com/combat/cuttle.html includes the original author's FAQ.
One-offs use explicit asynchronous counter windows even when no Two is held.
The engine stores hidden state; only view() is suitable for Discord rendering.
"""
from copy import deepcopy
from itertools import combinations
import random

RANKS = ('A','2','3','4','5','6','7','8','9','10','J','Q','K')
SUITS = ('C','D','H','S')
DECK = [r+s for s in SUITS for r in RANKS]


def rank(card):
    return RANKS.index(card[:-1])+1


class Cuttle:
    RULES_VERSION = 'pagat-classic-v1'
    RULES = ('Classic Cuttle practice (Pagat/Sipie): reach 21 points, reduced to 14/10/7/5 '
             'with 1/2/3/4 Kings. A–10 score their value or scuttle a weaker point card; '
             'equal values use clubs < diamonds < hearts < spades. A clears points; '
             '2 removes a permanent or counters a one-off; 3 retrieves a scrap; '
             '4 makes the opponent choose two discards; 5 draws two; 6 clears permanents; '
             '7 draws one card that must be played; 9 returns a permanent. '
             'Permanent 8 exposes the opposing hand; J transfers a point stack; '
             'Q protects other cards and one-offs against opposing targeted effects, '
             'but not scuttles or mass clears. Queens never protect Queens. '
             'Explicit Counter/Allow responses can chain Twos. Empty deck permits Pass; '
             'three consecutive passes draw. Dealer gets six, other seat five and first turn. No wallet.')

    def __init__(self, players=(1,0), seed=None):
        self.players = list(players)
        if len(self.players)!=2 or len(set(self.players))!=2 or any(type(p) is not int or p<0 for p in self.players):
            raise ValueError('Cuttle needs two distinct player IDs')
        self.deck = list(DECK)
        random.Random(seed).shuffle(self.deck)
        self.hands = {str(self.players[0]): [self.deck.pop() for _ in range(5)],
                      str(self.players[1]): [self.deck.pop() for _ in range(6)]}
        self.points = []  # {card, owner, jacks:[card codes]}; any Jack removal flips owner.
        self.permanents = []  # {card, owner}; standalone glasses, Queens and Kings.
        self.scrap = []
        self.pending = None
        self.forced = None
        self.turn = self.players[0]
        self.phase = 'play'
        self.passes = 0
        self.result = None
        self.log = ['Non-dealer has five cards and plays first; dealer has six.']
        self.known_hands = {str(p): [] for p in self.players}

    @property
    def finished(self):
        return self.result is not None

    def other(self, player):
        return self.players[1-self.players.index(player)]

    def score(self, player):
        return sum(rank(p['card']) for p in self.points if p['owner']==player)

    def threshold(self, player):
        kings = sum(p['owner']==player and rank(p['card'])==13 for p in self.permanents)
        return (21,14,10,7,5)[kings]

    def queen(self, player):
        return any(p['owner']==player and rank(p['card'])==12 for p in self.permanents)

    def _permanent_targets(self, actor):
        targets = [(p['card'],p['owner']) for p in self.permanents]
        targets += [(j,p['owner']) for p in self.points for j in p['jacks']]
        return [(card,owner) for card,owner in targets
                if owner==actor or rank(card)==12 or not self.queen(owner)]

    @staticmethod
    def _option(action, label, group='Turn'):
        return {'id': action, 'label': label[:100], 'group': group}

    def _card_actions(self, actor, cards):
        actions=[]
        add=lambda action,label,card: actions.append(self._option(action,label,card))
        for card in cards:
            r=rank(card)
            if r<=10:
                add(f'points:{card}',f'{card}: play for {r} points',card)
                for target in self.points:
                    if target['owner']!=actor and (r,SUITS.index(card[-1]))>(rank(target['card']),SUITS.index(target['card'][-1])):
                        add(f'scuttle:{card}:{target["card"]}',f'{card}: scuttle {target["card"]}',card)
            if r in (8,12,13):
                label={8:'expose opponent hand',12:'protect with Queen',13:'lower winning threshold'}[r]
                add(f'permanent:{card}',f'{card}: {label}',card)
            elif r==11:
                for target in self.points:
                    if target['owner']==actor or not self.queen(target['owner']):
                        add(f'jack:{card}:{target["card"]}',f'{card}: transfer {target["card"]} to {self.other(target["owner"])}',card)
            if r in (1,4,5,6,7):
                label={1:'scrap all points',4:'opponent discards two',5:'draw two',6:'scrap all permanents',7:'draw and immediately play'}[r]
                add(f'effect:{card}',f'{card}: {label}',card)
            elif r==3 and self.scrap:
                add(f'effect:{card}',f'{card}: retrieve a scrap after responses',card)
            elif r in (2,9):
                for target,owner in self._permanent_targets(actor):
                    label='scrap' if r==2 else 'return'
                    add(f'effect:{card}:{target}',f'{card}: {label} {target}',card)
        return actions

    def legal_actions(self, player_id):
        if self.finished or player_id!=self.turn:
            return []
        if self.phase=='counter':
            actions=[self._option('allow','Allow the pending effect / response','Response')]
            latest=self.pending['counters'][-1]['actor'] if self.pending['counters'] else self.pending['actor']
            if not self.queen(latest):
                actions += [self._option(f'counter:{c}',f'Counter with {c}','Response') for c in self.hands[str(player_id)] if rank(c)==2]
            return actions
        if self.phase=='rummage':
            return [self._option(f'take:{c}',f'Take {c} from scrap','Scrap') for c in self.scrap]
        if self.phase=='discard':
            hand=self.hands[str(player_id)]
            return [self._option('discard:'+','.join(cards),'Discard '+', '.join(cards),'Discard')
                    for cards in combinations(hand,min(2,len(hand)))]
        if self.phase=='forced':
            return self._card_actions(player_id,[self.forced])
        actions=[self._option('draw','Draw one card')] if self.deck else [self._option('pass','Pass (deck empty)')]
        return actions+self._card_actions(player_id,self.hands[str(player_id)])

    def act(self, player_id, action_id):
        if action_id not in {a['id'] for a in self.legal_actions(player_id)}:
            raise ValueError('This action is not legal in the current Cuttle phase.')
        before=self.to_dict()
        try:
            self._act(player_id,action_id)
            self._remember_exposed()
        except Exception:
            self.__dict__.update(self.from_dict(before).__dict__)
            raise
        return self.view(player_id)

    def _act(self, actor, action):
        parts=action.split(':'); mode=parts[0]
        if self.phase=='counter':
            if mode=='counter':
                card=parts[1]
                self.hands[str(actor)].remove(card)
                self.pending['counters'].append({'actor':actor,'card':card})
                self.turn=self.other(actor)
                self._note(f'{actor} counters with {card}.')
            else:
                pending=self.pending
                countered=len(pending['counters'])%2
                self.scrap.extend(c['card'] for c in pending['counters'])
                pending['counters']=[]
                if countered:
                    self._note(f'{pending["card"]} is countered.')
                    self._complete(pending['actor'],pending['card'])
                else:
                    self._resolve()
            return
        if self.phase=='rummage':
            card=parts[1]
            self.scrap.remove(card)
            self.hands[str(actor)].append(card)
            self._note(f'{actor} retrieves {card}.')
            self._complete(actor,self.pending['card'])
            return
        if self.phase=='discard':
            discarded=parts[1].split(',') if parts[1] else []
            for card in discarded:
                self.hands[str(actor)].remove(card)
                self.scrap.append(card)
            self._note(f'{actor} discards {", ".join(discarded)}.')
            self._complete(self.pending['actor'],self.pending['card'])
            return
        if mode=='draw':
            self.hands[str(actor)].append(self.deck.pop())
            self._note(f'{actor} draws one card.')
            self._complete(actor)
            return
        if mode=='pass':
            self.passes+=1
            self._note(f'{actor} passes ({self.passes}/3).')
            if self.passes==3:
                self.result={'winner':None,'reason':'three consecutive passes','practice_only':True}
                self.phase,self.turn='finished',None
            else:
                self.turn=self.other(actor)
            return
        card=parts[1]
        self.hands[str(actor)].remove(card)
        self.forced=None
        self.passes=0
        if mode=='points':
            self.points.append({'card':card,'owner':actor,'jacks':[]})
            self._note(f'{actor} plays {card} for {rank(card)} points.')
        elif mode=='permanent':
            self.permanents.append({'card':card,'owner':actor})
            self._note(f'{actor} plays permanent {card}.')
        elif mode=='scuttle':
            target=next(p for p in self.points if p['card']==parts[2])
            self.points.remove(target)
            self.scrap.extend([target['card']]+target['jacks']+[card])
            self._note(f'{actor} scuttles {target["card"]} with {card}.')
        elif mode=='jack':
            target=next(p for p in self.points if p['card']==parts[2])
            target['jacks'].append(card)
            target['owner']=self.other(target['owner'])
            self._note(f'{card} transfers {target["card"]} to {target["owner"]}.')
        elif mode=='effect':
            self.pending={'actor':actor,'card':card,'target':parts[2] if len(parts)>2 else None,'counters':[]}
            self.phase,self.turn='counter',self.other(actor)
            self._note(f'{actor} offers one-off {card}'+(f' targeting {parts[2]}.' if len(parts)>2 else '.'))
            return
        self._complete(actor)

    def _remove_permanent(self, card, *, returning=False):
        for permanent in self.permanents:
            if permanent['card']==card:
                owner=permanent['owner']
                self.permanents.remove(permanent)
                break
        else:
            target=next(p for p in self.points if card in p['jacks'])
            owner=target['owner']
            target['jacks'].remove(card)
            target['owner']=self.other(owner)
        if returning:
            self.hands[str(owner)].append(card)
        else:
            self.scrap.append(card)

    def _resolve(self):
        actor,card,target=self.pending['actor'],self.pending['card'],self.pending['target']
        r=rank(card)
        if r==1:
            for point in self.points:
                self.scrap.extend([point['card']]+point['jacks'])
            self.points=[]
        elif r==2:
            self._remove_permanent(target)
        elif r==3:
            if self.scrap:
                self.phase,self.turn='rummage',actor
                return
        elif r==4:
            opponent=self.other(actor)
            if self.hands[str(opponent)]:
                self.phase,self.turn='discard',opponent
                return
        elif r==5:
            for _ in range(min(2,len(self.deck))):
                self.hands[str(actor)].append(self.deck.pop())
        elif r==6:
            targets=[p['card'] for p in self.permanents]+[j for p in self.points for j in p['jacks']]
            for target in targets:
                self._remove_permanent(target)
        elif r==7:
            self.scrap.append(card)
            self.pending=None
            if self.deck:
                self.forced=self.deck.pop()
                self.hands[str(actor)].append(self.forced)
                self.phase,self.turn='forced',actor
                self._note(f'{actor} must immediately play drawn {self.forced}.')
                if self._card_actions(actor,[self.forced]):
                    return
                self.hands[str(actor)].remove(self.forced)
                self.scrap.append(self.forced)
                self._note(f'{self.forced} has no legal play and is scrapped.')
            self._complete(actor)
            return
        elif r==9:
            self._remove_permanent(target,returning=True)
        self._note(f'{card} resolves.')
        self._complete(actor,card)

    def _complete(self, actor, card=None):
        if card:
            self.scrap.append(card)
        self.pending,self.forced=None,None
        self.phase='play'
        self.passes=0
        for player in (actor,self.other(actor)):
            if self.score(player)>=self.threshold(player):
                self.result={'winner':player,'reason':'point threshold reached',
                             'scores':{str(p):self.score(p) for p in self.players},'practice_only':True}
                self.phase,self.turn='finished',None
                return
        self.turn=self.other(actor)

    def _note(self, message):
        self.log=(self.log+[message])[-6:]

    def _remember_exposed(self):
        for player in self.players:
            exposed=any(p['owner']==self.other(player) and rank(p['card'])==8 for p in self.permanents)
            if exposed:
                self.known_hands[str(player)]=sorted(set(self.known_hands[str(player)]+self.hands[str(player)]))

    def bot_action(self):
        actions=self.legal_actions(self.turn)
        if not actions:
            raise ValueError('No legal action')
        actor=self.turn
        def merit(option):
            parts=option['id'].split(':'); mode=parts[0]
            if mode=='counter': return 90
            if mode=='allow': return 0
            if mode=='discard': return -sum(rank(c) if rank(c)<=10 else 8 for c in parts[1].split(','))
            if mode=='take': return rank(parts[1]) if rank(parts[1])<=10 else 8
            if mode=='points': return 1000 if self.score(actor)+rank(parts[1])>=self.threshold(actor) else 40+rank(parts[1])
            if mode=='jack':
                point=next(p for p in self.points if p['card']==parts[2])
                return 60+rank(point['card']) if point['owner']!=actor else -20
            if mode=='permanent': return {13:55,12:30,8:20}[rank(parts[1])]
            if mode=='scuttle': return 35+rank(parts[2])
            if mode=='draw': return 10
            if mode=='effect':
                r=rank(parts[1])
                return {1: 45 if self.score(self.other(actor))>self.score(actor) else -5,
                        2:25,3:25,4:15,5:35,6:5,7:20,9:5}[r]
            return -100
        return max(actions,key=merit)['id']

    def concede(self, player_id):
        if player_id not in self.players or self.finished:
            raise ValueError('No active seat to concede.')
        self.result={'winner':self.other(player_id),'reason':'conceded','practice_only':True}
        self.phase,self.turn='finished',None

    def view(self, viewer_id=None):
        hands={}
        for player in self.players:
            exposed=any(p['owner']==self.other(player) and rank(p['card'])==8 for p in self.permanents)
            hands[str(player)]=list(self.hands[str(player)]) if player==viewer_id or exposed else [None]*len(self.hands[str(player)])
        if self.forced and self.turn!=viewer_id:
            hands[str(self.turn)]=[self.forced if c==self.forced else visible for c,visible in zip(self.hands[str(self.turn)],hands[str(self.turn)])]
        return {'kind':'cuttle','players':list(self.players),'turn':self.turn,'phase':self.phase,
                'hands':hands,'table':[p['card'] for p in self.points]+[j for p in self.points for j in p['jacks']]+[p['card'] for p in self.permanents],
                'points':deepcopy(self.points),'permanents':deepcopy(self.permanents),
                'scores':{str(p):self.score(p) for p in self.players},
                'thresholds':{str(p):self.threshold(p) for p in self.players},
                'remaining_deck':len(self.deck),'scrap_top':self.scrap[-1] if self.scrap else None,
                'scrap_count':len(self.scrap),'pending':deepcopy(self.pending),
                'known_hands':deepcopy(self.known_hands),'log':list(self.log),'result':deepcopy(self.result)}

    def to_dict(self):
        return {'version':self.RULES_VERSION,**deepcopy(self.__dict__)}

    @classmethod
    def from_dict(cls,state):
        data=deepcopy(state)
        if data.pop('version')!=cls.RULES_VERSION:
            raise ValueError('Unsupported Cuttle rules version')
        game=cls.__new__(cls)
        game.__dict__.update(data)
        return game
