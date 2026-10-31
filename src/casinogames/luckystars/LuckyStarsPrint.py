"""Lucky Stars: centered choice followed by dealer/player card separation."""
from PIL import Image, ImageDraw
from casinogames.assetloader import load_lucky_assets
from casinogames.card_scene import felt, card, scene, png, gif, result_of, text, SMALL

assets=load_lucky_assets()


def make_card_with_stars(star_count, game=None):
    art=assets['blank_full'].resize((32,48),Image.Resampling.NEAREST)
    star=assets['star'].resize((9,9),Image.Resampling.NEAREST)
    positions={1:[(12,20)],2:[(12,12),(12,28)],3:[(12,8),(5,28),(19,28)],
               4:[(5,10),(19,10),(5,28),(19,28)],
               5:[(5,7),(19,7),(12,20),(5,33),(19,33)]}
    for xy in positions[star_count]:
        art.alpha_composite(star,xy)
    return art


def _board(game,reveal=False,progress=1,flip_width=1,face=True):
    board=felt(game)
    if reveal:
        text(ImageDraw.Draw(board),(105,3),'LUIGI',SMALL)
        text(ImageDraw.Draw(board),(110,181),'YOU',SMALL)
    for i,x in enumerate((80,144)):
        y=72
        if reveal:
            target=128 if i==game.picked else 18
            y=round(y+(target-y)*progress)
        art=make_card_with_stars((game.left_card,game.right_card)[i]) if reveal and face else card()
        w=max(1,round(32*flip_width))
        board.alpha_composite(art.resize((w,48),Image.Resampling.NEAREST),(x+(32-w)//2,y))
    return board


def render_lucky_board(game,reveal=False):
    return png(scene(game,_board(game,reveal),outcome=result_of(game) if reveal else None))


def make_slide_animation(game,duration=120,tail_hold_ms=2500):
    frames=[]
    for i in range(1,9):
        p=i/8
        frames.append(scene(game,_board(game,True,p*p*(3-2*p),face=False),i))
    for stage,width in enumerate((1,.5,.08,.5,1)):
        frames.append(scene(game,_board(game,True,1,width,stage>=3),stage+8))
    # Return the exact playback duration so Discord does not cut off the reveal.
    return gif(frames,duration,tail=tail_hold_ms), (len(frames)*duration+tail_hold_ms)/1000


def draw_card_face(star_count):
    return make_card_with_stars(star_count)
