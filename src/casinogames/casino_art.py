"""Pixel art extracted from the user-supplied SM64 DS casino sheet."""
from functools import lru_cache
from pathlib import Path
from PIL import Image, ImageOps

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
