"""Pair-A-Gone: tight card grid, deck counter, selection and one-shot deals."""
from PIL import ImageDraw
from casinogames.card_scene import (
    felt, grid_rect, put_card, card, scene, png, gif, flip_frames, result_of,
    bottom_from, number,
)


def _board(game, blanks=()):
    board=felt(game)
    for i,symbol in enumerate(game.board):
        if symbol and i not in blanks:
            put_card(board,grid_rect(game,i),symbol)
    draw=ImageDraw.Draw(board)
    for i in game.selected:
        x,y,w,h=grid_rect(game,i)
        draw.rectangle((x,y,x+w-1,y+h-1),outline='#fff595',width=2)
    board.alpha_composite(card(None,(12,18)),(235,12))
    number(draw,(232,33),len(game.deck))
    return board


def render_pair_board(game):
    return png(scene(game,_board(game),outcome=result_of(game)))


def render_pair_board_with_blanks(game,blanks):
    return png(scene(game,_board(game,blanks)))


def make_pair_flicker_gif(game,positions,symbols,duration=60):
    frames=[]
    for stage in range(6):
        board=_board(game,positions)
        for pos,sym in zip(positions,symbols):
            if stage in (0,2):
                put_card(board,grid_rect(game,pos),sym)
        frames.append(scene(game,board,stage))
    return gif(frames,duration)


def make_deal_flip_gif(game,pos,symbol,base_board,duration=120):
    return flip_frames(game,bottom_from(base_board),[(grid_rect(game,pos),symbol)],
                       dealing=True,duration=duration)


def make_simultaneous_flip_gif(game,new_cards,duration=80):
    return flip_frames(game,_board(game,[p for p,_ in new_cards]),
                       [(grid_rect(game,p),s) for p,s in new_cards],dealing=True,duration=duration)
