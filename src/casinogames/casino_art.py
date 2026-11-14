"""Pixel art extracted from the user-supplied SM64 DS casino sheet."""
from functools import lru_cache
from pathlib import Path
from PIL import Image, ImageOps, ImageFont

from cosmetics.rendering import current_appearance

ROOT = Path(__file__).resolve().parents[1] / 'assets' / 'casino'

@lru_cache(maxsize=64)
def sprite(name):
    with Image.open(ROOT / f'{name}.png') as source:
        return source.convert('RGBA')

@lru_cache(maxsize=2)
def _felt_variant(theme):
    # Colorize a fresh luminance image; the cached source pixels stay untouched.
    source = sprite('felt')
    shades = {'midnight': ('#040d1d', '#3f76a3'), 'rose': ('#26081c', '#a64d75')}
    dark, light = shades[theme]
    art = ImageOps.colorize(ImageOps.grayscale(source), dark, light).convert('RGBA')
    art.putalpha(source.getchannel('A'))
    return art


def background(size):
    theme = current_appearance().felt
    # Keep the original path byte-for-byte for unset/default/unknown cosmetics.
    source = _felt_variant(theme) if theme in ('midnight', 'rose') else sprite('felt')
    return source.resize(size, Image.Resampling.NEAREST)

def paste(canvas, name, xy, scale=2):
    art = sprite(name)
    art = art.resize((art.width * scale, art.height * scale), Image.Resampling.NEAREST)
    canvas.alpha_composite(art, xy)

def badge(canvas, name, y, scale=2):
    art = sprite(name)
    paste(canvas, name, ((canvas.width - art.width * scale) // 2, y), scale)


SIZE = (512, 768)


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


def text(draw, xy, value, font=FONT):
    draw.text(xy, str(value), font=font, fill='#fff19b', stroke_width=1, stroke_fill='#454018')


def compose(top, bottom):
    board=Image.new('RGBA',(256,384),'#004b10')
    board.alpha_composite(top,(0,0))
    board.alpha_composite(bottom,(0,192))
    return board.resize(SIZE,Image.Resampling.NEAREST)


def dealer_frame(index):
    atlas = sprite('dealer_motion')
    index = min(49, max(0, index))
    x, y = index % 10 * 256, index // 10 * 192
    return atlas.crop((x, y, x + 256, y + 192))


TINY = ImageFont.load_default(size=8)


GOLD = "#f8d76c"


def fit_text(draw, xy, value, width=244, font=SMALL, fill=GOLD):
    label = str(value).translate({8212: "-", 8211: "-", 8217: chr(39), 215: "x", 8594: "->"})
    while label and draw.textlength(label, font=font) > width:
        label = label[:-1]
    draw.text(xy, label, font=font, fill=fill, stroke_width=1, stroke_fill="#26371b")
