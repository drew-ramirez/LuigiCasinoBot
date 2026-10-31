"""Viewer-safe DS tables for the seven practice duels.

Only projected dictionaries enter this module. Text sits directly on the felt;
the existing dealer screen is never covered by headings or status panels.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from PIL import Image, ImageDraw

from casinogames.card_scene import gif, png
from casinogames.casino_art import background
from casinogames.expansion_render import _fit, _scene, TINY, GOLD
from casinogames.mario_cards import face as mario_face

KINDS = {'triple_triad', 'red7', 'scopa', 'cuttle', 'pazaak', 'platoon', 'casino_war'}
SEATS = ('#6fbdff', '#ff9a85')


@dataclass(frozen=True)
class DuelSlot:
    rect: tuple
    face: object
    style: str = 'standard'
    owner: int | None = None
    identity: str | None = None


def _seat(players, player):
    return 'LUIGI' if player == 0 else f'P{players.index(player)+1}'


def _visible_hand(state):
    hands = state.get('hands', {})
    players = state.get('players', [])
    if str(state.get('viewer_id')) in hands:
        return str(state['viewer_id'])
    return next((str(p) for p in players if any(v is not None for v in hands.get(str(p), []))),
                str(players[0]) if players else '')


def _layout(kind, state):
    """Return bounded native-screen slots and small labels, with no hidden lookup."""
    if kind not in KINDS:
        raise ValueError('Unknown duel table')
    slots, labels = {}, []
    players = state.get('players', [])
    hands = state.get('hands', {})
    scores = state.get('scores', {})
    own = _visible_hand(state)

    def label(x, y, value, width=244, color=GOLD):
        labels.append((x, y, str(value), width, color))

    def add(key, face, rect, style='standard', owner=None, identity=None):
        if identity is None and face is not None and not isinstance(face, dict):
            identity = str(face) if style in ('standard', 'compact', 'red7') else None
        slots[key] = DuelSlot(rect, face, style, owner, identity)

    def row(key, values, y, *, x=7, width=242, height=36, style='standard', owner=None):
        values = list(values)
        # Keep every card in its native portrait shape. Busy rows overlap as
        # physical fans instead of compressing the artwork into narrow strips.
        w=round(height*2/3)
        step=min(w+4,(width-w)/max(1,len(values)-1))
        for i,value in enumerate(values):
            add(f'{key}:{i}',value,(x+i*step,y,w,height),style,owner)

    if kind == 'triple_triad':
        for seat, player in enumerate(players):
            x = 4 if seat == 0 else 200
            label(x, 3, f'{_seat(players,player)} {scores.get(str(player),5)}', 40, SEATS[seat])
            for i, value in enumerate(hands.get(str(player), [])):
                add(f'h{player}:{i}', value, (x+(i%2)*28,20+(i//2)*51,24,36), 'triad', seat,
                    f"triad:{seat}:{value['id']}" if value else None)
        for i, entry in enumerate(state.get('table', [None]*9)):
            r,c = divmod(i,3)
            rect = (76+c*34, 16+r*54, 28,42)
            owner = players.index(entry['owner']) if entry else None
            value = entry['card'] if entry else ''
            add(f'board:{i}', value, rect, 'triad', owner,
                f"triad:{owner}:{value['id']}" if entry else None)
            label(rect[0]+7, rect[1]+43, f'{chr(65+r)}{c+1}', 28)
        label(62,180,'OPEN  /  N E S W',145)
    elif kind == 'red7':
        palettes = state.get('palettes', {})
        for seat, player in enumerate(players):
            y = 4+seat*49
            label(7,y,f'{_seat(players,player)} PALETTE',135,SEATS[seat])
            row(f'palette:{player}',palettes.get(str(player),[]),y+12,style='red7',owner=seat)
        label(7,105,f"{state.get('rule','red').upper()}: {state.get('rule_name','Highest card')}",242)
        label(7,128,'HAND  ' + ' / '.join(f'{_seat(players,p)} {len(hands.get(str(p),[]))}' for p in players))
        row('hand',hands.get(own,[]),143,height=42,style='red7')
    elif kind == 'pazaak':
        if state.get('phase') == 'side_deck':
            label(8,7,'SIDE DECK  /  SELECT TEN MODIFIERS')
            values=hands.get(own,[])
            for i in range(2):
                row(f'side{i}', values[i*5:i*5+5], 25+i*70, x=20,width=216,height=60,style='modifier')
            label(8,174,'CONFIRM YOUR SELECTION TO DEAL')
        else:
            for seat,player in enumerate(players):
                y=4+seat*52
                total=state.get('totals',{}).get(str(player),0)
                stood=' STAND' if state.get('standing',{}).get(str(player)) else ''
                label(7,y,f'{_seat(players,player)}  {total} / 20{stood}   SETS {scores.get(str(player),0)}',242,SEATS[seat])
                row(f'board:{player}',state.get('boards',{}).get(str(player),[]),y+13,height=36,style='modifier',owner=seat)
            label(7,115,f"SIDE HAND   /   SET {state.get('set_number',1)}")
            row('hand',hands.get(own,[]),134,height=48,style='modifier')
    elif kind == 'platoon':
        for seat,player in enumerate(players):
            y=4+seat*74
            label(7,y,f'{_seat(players,player)}  FLAGS {scores.get(str(player),0)}',180,SEATS[seat])
            for i,pile in enumerate(state.get('formations',{}).get(str(player),[])):
                x=7+i*49
                label(x,y+12,f"{pile['label']} {pile['count']}{' DONE' if pile.get('spent') else ''}",46)
                values=pile.get('cards',[])
                rows=max(1,(len(values)+1)//2)
                step=15/max(1,rows-1)
                for j,value in enumerate(values):
                    col,r=j%2,j//2
                    add(f'pile:{player}:{i}:{j}',value,(x+col*22,y+25+r*step,20,30),'compact',seat)
        if state.get('phase') in ('formation','setup','arrange','placement'):
            label(7,149,'UNASSIGNED HAND  /  ASSIGN TO A-E')
            assignments=state.get('assignments')
            values=[(i,value) for i,value in enumerate(hands.get(own,[]))
                    if assignments is None or i>=len(assignments) or assignments[i] is None]
            for position,(i,value) in enumerate(values):
                add(f'hand:{i}',value,(7+position*23,161,19,28))
        else:
            prediction=state.get('predictions',{})
            label(7,149,'PREDICTIONS  '+ ' / '.join(f'{_seat(players,int(p))}: {_seat(players,v[0])}-{chr(65+v[1])}' for p,v in prediction.items()),242)
            row('battle',state.get('table',[]),161,height=28)
    elif kind == 'casino_war':
        for seat,player in enumerate(players):
            x=48+seat*111
            label(x-7,18,_seat(players,player),75,SEATS[seat])
            values=hands.get(str(player),[None])
            add(f'war:{player}',values[0] if values else None,(x,36,44,66),owner=seat)
        label(19,120,f"STAKE {state.get('stake',0)}   COMMITTED {state.get('committed',0)}")
        result=state.get('result')
        if result:
            label(19,141,f"RETURN {result.get('gross',0)}   NET {result.get('net',0):+}")
            label(19,162,result.get('outcome',result.get('reason','')).upper())
        else:
            label(19,145,'TIE: SURRENDER OR GO TO WAR' if state.get('phase')=='tie' else 'HIGH CARD WINS')
    elif kind == 'scopa':
        label(7,4,' / '.join(f"{_seat(players,p)}  {'TOTAL' if state.get('result') else 'SWEEPS'} {scores.get(str(p),0)}" for p in players))
        values=state.get('table',[])
        # A large table can occupy two rows without covering the private hand.
        split=max(10,(len(values)+1)//2) if len(values)>10 else len(values)
        row('table0',values[:split],24,height=36)
        row('table1',values[split:],67,height=36)
        if state.get('result'):
            breakdown=state['result'].get('breakdown',{})
            for seat,player in enumerate(players):
                detail=breakdown.get(str(player),{})
                for i,key in enumerate(('cards','coins','settebello','primiera','sweeps')):
                    label(12+seat*124,29+i*14,f"{key.upper()} {detail.get(key,0)}",120,SEATS[seat])
        label(7,108,f"DECK {state.get('remaining_deck',0)}   DIAMONDS = COINS")
        label(7,128,'YOUR HAND')
        row('hand',hands.get(own,[]),141,height=45)
    elif kind == 'cuttle':
        for seat,player in enumerate(players):
            y=3+seat*49
            threshold=state.get('thresholds',{}).get(str(player),21)
            label(7,y,f'{_seat(players,player)}  {scores.get(str(player),0)} / {threshold}',140,SEATS[seat])
            points=[v for v in state.get('points',[]) if v['owner']==player]
            permanents=[v['card'] for v in state.get('permanents',[]) if v['owner']==player]
            cards=[]
            for point in points:
                cards.append(point['card'])
                cards.extend(point.get('jacks',[]))
            row(f'points:{player}',cards,y+13,x=7,width=165,height=36,owner=seat)
            row(f'permanents:{player}',permanents,y+13,x=179,width=70,height=36,owner=seat)
        label(7,102,'POINTS + JACKS',165)
        label(179,102,'ROYALS',70)
        pending=state.get('pending')
        label(7,116,f"{state.get('phase','play').upper()}  /  SCRAP {state.get('scrap_top') or '-'}" +
              (f"  /  {pending['card']}" if pending else ''))
        values=hands.get(own,[])
        if len(values)>13:
            split=(len(values)+1)//2
            row('hand0',values[:split],130,height=28)
            row('hand1',values[split:],160,height=28)
        else:
            row('hand',values,141,height=45)
    return slots,labels


def _art(slot):
    """Use the shared Mario frame for every visible card and covered card."""
    if slot.face == '':
        return None
    _,_,w,h=map(round,slot.rect)
    return mario_face(slot.face,slot.style,(w,h))


def _draw(board, slot, squeeze=1):
    art=_art(slot)
    x,y,w,h=map(round,slot.rect)
    fw=max(1,round(w*squeeze))
    x+=(w-fw)//2
    if art is None:
        ImageDraw.Draw(board).rounded_rectangle((x,y,x+fw-1,y+h-1),radius=2,outline='#50734b')
    else:
        if fw!=w:
            art=art.resize((fw,h),Image.Resampling.NEAREST)
        board.alpha_composite(art,(x,y))
    if slot.owner is not None:
        # Seat color belongs beside the card, never over its Mario frame.
        ImageDraw.Draw(board).line((x-2,y+4,x-2,y+h-5),fill=SEATS[slot.owner],width=1)


def _base(labels):
    board=background((256,192)).copy()
    draw=ImageDraw.Draw(board)
    for x,y,value,width,color in labels:
        _fit(draw,(x,y),value,width=width,font=TINY,fill=color)
    return board


def _still(kind,state):
    slots,labels=_layout(kind,state)
    board=_base(labels)
    for slot in slots.values(): _draw(board,slot)
    return _scene(board)


def _transition(kind,previous,current,steps=8):
    before,_=_layout(kind,previous) if previous is not None else ({},[])
    after,labels=_layout(kind,current)
    # Identity matching moves known cards between hand/table/capture areas.
    # Unseen cards are matched only by their public position, never a secret ID.
    used=set(); matches={}
    for key,new in after.items():
        oldkey=key if key in before and key not in used and before[key].face==new.face else None
        if oldkey is None:
            oldkey=next((k for k,v in before.items() if k not in used and new.identity is not None
                         and new.identity==v.identity),None)
        if oldkey is None and key in before and key not in used:
            oldkey=key
        if oldkey is not None:
            matches[key]=before[oldkey];used.add(oldkey)
    frames=[]
    for step in range(steps):
        t=(step+1)/steps; eased=1-(1-t)**3
        board=_base(labels)
        for key,old in before.items():
            if key not in used and t<.875:
                x,y,w,h=old.rect
                _draw(board,replace(old,rect=(x,y+(188-y)*eased,w,h)),squeeze=1-t)
        for key,new in after.items():
            old=matches.get(key)
            if old is None:
                x,y,w,h=new.rect
                source=(113,-h,w,h)
                rect=tuple(a+(b-a)*eased for a,b in zip(source,new.rect))
                _draw(board,replace(new,rect=rect))
            else:
                rect=tuple(a+(b-a)*eased for a,b in zip(old.rect,new.rect))
                changed=old.face!=new.face or old.owner!=new.owner
                show=old if changed and t<.5 else new
                _draw(board,replace(show,rect=rect),squeeze=max(.08,abs(2*t-1)) if changed else 1)
        frames.append(_scene(board,step,dealing=True))
    frames.append(_still(kind,current))
    return frames


def render_duel(kind, public, *, previous=None, animate=False):
    """Render a single viewer's projection, optionally after an accepted action.

    Both snapshots must belong to the same viewer. Arbitrary extra fields are
    ignored, including deck/RNG/known-hand history. The caller owns redaction.
    """
    if not animate: return png(_still(kind,public))
    frames=[_still(kind,previous)] if previous is not None else []
    frames.extend(_transition(kind,previous,public))
    return gif(frames,85,tail=1000)


def render_sequence(kind, projections):
    """Animate every accepted human/bot step, preserving intermediate reactions."""
    projections=list(projections)
    if not projections: raise ValueError('At least one projection is required')
    if len(projections)==1: return render_duel(kind,projections[0])
    # Keep every accepted state while bounding tween frames for Discord uploads.
    steps=max(1,min(8,80//(len(projections)-1)-1))
    frames=[_still(kind,projections[0])]
    for before,after in zip(projections,projections[1:]):
        frames.extend(_transition(kind,before,after,steps=steps))
    encoded=gif(frames,85,tail=1000)
    if encoded.getbuffer().nbytes <= 8_000_000:
        return encoded
    # An unusually long sequence retains all accepted states first; if even
    # those exceed the upload limit, progressively sample the long replay.
    frames=[_still(kind,state) for state in projections]
    encoded=gif(frames,180,tail=1000)
    while encoded.getbuffer().nbytes > 8_000_000 and len(frames)>2:
        frames=frames[:-1:2]+[frames[-1]]
        encoded=gif(frames,180,tail=1000)
    return encoded
