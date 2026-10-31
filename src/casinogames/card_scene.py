"""Shared two-screen DS card presentation; rendering never changes game state."""
import io
from functools import lru_cache
from PIL import Image, ImageDraw
from casinogames.casino_art import background, sprite
from casinogames.assetloader import load_memory_faces, load_memory_backs
from casinogames.roulette_render import compose, dealer_frame, number, text, SMALL

FACES = load_memory_faces()
BACKS = load_memory_backs()
NATIVE = (256, 192)


@lru_cache(maxsize=96)
def card(symbol=None, size=(32, 48)):
    source = FACES.get_face(symbol) if symbol else BACKS.get('back_full')
    return source.resize(size, Image.Resampling.NEAREST)


def put_card(board, rect, symbol=None, width=1.0, raised=0):
    x, y, w, h = rect
    art = card(symbol, (w, h))
    fw = max(1, round(w * width))
    art = art.resize((fw, h), Image.Resampling.NEAREST)
    board.alpha_composite(art, (x + (w-fw)//2, y-raised))


def grid_rect(game, index):
    row, col = divmod(index, game.COLS)
    if game.ROWS == 2:
        return 16 + col*64, 43 + row*77, 32, 48
    w, h = (30, 44) if game.ROWS == 4 else (32, 48)
    step = w + 2
    start = 52 if game.COLS == 5 else 58
    return start + col*step, 8 + row*(h+2), w, h


def poker_rect(index, dealer=False, raised=0):
    return 52 + index*39, (20 if dealer else 134)-raised, 32, 48


def felt(game):
    board = background(NATIVE).copy()
    # This number is the stake, not a fabricated wallet balance.
    bet = sprite('bet').resize((16, 16), Image.Resampling.NEAREST)
    board.alpha_composite(bet, (3, 4))
    amount=max(0,int(game.bet))
    if amount<100:
        number(ImageDraw.Draw(board),(21,5),amount)
    else:
        label=str(amount) if amount<100000 else f'{amount/1000:.0f}k'
        if amount>=1000000:
            label=f'{amount/1000000:.1f}M'
        text(ImageDraw.Draw(board),(20,7),label,SMALL)
    return board


def result_of(game):
    key = game.GAME_KEY
    if key == 'picturepoker':
        return (getattr(game, 'result', None) or {}).get('outcome')
    if key == 'memorymatch':
        if game.is_board_cleared():
            return 'win'
        if game.remaining_attempts <= 0:
            return 'lose'
    if key == 'pairagone':
        if game.is_board_cleared():
            return 'win'
        if not game.has_possible_moves():
            return 'lose'
    if key == 'luckystars' and game.finished:
        values = (game.left_card, game.right_card)
        return 'win' if values[game.picked] > values[1-game.picked] else 'lose'
    return None


def dealer(game, tick=0, *, outcome=None, dealing=False):
    if dealing:
        atlas = sprite('dealer_cards_motion')
        i = min(tick, 8)
        top = atlas.crop((i*256, 0, (i+1)*256, 192))
    else:
        top = dealer_frame(tick if outcome == 'win' and tick<22 else 24 + tick % 26)
    d = ImageDraw.Draw(top)
    if game.GAME_KEY == 'picturepoker':
        # Compact illustrated payout ladder, using this bot's actual paytable.
        from casinogames.picturepoker.PicturePoker import PicturePoker
        rows = [('five_kind',5,0),('four_kind',4,0),('full_house',3,2),
                ('three_kind',3,0),('two_pair',2,2),('one_pair',2,0)]
        for row,(rank,stars,mushrooms) in enumerate(rows):
            y = 3 + row*14
            for i,sym in enumerate(['star']*stars + ['mushroom']*mushrooms):
                top.alpha_composite(card(sym,(7,11)),(3+i*7,y))
            text(d,(42,y),PicturePoker.MULTIPLIER[rank],SMALL)
    if game.GAME_KEY == 'memorymatch':
        text(d,(5,155),'TRIES',SMALL)
        count = max(0, game.remaining_attempts)
        for i in range(min(count,8)):
            top.alpha_composite(sprite('coin'),(5+i*15,173))
        if count > 8:
            text(d,(127,175),count,SMALL)
    if getattr(game,'stars',0):
        star=sprite('slot_star').resize((12,12),Image.Resampling.NEAREST)
        top.alpha_composite(star,(232,139))
        text(d,(228,153),game.stars,SMALL)
    if outcome in ('lose','loss'):
        art=sprite('too_bad')
        top.alpha_composite(art,((256-art.width)//2,153))
    elif outcome == 'tie':
        text(d,(110,160),'DRAW')
    return top


def scene(game, board, tick=0, *, outcome=None, dealing=False):
    return compose(dealer(game,tick,outcome=outcome,dealing=dealing),board)


def png(image):
    out=io.BytesIO()
    image.save(out,'PNG')
    out.seek(0)
    return out


def gif(frames, duration=90, *, tail=0, loop=False):
    # A single palette avoids color flicker. Event animations play exactly once.
    # Sample actual card boards at native scale as well as the room. Resizing
    # the whole two-screen scene made vivid card colors underrepresented.
    boards=[]
    for index in sorted({0,len(frames)//2,len(frames)-1}):
        frame=frames[index]
        boards.append(frame.crop((0,frame.height//2,frame.width,frame.height)).resize(NATIVE,Image.Resampling.NEAREST))
    # The dealer occupies half of the final image, so give both screens equal
    # weight rather than letting repeated green felt consume its palette.
    samples=[dealer_frame(24)]*len(boards)+boards
    atlas=Image.new('RGB',(256*len(samples),192))
    for i,art in enumerate(samples):
        atlas.paste(art.convert('RGB'),(i*256,0))
    palette=atlas.quantize(colors=256)
    encoded=[im.convert('RGB').quantize(palette=palette,dither=Image.Dither.NONE) for im in frames]
    durations=[duration]*len(frames)
    durations[-1]+=tail
    out=io.BytesIO()
    options={'loop':0} if loop else {}
    encoded[0].save(out,'GIF',save_all=True,append_images=encoded[1:],duration=durations,disposal=1,**options)
    out.seek(0)
    return out


def bottom_from(image):
    return image.crop((0,384,512,768)).resize(NATIVE,Image.Resampling.NEAREST)


def waiting_animation(game, board_png):
    """A live room over a stable board; no hidden cards are revealed."""
    with Image.open(board_png) as image:
        bottom=bottom_from(image)
    return gif([scene(game,bottom,i) for i in range(26)],100,loop=True)


def clear_card(board, rect):
    x,y,w,h=rect
    board.paste(background(NATIVE).crop((x,y,x+w,y+h)),(x,y))


def flip_frames(game, board, items, *, reverse=False, dealing=False, duration=90):
    frames=[]
    widths=(1,.5,.08,.5,1)
    for stage,width in enumerate(widths):
        step=board.copy()
        for rect,symbol in items:
            clear_card(step,rect)
            face = stage < 2 if reverse else stage >= 3
            put_card(step,rect,symbol if face else None,width)
        frames.append(scene(game,step,stage,dealing=dealing))
    return gif(frames,duration)
