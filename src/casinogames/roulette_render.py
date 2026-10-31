"""Reference-based DS roulette: two 256x192 screens, presented at 2x.

The surround/rotor and dealer stills are extracted reference artwork, not a
recreated 3D model. Geometry controls the camera, ball and exact winning pocket.
"""
import io
import math
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from casinogames.casino_art import sprite
from casinogames.casino_games import BET_GROUPS
from casinogames.roulette_dividers_3d import render_dividers

SIZE = (512, 768)
SPIN_DURATION_SECONDS = 20.0
# Clockwise texture order, starting at -105 degrees in the overhead reference.
WHEEL_ORDER = (6, 4, 8, 1, 10, 3, 11, 0, 7, 2, 9, 5)
FONT = ImageFont.load_default(size=14)
SMALL = ImageFont.load_default(size=9)
DIGITS = ('01110/11011/11011/11011/11011/11011/01110',
          '00110/01110/00110/00110/00110/00110/01111',
          '11110/00011/00011/00110/01100/11000/11111',
          '11110/00011/00011/01110/00011/00011/11110',
          '00110/01110/11010/11010/11111/00010/00010',
          '11111/11000/11000/11110/00011/00011/11110',
          '01110/11000/11000/11110/11011/11011/01110',
          '11111/00011/00110/00110/01100/01100/01100',
          '01110/11011/11011/01110/11011/11011/01110',
          '01110/11011/11011/01111/00011/00011/01110')

def number(draw, xy, value):
    x,y=xy
    scale=2 if len(str(value)) <= 7 else 1
    for character in str(value):
        for row,bits in enumerate(DIGITS[int(character)].split('/')):
            for col,bit in enumerate(bits):
                if bit=='1':
                    px,py=x+col*scale,y+row*scale
                    draw.rectangle((px+1,py+1,px+scale,py+scale),fill='#38401a')
                    draw.rectangle((px,py,px+scale-1,py+scale-1),fill='#fff595')
        x+=6*scale

def chip_anchor(selection):
    if selection == 'red':
        return 72, 55
    if selection == 'black':
        return 72, 135
    cells = BET_GROUPS[selection]
    return (sum(112 + i % 3 * 48 for i in cells) / len(cells),
            sum(36 + i // 3 * 40 for i in cells) / len(cells))

def landing_angle(pocket, rotation):
    return math.radians(-105 + WHEEL_ORDER.index(pocket) * 30 - rotation)

def text(draw, xy, value, font=FONT):
    draw.text(xy, str(value), font=font, fill='#fff19b', stroke_width=1, stroke_fill='#454018')

def table(game, *, reveal=False, flash=False, credit=1.0):
    board = sprite('roulette_board').resize((256,192), Image.Resampling.NEAREST).copy()
    draw = ImageDraw.Draw(board)
    board.alpha_composite(sprite('coin'), (7,6))
    balance = game.balance_after_wager
    if balance is None:
        balance = game.bet
    if reveal and game.result:
        balance += round(game.result['payout'] * credit)
    number(draw,(25,6),balance)
    occupied = {}
    for index, selection in enumerate(game.placements):
        x,y = chip_anchor(selection)
        stack = occupied.get(selection,0)
        occupied[selection] = stack+1
        board.alpha_composite(sprite('coin'),(int(x+4+stack*2),int(y-3-stack*3)))
    for index in range(len(game.placements),len(game.chips)):
        board.alpha_composite(sprite('coin'),(22,80+index*17))
    if reveal and game.result:
        p = game.result['pocket']
        x, y = 88+p%3*48, 16+p//3*40
        if flash:
            draw.rectangle((x,y,x+48,y+40),outline='#fffde0',width=3)
        if game.result['payout']:
            board.alpha_composite(sprite('coin'),(8,44))
            text(draw,(8,64),'+'+str(game.result['payout']),SMALL)
    return board

@lru_cache(maxsize=1)
def tilted_rotor():
    """Keep the symbol ring, but rebuild the inner slots without overhead spokes.

    Divider tips sit on pocket boundaries, leaving each ball landing centered
    between them. This whole layer rotates underneath the stationary spindle.
    """
    scale=4
    rotor=sprite('roulette_rotor').resize((168*scale,168*scale),Image.Resampling.NEAREST)
    draw=ImageDraw.Draw(rotor)
    def point(radius,angle):
        angle=math.radians(angle)
        return ((84+radius*math.cos(angle))*scale,(84+radius*math.sin(angle))*scale)
    boundaries=[-120+i*30 for i in range(12)]
    rim=[point(58,a) for a in boundaries]
    draw.polygon(rim,fill='#062c12')
    for i,angle in enumerate(boundaries):
        draw.polygon([point(0,0),point(58,angle),point(58,angle+30)],
                     fill='#062c12')
    draw.line(rim+[rim[0]],fill='#929a78',width=scale)
    return rotor.resize((168,168),Image.Resampling.LANCZOS)


def draw_ball(top,x,y,radius):
    """Readable ivory ball with a small contact shadow and rounded highlight."""
    d=ImageDraw.Draw(top)
    d.ellipse((x-radius+2,y-radius+4,x+radius+2,y+radius+3),fill='#51431e')
    d.ellipse((x-radius,y-radius,x+radius,y+radius),fill='#dedda4',outline='#b4ad72')
    d.ellipse((x-radius+1,y-radius+1,x+radius-1,y+radius-2),fill='#fffbd1')
    d.ellipse((x-radius+2,y-radius+1,x+1,y),fill='#ffffeb')


@lru_cache(maxsize=1)
def spindle_contact_shadow():
    # A small soft contact seam under the hub, not an outline around the shaft.
    alpha=Image.new('L',(256,192))
    alpha.paste(sprite('roulette_spindle').getchannel('A'),(0,2))
    ImageDraw.Draw(alpha).rectangle((0,0,255,88),fill=0)
    alpha=alpha.filter(ImageFilter.GaussianBlur(1.2)).point(lambda value:value//3)
    layer=Image.new('RGBA',(256,192),(12,17,5,0))
    layer.putalpha(alpha)
    return layer


def wheel(rotation=0, *, tilt=0, ball_angle=None, ball_radius=112):
    if tilt >= .8:
        top=sprite('roulette_tilt_surround').copy()
        ImageDraw.Draw(top).ellipse((-3,24,259,180),fill='#82652c')
        rotor=tilted_rotor().rotate(rotation,resample=Image.Resampling.BICUBIC)
        projected=rotor.resize((262,156),Image.Resampling.BICUBIC)
        top.alpha_composite(projected,(-3,24))
        top=render_dividers(top,rotation,ball_angle,ball_radius)
        # Gold silhouette alone occludes the rear ball/slots. Divider geometry
        # belongs to the wheel beneath it and must never be baked into this mask.
        top.alpha_composite(spindle_contact_shadow())
        top.alpha_composite(sprite('roulette_spindle'))
    else:
        top=sprite('roulette_surround').copy()
        ImageDraw.Draw(top).ellipse((45,14,215,182),fill='#82652c')
        rotor=sprite('roulette_rotor').rotate(rotation,resample=Image.Resampling.BICUBIC)
        top.alpha_composite(rotor,(46,14))
        if ball_angle is not None:
            draw_ball(top,130+ball_radius*math.cos(ball_angle),98+ball_radius*math.sin(ball_angle),4)
    return top


def compose(top, bottom):
    board=Image.new('RGBA',(256,384),'#004b10')
    board.alpha_composite(top,(0,0))
    board.alpha_composite(bottom,(0,192))
    return board.resize(SIZE,Image.Resampling.NEAREST)

def frame(game, tick=0, *, spinning=False):
    if game.result is not None and not spinning:
        top=dealer_frame(49)
        if game.result['payout']:
            art=sprite('you_win')
            top.alpha_composite(art,((256-art.width)//2,153))
        if not game.result['payout']:
            art=sprite('too_bad')
            top.alpha_composite(art,((256-art.width)//2,153))
        return compose(top,table(game,reveal=True,flash=True))
    return compose(wheel(tick*3),table(game))

def motion_at(seconds, pocket):
    """Continuous rotor with a separate orbit, inward bounce, then carried ball.

    The ball locks to the actual outcome's radial slot while the wheel keeps
    turning. Angles stay unwrapped so the landing cannot jump across 360 degrees.
    """
    rotation = seconds * 60
    target = landing_angle(pocket, rotation)
    if seconds < 9.4:
        angle = landing_angle(pocket, 9.4 * 60) + (seconds - 9.4) * 4.2
        radius = 108
    elif seconds < 11.2:
        p = (seconds - 9.4) / 1.8
        # Damped deflections across the dividers before the ball seats inside.
        angle = target + math.sin(p * math.pi * 3) * .24 * (1 - p)
        radius = 48 + 60 * (1 - p) ** 2 + 9 * abs(math.sin(p * math.pi * 3)) * (1 - p)
    else:
        angle, radius = target, 48
    return rotation, angle, radius


def dealer_frame(index):
    atlas = sprite('dealer_motion')
    index = min(49, max(0, index))
    x, y = index % 10 * 256, index // 10 * 192
    return atlas.crop((x, y, x + 256, y + 192))


def countdown(top, seconds):
    # Each numeral shrinks over its one-second beat, like the reference.
    digit = 3 - int(seconds)
    scale = round(8 - (seconds % 1) * 4)
    mask = Image.new('L', (5 * scale + 4, 7 * scale + 4))
    draw = ImageDraw.Draw(mask)
    for row, bits in enumerate(DIGITS[digit].split('/')):
        for col, bit in enumerate(bits):
            if bit == '1':
                x, y = col * scale + 2, row * scale + 2
                draw.rectangle((x,y,x+scale-1,y+scale-1), fill=255)
    glyph = Image.new('RGBA', mask.size)
    glyph.paste('#64250d', mask=mask.filter(ImageFilter.MaxFilter(5)))
    glyph.paste('#fff595', mask=mask)
    top.alpha_composite(glyph, ((256-glyph.width)//2, (192-glyph.height)//2))


def animation_frames(game):
    if game.result is None:
        # Both motions close seamlessly after six seconds. Chip edits retain
        # this animation rather than replacing it with a frozen board.
        frames = [compose(wheel(i * 6, ball_angle=i * math.tau / 20,
                                ball_radius=108), table(game)) for i in range(60)]
        return frames, [100] * len(frames), True
    frames = []
    durations = []
    # Three countdown beats, direct camera cut, outer orbit, drop and carry.
    for i in range(122):
        seconds = i / 10
        rotation, angle, radius = motion_at(seconds, game.result['pocket'])
        top = wheel(rotation, tilt=int(seconds >= 3), ball_angle=angle, ball_radius=radius)
        if seconds < 3:
            countdown(top, seconds)
        frames.append(compose(top, table(game)))
        durations.append(100)
    # The reveal begins WITH YOU WIN. Its disappearance and Luigi lowering
    # his hands follow in source order; Toad and the room sign also move.
    won = bool(game.result['payout'])
    for i in range(50):
        top = dealer_frame(i if won else 24 + i % 26)
        if not won and i < 22:
            art = sprite('too_bad')
            top.alpha_composite(art, ((256-art.width)//2, 153))
        frames.append(compose(top, table(game, reveal=True, flash=i % 6 < 3, credit=0)))
        durations.append(100)
    # Decorative coins stream toward the wallet; the counter uses the actual
    # payout, never the twelve coins from the recorded reference round.
    for i in range(18):
        top = dealer_frame(24 + i % 26)
        bottom = table(game, reveal=True, flash=i % 6 < 3, credit=(i+1)/18)
        if won:
            for j in range(12):
                p = max(0, min(1, (i - j*.45)/11))
                if p < 1:
                    x0, y0 = 62 + j % 6 * 23, 101 + j // 6 * 22
                    x = round(x0 + (7-x0)*p)
                    y = round(y0 + (6-y0)*p - 35*math.sin(p*math.pi))
                    bottom.alpha_composite(sprite('coin'), (x, y))
        frames.append(compose(top, bottom))
        durations.append(100)
    frames.append(frame(game))
    durations.append(1000)
    return frames, durations, False


def render(game, animated=False):
    out=io.BytesIO()
    if not animated:
        frame(game).save(out,'PNG')
    else:
        frames,durations,loop=animation_frames(game)
        # One shared palette avoids flashing colors across the spin.
        atlas=Image.new('RGB',(256*4,192))
        for i,name in enumerate(('roulette_surround','dealer_idle','dealer_win','roulette_board')):
            atlas.paste(sprite(name).convert('RGB').resize((256,192)),(i*256,0))
        palette=atlas.quantize(colors=192)
        frames=[f.convert('RGB').quantize(palette=palette,dither=Image.Dither.NONE) for f in frames]
        options={'loop':0} if loop else {}
        frames[0].save(out,'GIF',save_all=True,append_images=frames[1:],duration=durations,disposal=1,**options)
    out.seek(0)
    return out
