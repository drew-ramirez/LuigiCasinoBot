"""Memory Match: animated dealer above a native DS card grid."""
from casinogames.card_scene import (
    felt, grid_rect, put_card, scene, png, flip_frames, result_of,
)


def _board(game, overrides=None):
    board=felt(game)
    for i,(symbol,flipped,matched) in enumerate(game.board):
        rect=grid_rect(game,i)
        if overrides and i in overrides:
            art=overrides[i].resize(rect[2:])
            board.alpha_composite(art,rect[:2])
        elif not matched:
            put_card(board,rect,symbol if flipped else None)
    return board


def render_board_image(game, overrides=None):
    return png(scene(game,_board(game,overrides),outcome=result_of(game)))


def make_board_flip_gif(game,pos,symbol,duration=90):
    return flip_frames(game,_board(game),[(grid_rect(game,pos),symbol)],duration=duration)


def make_board_reverse_flip_gif(game,positions,symbols,duration=90):
    return flip_frames(game,_board(game),[(grid_rect(game,p),s) for p,s in zip(positions,symbols)],
                       reverse=True,duration=duration)
