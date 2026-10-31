"""Picture Poker's two-screen layout with lifted discards and hand ranks."""
from PIL import ImageDraw
from casinogames.casino_art import sprite
from casinogames.card_scene import (
    felt, poker_rect, put_card, card, scene, png, gif, bottom_from, flip_frames,
    clear_card, text, SMALL,
)


def render_hand(hand,reveal=False):
    return [card(symbol if reveal else None) for symbol in hand]


def _board(game,reveal=False,hidden_player=(),hidden_dealer=(),controls=True):
    board=felt(game)
    selected=getattr(game,'selected_discards',set()) if controls and not reveal else set()
    for i,symbol in enumerate(game.luigi_hand):
        put_card(board,poker_rect(i,True),symbol if reveal and i not in hidden_dealer else None)
    for i,symbol in enumerate(game.player_hand):
        put_card(board,poker_rect(i,raised=8 if i in selected else 0),
                 symbol if i not in hidden_player else None)
    for i,sym in enumerate(('star','mario','luigi','flower','mushroom','cloud')):
        board.alpha_composite(card(sym,(12,17)),(8,86+i*17))
    result=getattr(game,'result',None)
    if result and reveal:
        for key,y in [('luigi_rank',71),('player_rank',116)]:
            rank=result.get(key)
            if rank and rank!='junk':
                art=sprite(rank)
                board.alpha_composite(art,((256-art.width)//2+10,y))
    elif controls:
        art=sprite('hit' if selected else 'hold')
        board.alpha_composite(art,(60,82))
    return board


def render_board(game,reveal=False):
    outcome=(game.result or {}).get('outcome') if reveal else None
    return png(scene(game,_board(game,reveal),outcome=outcome))


def render_board_with_hidden(game,hidden_player=(),hidden_dealer=(),reveal_dealer=False):
    return png(scene(game,_board(game,reveal_dealer,hidden_player,hidden_dealer,controls=False)))


def make_deal_flip_gif(game,pos,symbol,base_board,duration=100,dealer=False):
    return flip_frames(game,bottom_from(base_board),[(poker_rect(pos,dealer),symbol)],
                       dealing=True,duration=duration)


def make_discard_flicker_gif(game,pos,base_board,duration=120,dealer=True):
    frames=[]
    base=bottom_from(base_board)
    x,y,w,h=poker_rect(pos,dealer)
    for i in range(5):
        board=base.copy()
        clear_card(board,(x,y,w,h))
        if i<4:
            put_card(board,(x,y-round(i*12),w,h))
        frames.append(scene(game,board,i,dealing=True))
    return gif(frames,duration)


def make_final_reveal_gif(game,duration=100):
    frames=[]
    for stage,width in enumerate((1,.5,.08,.5,1)):
        board=_board(game,controls=False)
        for i,symbol in enumerate(game.luigi_hand):
            rect=poker_rect(i,True)
            clear_card(board,rect)
            put_card(board,rect,symbol if stage>=3 else None,width)
        frames.append(scene(game,board,stage))
    result=game.result or {}
    for i in range(30):
        board=_board(game,True)
        if i>=20 and result.get('outcome')=='win':
            # Decorations follow the win banner. Authoritative payout remains
            # in Discord's summary, including the economy's progression bonus.
            for j in range(6):
                y=100-round((i-20)*4)-j*3
                board.alpha_composite(sprite('coin'),(80+j*17,y))
        frames.append(scene(game,board,i,outcome=result.get('outcome')))
    return gif(frames,duration,tail=1200)
