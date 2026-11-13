"""A public-data-only casino profile card with optional frame and sparkles."""
from collections.abc import Mapping
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

from casinogames.casino_art import background, sprite
from casinogames.card_scene import card
from cosmetics.catalog import Appearance
from cosmetics.rendering import run_with_appearance

NATIVE = (256, 160)
SIZE = (512, 320)
NAME = ImageFont.load_default(size=14)
LABEL = ImageFont.load_default(size=9)
VALUE = ImageFont.load_default(size=12)


def _text(draw, xy, value, width, font, fill='#fff4ce'):
    value = str(value)
    while value and draw.textlength(value, font=font) > width:
        value = value[:-1]
    draw.text(xy, value, font=font, fill=fill, stroke_width=1, stroke_fill='#253428')


def _count(value):
    try:
        return max(0, int(value))
    except (TypeError, ValueError, OverflowError):
        return 0


def _base(public, appearance):
    image = background(NATIVE)
    draw = ImageDraw.Draw(image)
    name = public.get('name', 'Player')
    name = ' '.join(name.split()) if isinstance(name, str) else 'Player'
    _text(draw, (17, 18), name or 'Player', 182, NAME)
    _text(draw, (18, 39), 'CASINO PROFILE', 174, LABEL)
    image.alpha_composite(card('luigi', (24, 36)), (214, 17))
    stats = [('balance', 'COINS', 'coin'), ('games_played', 'GAMES PLAYED', None),
             ('career_stars', 'CAREER STARS', 'slot_star')]
    for index, (key, label, icon) in enumerate(stats):
        y = 67 + index * 26
        if icon:
            image.alpha_composite(sprite(icon).resize((14, 14), Image.Resampling.NEAREST), (18, y-1))
        else:
            image.alpha_composite(card('mushroom', (10, 15)), (20, y-1))
        _text(draw, (41, y+1), label, 95, LABEL)
        count = _count(public.get(key, 0))
        value = f'{count:,}'
        font = VALUE if draw.textlength(value, font=VALUE) <= 100 else LABEL
        if draw.textlength(value, font=font) > 100:
            digits = str(count)
            value = f'~{digits[0]}.{digits[1:4]}e{len(digits)-1}'
        _text(draw, (139, y), value, 102, font)
    if appearance.profile_frame == 'silver':
        draw.rectangle((4, 4, 251, 155), outline='#d9e1eb', width=2)
        draw.rectangle((7, 7, 248, 152), outline='#78899c', width=1)
        draw.line((5, 154, 5, 5, 250, 5), fill='#f5f8ff', width=1)
        draw.line((250, 6, 250, 154, 6, 154), fill='#9baab9', width=1)
    return image


def _sparkles(image, tick):
    draw = ImageDraw.Draw(image)
    # Deterministic twinkles sit along the frame, clear of the public statistics.
    positions = ((28, 10), (115, 9), (230, 10), (245, 76), (211, 150), (80, 150), (10, 104))
    radii = (0, 1, 2, 3, 2, 1)
    for index, (x, y) in enumerate(positions):
        radius = radii[(tick+index*2) % len(radii)]
        if radius:
            draw.line((x-radius, y, x+radius, y), fill='#c9e8ff')
            draw.line((x, y-radius, x, y+radius), fill='#c9e8ff')
            draw.point((x, y), fill='#ffffff')
            if radius == 3:
                draw.point((x-1, y-1), fill='#e6f4ff')
                draw.point((x+1, y+1), fill='#e6f4ff')


def _render(public, appearance, animate):
    base = _base(public, appearance)
    sparkle = appearance.profile_effect == 'sparkle'
    frames = []
    for tick in range(12 if animate and sparkle else 1):
        frame = base.copy()
        if sparkle:
            _sparkles(frame, tick)
        frames.append(frame.resize(SIZE, Image.Resampling.NEAREST))
    output = BytesIO()
    if len(frames) == 1:
        frames[0].save(output, 'PNG')
    else:
        # One stable palette covers every particle color without touching the
        # shared game GIF encoder or embedding source profile dictionaries.
        atlas = Image.new('RGB', (SIZE[0]*3, SIZE[1]))
        for index, frame in enumerate((frames[0], frames[2], frames[4])):
            atlas.paste(frame.convert('RGB'), (index*SIZE[0], 0))
        palette = atlas.quantize(colors=256)
        encoded = [frame.convert('RGB').quantize(palette=palette, dither=Image.Dither.NONE) for frame in frames]
        encoded[0].save(output, 'GIF', save_all=True, append_images=encoded[1:],
                        duration=110, loop=0, disposal=2)
    output.seek(0)
    return output


def render_profile(public, appearance: Appearance, animate=False):
    """Render only name, balance, games_played, and career_stars.

    The caller supplies resolved ownership and the animation preference. Extra
    account fields are ignored; this module never imports persistence services.
    Disabling animation always produces a static PNG, including equipped effects.
    """
    if not isinstance(public, Mapping):
        raise TypeError('A profile requires a public mapping')
    return run_with_appearance(appearance, _render, public, appearance, bool(animate))
