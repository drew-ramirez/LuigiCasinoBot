"""DS table presentation for expansion games, fed *only* viewer-safe state.

No engine, deck, RNG or wallet is accepted here. Event GIFs interpolate saved
card slots; they do not decide an outcome or conceal a frame-timed action.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from types import SimpleNamespace

from PIL import Image, ImageDraw, ImageFont

from casinogames.card_scene import card, dealer, gif, png
from casinogames.casino_art import background
from casinogames.roulette_render import compose, SMALL

KINDS = {
    "memory_master", "pairagone_endless", "pairagone_on", "pairagone_and_on",
    "blackjack", "thrilling_cards", "fortune_tower",
}
GRID_KINDS = {"memory_master", "pairagone_endless", "pairagone_on", "pairagone_and_on"}
TINY = ImageFont.load_default(size=8)
RANK = ImageFont.load_default(size=11)
IVORY = "#fff4ce"
GOLD = "#f8d76c"


@dataclass(frozen=True)
class Slot:
    rect: tuple
    face: object
    style: str = "standard"
    selected: bool = False


def _fit(draw, xy, value, width=244, font=SMALL, fill=GOLD):
    label = str(value).translate({8212: "-", 8211: "-", 8217: chr(39), 215: "x", 8594: "->"})
    while label and draw.textlength(label, font=font) > width:
        label = label[:-1]
    draw.text(xy, label, font=font, fill=fill, stroke_width=1, stroke_fill="#26371b")


@lru_cache(maxsize=512)
def _face(value, style, size):
    from casinogames.mario_cards import face
    return face(value, style, size)


def _draw_slot(board, slot, *, squeeze=1):
    x,y,w,h = map(round,slot.rect)
    if slot.face == "":
        ImageDraw.Draw(board).rounded_rectangle((x,y,x+w-1,y+h-1),radius=2,
                                                outline="#50734b")
        return
    art = _face(slot.face,slot.style,(w,h))
    fw=max(1,round(w*squeeze))
    if fw != w:
        art=art.resize((fw,h),Image.Resampling.NEAREST)
    x += (w-fw)//2
    d=ImageDraw.Draw(board)
    d.rounded_rectangle((x+2,y+3,x+fw+1,y+h+2),radius=2,fill="#162c1a")
    if slot.selected:
        d.rounded_rectangle((x-2,y-2,x+fw+1,y+h+1),radius=3,outline=GOLD,width=2)
    board.alpha_composite(art,(x,y))


def _slots(kind, state):
    slots={}
    if kind in GRID_KINDS:
        cols=int(state.get("cols",5)); rows=int(state.get("rows",4))
        w,h=(28,42) if rows==3 else (24,36)
        dx,dy=(37,58) if cols==6 else (43,44)
        start=(256-(cols-1)*dx-w)//2
        selected=state.get("selected",[])
        for i,value in enumerate(state.get("cards",[])):
            r,c=divmod(i,cols)
            slots[str(i)]=Slot((start+c*dx,4+r*dy,w,h),value,"memory",i in selected)
    elif kind=="blackjack":
        for row,cards in [("dealer",state.get("dealer",[]))]:
            step=min(30,210/max(1,len(cards)))
            for i,value in enumerate(cards):
                slots[f"{row}{i}"]=Slot((20+i*step,22,28,42),value)
        hands=state.get("hands",[])
        for h,hand in enumerate(hands):
            cards=hand["cards"]; panel=236/max(1,len(hands))
            step=min(29,(panel-30)/max(1,len(cards)-1))
            for i,value in enumerate(cards):
                slots[f"h{h}c{i}"]=Slot((10+h*panel+i*step,109,28,42),value,
                                         selected=h==state.get("active_hand") and i==0)
    elif kind=="fortune_tower":
        slots["gate"]=Slot((116,2,22,33),state.get("gate"),"tower")
        rows=state.get("rows",[])
        for r,row in enumerate(rows):
            active=r==len(rows)-1
            w,h,gap,y=(24,36,5,141) if active else (18,27,11,38+r*16)
            x=(256-(len(row)*(w+gap)-gap))//2
            for c,value in enumerate(row):
                slots[f"r{r}c{c}"]=Slot((x+c*(w+gap),y,w,h),value,"tower",active)
    elif kind=="thrilling_cards":
        seats=state.get("seats",[])
        count=len(seats)
        for i,seat in enumerate(seats):
            x=20+i*(210/max(1,count-1)) if count>1 else 113
            # Four seats occupy compact booths around a central pot.
            x=min(x,208)
            y=30 if i%2==0 else 126
            slots[str(i)]=Slot((x,y,28,42),seat.get("card"),
                               selected=seat.get("player_id")==state.get("turn"))
    return slots


def _board(kind,state):
    board=background((256,192)).copy()
    d=ImageDraw.Draw(board)
    if kind in GRID_KINDS:
        cols=int(state.get("cols",5))
        for i,slot in _slots(kind,state).items():
            x,y,w,h=slot.rect; r,c=divmod(int(i),cols)
            _fit(d,(x+8,y+h+1),f"{chr(65+r)}{c+1}",font=TINY)
    elif kind=="blackjack":
        _fit(d,(12,5),"LUIGI  " + (str(state["dealer_total"]) if state.get("dealer_total") is not None else "?"))
        d.line((10,82,246,82),fill="#b8a767")
        hands=state.get("hands",[])
        for i,hand in enumerate(hands):
            from casinogames.blackjack import hand_total
            total,soft=hand_total(hand["cards"])
            x=10+i*(236/max(1,len(hands)))
            _fit(d,(x,94),f"HAND {i+1}   {total}{' soft' if soft else ''}",width=110)
            result=state.get("result")
            label=result["hands"][i]["outcome"].upper() if result else "STOOD" if hand.get("done") else "PLAY"
            _fit(d,(x,158),f"{label}  /  {hand['bet']}",width=110)
        _fit(d,(10,180),f"COMMITTED {state.get('total_committed',0)}",font=TINY)
    elif kind=="fortune_tower":
        _fit(d,(8,6),"GATE USED" if state.get("gate_used") else "GATE READY",width=100,font=TINY)
        _fit(d,(168,6),f"SET x{state.get('multiplier',1)}",width=80,font=TINY)
        _fit(d,(8,22),f"ROW {state.get('row_number',2)} OF 8",width=100,font=TINY)
        _fit(d,(168,22),f"OFFER {state.get('offer',0)}",width=80,font=TINY)
        _fit(d,(10,182),"H = HERO  /  PRACTICE POINTS",font=TINY)
    elif kind=="thrilling_cards":
        seats=state.get("seats",[])
        d.rounded_rectangle((72,76,184,109),radius=12,fill="#173820",outline="#c0ad68")
        _fit(d,(86,82),f"POT  {state.get('pot',0)}",width=90)
        for i,seat in enumerate(seats):
            x,y,w,h=_slots(kind,state)[str(i)].rect
            _fit(d,(x-5,y-15),f"SEAT {i+1}",width=48,font=TINY)
            _fit(d,(x-4,y+h+5),"FOLDED" if seat.get("folded") else f"IN {seat.get('committed',0)}",width=50,font=TINY)
        _fit(d,(8,181),"PRIVATE CARDS VIA YOUR OWN VIEW",font=TINY)
    return board


def _scene(board,tick=0,dealing=False):
    # Use the existing dealer scene without covering its artwork with banners.
    # Game titles, scores and status remain in the Discord message.
    top=dealer(SimpleNamespace(GAME_KEY="expansion"),tick,dealing=dealing)
    return compose(top,board)


def render_table(kind, public, *, previous=None, animate=False):
    """Render a projected state; previous must have the SAME viewer identity.

    PNGs remain fully readable without animation. GIFs play once, include a
    final resting frame, and contain no state absent from these projections.
    Unknown dictionary keys are ignored (never encoded in image metadata).
    """
    if kind not in KINDS:
        raise ValueError("Unknown expansion table")
    current=_slots(kind,public)
    base=_board(kind,public)
    final=base.copy()
    for slot in current.values():
        _draw_slot(final,slot)
    if not animate:
        return png(_scene(final))
    before=_slots(kind,previous) if previous is not None else {}
    removed = []
    sources = before
    if (kind in GRID_KINDS - {"memory_master"} and previous is not None
            and public.get("score",0) == previous.get("score",0) + 2
            and len(public.get("removed",[])) == 2):
        removed = [before[str(i)] for i in public["removed"]]
        survivors = [slot for key,slot in before.items() if int(key) not in public["removed"]]
        sources = {str(i): slot for i,slot in enumerate(survivors)}
    frames=[]
    if previous is not None:
        oldboard=_board(kind,previous)
        for slot in before.values():
            _draw_slot(oldboard,slot)
        frames.append(_scene(oldboard))
    for step in range(9):
        t=(step+1)/9
        eased=1-(1-t)**3
        board=base.copy()
        if t < .65:
            for old in removed:
                x,y,w,h=old.rect
                _draw_slot(board,Slot((x,y-30*eased,w,h),old.face,old.style),squeeze=max(.1,1-t))
        for key,slot in current.items():
            old=sources.get(key)
            if old is None or old.face=="" and slot.face!="":
                x,y,w,h=slot.rect
                moving=Slot((x,(y+42)*eased-42,w,h),slot.face,slot.style,slot.selected)
                _draw_slot(board,moving)
            elif old.face != slot.face:
                face=old.face if t<.5 else slot.face
                squeeze=max(.06,abs(2*t-1))
                _draw_slot(board,Slot(slot.rect,face,slot.style,slot.selected),squeeze=squeeze)
            elif old.rect != slot.rect:
                rect=tuple(a+(b-a)*eased for a,b in zip(old.rect,slot.rect))
                _draw_slot(board,Slot(rect,slot.face,slot.style,slot.selected))
            else:
                _draw_slot(board,slot)
        frames.append(_scene(board,step,dealing=True))
    frames.append(_scene(final))
    return gif(frames,90,tail=1000)
