"""Expansion card faces composed from the existing SM64 DS frame and sprites.

The frame and motifs come from assets/cardart/cards.gif, already used by Lucky
Stars and Pair-a-Gone. Rule-bearing ranks, suits and values stay authoritative;
character art is decoration, never an alternate rank or suit mapping.
"""
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1] / 'assets' / 'cardart'
COLORS = {'R':'#c82435', 'O':'#d46208', 'Y':'#f1cb27', 'G':'#238849',
          'B':'#2265b8', 'I':'#51399c', 'V':'#9a39a8'}
MOTIFS = {'star':(49,0,80,32), 'cloud':(96,0,128,32),
          'luigi':(144,0,176,32), 'mario':(192,0,224,32),
          'flower':(49,32,80,64), 'mushroom':(96,32,128,64),
          'goomba':(144,32,176,64), 'bowser':(192,32,224,64),
          'boo':(73,65,104,93), 'yoshi':(104,64,136,96)}
# Small bitmap numerals remain crisp at native DS resolution.
GLYPHS = {
    '0':('111','101','101','101','111'), '1':('010','110','010','010','111'),
    '2':('111','001','111','100','111'), '3':('111','001','111','001','111'),
    '4':('101','101','111','001','001'), '5':('111','100','111','001','111'),
    '6':('111','100','111','101','111'), '7':('111','001','010','010','010'),
    '8':('111','101','111','101','111'), '9':('111','101','111','001','111'),
    'A':('010','101','111','101','101'), 'J':('001','001','001','101','111'),
    'Q':('111','101','101','111','001'), 'K':('101','101','110','101','101'),
    'H':('101','101','111','101','101'), 'W':('101','101','101','111','101'),
    'R':('110','101','110','101','101'), 'O':('111','101','101','101','111'),
    'Y':('101','101','010','010','010'), 'G':('111','100','101','101','111'),
    'B':('110','101','110','101','110'), 'I':('111','010','010','010','111'),
    'V':('101','101','101','101','010'), '+':('000','010','111','010','000'),
    '-':('000','000','111','000','000'), '\u00b1':('010','111','010','000','111'),
}
SUITS = {
    'D':('00100','01110','11111','01110','00100'),
    'H':('11011','11111','11111','01110','00100'),
    'S':('00100','01110','11111','10101','00100'),
    'C':('00100','01110','10101','11111','00100'),
}


@lru_cache(maxsize=1)
def _sheet():
    with Image.open(ROOT / 'cards.gif') as source:
        art = source.convert('RGBA')
    # Magenta is the source sheet's background, not part of the game artwork.
    key = art.getpixel((255,127))[:3]
    pixels=art.get_flattened_data() if hasattr(art,'get_flattened_data') else art.getdata()
    art.putdata([(r,g,b,0 if (r,g,b)==key else a) for r,g,b,a in pixels])
    return art


def _stamp(image, pattern, xy, color, scale=1):
    draw=ImageDraw.Draw(image)
    for y,row in enumerate(pattern):
        for x,bit in enumerate(row):
            if bit=='1':
                left,top=xy[0]+x*scale,xy[1]+y*scale
                draw.rectangle((left,top,left+scale-1,top+scale-1),fill=color)


def _text(image, value, xy, color='#182d37', scale=1):
    for index,char in enumerate(str(value)):
        if char in GLYPHS:
            _stamp(image,GLYPHS[char],(xy[0]+index*4*scale,xy[1]),color,scale)


def _center(image, value, y, color='#182d37', scale=1):
    width=(len(str(value))*4-1)*scale
    _text(image,value,((32-width)//2,y),color,scale)


@lru_cache(maxsize=32)
def _motif(name):
    art=_sheet().crop(MOTIFS[name])
    bounds=art.getbbox()
    return art.crop(bounds) if bounds else art


def _portrait(image,name,box):
    art=_motif(name)
    x,y,w,h=box
    ratio=min(w/art.width,h/art.height)
    size=(max(1,round(art.width*ratio)),max(1,round(art.height*ratio)))
    art=art.resize(size,Image.Resampling.NEAREST)
    image.alpha_composite(art,(x+(w-art.width)//2,y+(h-art.height)//2))


def _frame():
    return _sheet().crop((143,64,176,112)).resize((32,48),Image.Resampling.NEAREST)


def _native(value,style):
    if value is None or style=='memory':
        from casinogames.card_scene import card
        return card(value or None,(32,48)).copy()
    art=_frame()
    draw=ImageDraw.Draw(art)
    if style=='triad':
        _portrait(art,value['id'],(5,12,22,24))
        _center(art,value['north'],4,scale=1)
        _center(art,value['south'],39,scale=1)
        _text(art,value['west'],(3,23));_text(art,value['east'],(26,23))
    elif style=='red7':
        code=str(value);color=COLORS[code[0]]
        draw.rectangle((3,3,28,44),fill=color)
        ink='#202d30' if code[0]=='Y' else '#ffffff'
        _text(art,code,(4,4),ink)
        _center(art,code[1],12,ink,scale=3)
        symbol=dict(zip('ROYGBIV',['mushroom','flower','star','yoshi','cloud','boo','bowser']))[code[0]]
        _portrait(art,symbol,(9,29,14,13))
        _text(art,code[0],(4,38),ink)
    elif style=='modifier':
        label=str(value)
        if isinstance(value,int) and value>0:label='+'+label
        negative=label.startswith('-');mixed=label.startswith('\u00b1')
        tint='#e5c3c0' if negative else '#c6c5ed' if mixed else '#c8ecf0'
        draw.rectangle((3,3,28,44),fill=tint)
        ink='#9b2133' if negative else '#49358d' if mixed else '#164c82'
        _text(art,label,(4,4),ink)
        scale=2 if len(label)>1 else 3
        _center(art,label,13,ink,scale)
        _portrait(art,'boo' if negative else 'star' if mixed else 'mushroom',(8,29,16,14))
    elif style=='tower':
        label='H' if value==0 else str(value)
        _center(art,label,5,scale=2)
        _portrait(art,'luigi' if value==0 else 'star',(5,20,22,22))
    else:
        code=str(value)
        if code.startswith('X'):
            _text(art,'W',(3,4));_portrait(art,'boo',(4,13,24,25));_text(art,'W',(26,39))
            return art
        rank,suit=code[:-1],code[-1]
        ink='#a51d2d' if suit in ('H','D') else '#182d37'
        _text(art,rank,(3,4),ink)
        _stamp(art,SUITS[suit],(23,4),ink)
        # Red and black royals intentionally contrast Mario and Bowser portraits.
        portrait={'K':'mario' if suit in ('H','D') else 'bowser',
                  'Q':'flower','J':'luigi','A':'star'}.get(rank,
                  {'D':'star','H':'mushroom','C':'flower','S':'goomba'}[suit])
        _portrait(art,portrait,(4,13,24,24))
        _stamp(art,SUITS[suit],(4,39),ink)
        _text(art,rank,(29-(len(rank)*4-1),39),ink)
    return art


def face(value,style,size):
    """Draw into a portrait slot; callers control legal card information/layout."""
    return _native(value,style).resize(tuple(map(round,size)),Image.Resampling.NEAREST)
