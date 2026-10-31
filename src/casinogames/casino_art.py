"""Pixel art extracted from the user-supplied SM64 DS casino sheet."""
from functools import lru_cache
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1] / 'assets' / 'casino'

@lru_cache(maxsize=64)
def sprite(name):
    with Image.open(ROOT / f'{name}.png') as source:
        return source.convert('RGBA')

def background(size):
    return sprite('felt').resize(size, Image.Resampling.NEAREST)

def paste(canvas, name, xy, scale=2):
    art = sprite(name)
    art = art.resize((art.width * scale, art.height * scale), Image.Resampling.NEAREST)
    canvas.alpha_composite(art, xy)

def badge(canvas, name, y, scale=2):
    art = sprite(name)
    paste(canvas, name, ((canvas.width - art.width * scale) // 2, y), scale)
