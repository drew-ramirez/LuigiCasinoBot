import copy
import io
from PIL import Image
import pytest
from casinogames.card_scene import grid_rect, waiting_animation, bottom_from
from casinogames.memorymatch.MemoryMatch import MemoryMatch
from casinogames.memorymatch.MemoryMatchPrint import render_board_image, make_board_flip_gif, make_board_reverse_flip_gif
from casinogames.pairagone.PairAGone import PairAGone
from casinogames.pairagone.PairAGonePrint import render_pair_board, make_pair_flicker_gif, make_simultaneous_flip_gif
from casinogames.picturepoker.PicturePoker import PicturePoker
from casinogames.picturepoker.PicturePokerPrint import render_board, render_board_with_hidden, make_deal_flip_gif, make_final_reveal_gif
from casinogames.luckystars.LuckyStars import LuckyStars
from casinogames.luckystars.LuckyStarsPrint import render_lucky_board, make_slide_animation


def check_gif(data, *, loop=False):
    assert len(data.getvalue())<8_000_000
    with Image.open(data) as im:
        assert im.size==(512,768)
        assert im.n_frames>1
        assert ('loop' in im.info)==loop
        total=0
        for i in range(im.n_frames):
            im.seek(i)
            total+=im.info['duration']
        return total


@pytest.mark.parametrize('stars',[0,1,2,3])
def test_memory_all_difficulties_fit_and_events_preserve_state(stars):
    game=MemoryMatch(1,25,initial_stars=stars)
    before=copy.deepcopy(vars(game))
    for i in range(len(game.board)):
        x,y,w,h=grid_rect(game,i)
        assert 0<=x<x+w<=256 and 0<=y<y+h<=192
    assert Image.open(render_board_image(game)).size==(512,768)
    assert check_gif(make_board_flip_gif(game,0,game.board[0][0]))==450
    assert check_gif(make_board_reverse_flip_gif(game,[0,1],[b[0] for b in game.board[:2]]))==450
    assert vars(game)==before


def test_hidden_memory_symbols_do_not_leak_and_matches_leave_board():
    game=MemoryMatch(1,25)
    original=render_board_image(game).getvalue()
    game.board[0]=('mario',False,False)
    assert render_board_image(game).getvalue()==original
    game.board[0]=('mario',False,True)
    assert render_board_image(game).getvalue()!=original


def test_pair_deck_selection_and_replacements_are_visual_only():
    game=PairAGone(1,25)
    game.selected=[2]
    before=copy.deepcopy(vars(game))
    plain=render_pair_board(game).getvalue()
    assert check_gif(make_pair_flicker_gif(game,[0,1],game.board[:2]))==360
    assert check_gif(make_simultaneous_flip_gif(game,[(18,game.board[18]),(19,game.board[19])]))==400
    assert vars(game)==before
    game.selected=[]
    assert render_pair_board(game).getvalue()!=plain
    game.deck.pop()
    assert Image.open(render_pair_board(game)).size==(512,768)


def test_poker_hidden_hand_stays_hidden_until_final_reveal():
    game=PicturePoker();game.start_round(forced_bet=25)
    game.player_hand=['star']*5
    game.luigi_hand=['cloud']*5
    hidden=render_board(game).getvalue()
    game.luigi_hand=['mario','mario','cloud','cloud','mushroom']
    assert render_board(game).getvalue()==hidden
    game.selected_discards={1}
    assert render_board(game).getvalue()!=hidden
    base=Image.open(render_board_with_hidden(game,hidden_player=[1])).convert('RGBA')
    before=copy.deepcopy(vars(game))
    assert check_gif(make_deal_flip_gif(game,1,'star',base))==500
    assert vars(game)==before
    game.resolve_round()
    before=copy.deepcopy(vars(game))
    assert check_gif(make_final_reveal_gif(game))==4700
    assert vars(game)==before


@pytest.mark.parametrize('pick',[0,1])
def test_lucky_animation_duration_and_hidden_cards(pick):
    game=LuckyStars(25);game.left_card=2;game.right_card=5
    hidden=render_lucky_board(game).getvalue()
    game.left_card=4;game.right_card=1
    assert render_lucky_board(game).getvalue()==hidden
    game.pick_card(pick)
    before=copy.deepcopy(vars(game))
    data,seconds=make_slide_animation(game,duration=70,tail_hold_ms=800)
    assert check_gif(data)==seconds*1000
    assert vars(game)==before


def test_only_waiting_scenes_loop_and_keep_board_unchanged():
    game=MemoryMatch(1,25)
    data=waiting_animation(game,render_board_image(game))
    check_gif(data,loop=True)
    with Image.open(data) as im:
        initial=im.convert('RGB').crop((0,384,512,768)).tobytes()
        im.seek(im.n_frames-1)
        assert im.convert('RGB').crop((0,384,512,768)).tobytes()==initial
