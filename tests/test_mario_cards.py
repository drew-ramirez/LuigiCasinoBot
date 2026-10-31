"""Mario sprite-frame identity and rule-bearing card labels at native size."""
from copy import deepcopy
from pathlib import Path

from PIL import Image
import pytest

from casinogames.mario_cards import face
from casinogames.triple_triad import CARDS

ART = Path(__file__).resolve().parents[1] / 'src' / 'assets' / 'cardart'
NATIVE = (32, 48)
STANDARD = [rank + suit for rank in ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K'] for suit in 'CDHS']
MEMORY = ['star', 'cloud', 'luigi', 'mario', 'flower', 'mushroom', 'goomba', 'bowser', 'boo', 'yoshi']
SAMPLES = [('AS', 'standard'), ('10H', 'compact'), ('X1', 'standard'),
           ('Y7', 'red7'), ('-6', 'modifier'), ('±3', 'modifier'),
           (0, 'tower'), (7, 'tower'), (CARDS[0], 'triad')]


def samples():
    yield from SAMPLES
    yield from ((card, 'standard') for card in STANDARD)
    yield from ((color + str(rank), 'red7') for color in 'ROYGBIV' for rank in range(1, 8))
    yield from ((sign + str(rank), 'modifier') for sign in ['+', '-', '±'] for rank in range(1, 7))
    yield from ((rank, 'modifier') for rank in range(1, 11))
    yield from ((card, 'triad') for card in CARDS)
    yield from ((name, 'memory') for name in MEMORY)
    yield from ((None, style) for style in ['standard', 'compact', 'triad', 'red7', 'modifier', 'tower', 'memory'])


def test_expansion_perimeters_are_the_existing_sprite_frame_not_generic_rectangles():
    with Image.open(ART / 'cards.gif') as source:
        sheet = source.convert('RGBA')
    key = sheet.getpixel((255, 127))[:3]
    expected = sheet.crop((143, 64, 176, 112)).resize(NATIVE, Image.Resampling.NEAREST)
    # Compare the untouched three-pixel frame, independently of new face content.
    border = [(x, y) for y in range(48) for x in range(32)
              if x < 3 or x >= 29 or y < 3 or y >= 45]
    opaque_colors = {expected.getpixel(p) for p in border if expected.getpixel(p)[:3] != key}
    assert len(opaque_colors) >= 4
    for value, style in SAMPLES:
        actual = face(value, style, NATIVE)
        for point in border:
            pixel = expected.getpixel(point)
            target = (*pixel[:3], 0) if pixel[:3] == key else pixel
            assert actual.getpixel(point) == target, (value, style, point)


def test_all_game_assets_load_at_native_portrait_size_without_opaque_sheet_key():
    with Image.open(ART / 'cards.gif') as sheet:
        key = sheet.convert('RGB').getpixel((255, 127))
    for value, style in samples():
        image = face(value, style, NATIVE)
        assert image.mode == 'RGBA' and image.size == NATIVE
        assert image.getbbox() is not None
        assert not any(pixel[:3] == key and pixel[3] for pixel in image.get_flattened_data()), (value, style)


@pytest.mark.parametrize('value,style', SAMPLES)
def test_scaling_preserves_crisp_native_portrait_art(value, style):
    native = face(value, style, NATIVE)
    enlarged = face(value, style, (64, 96))
    assert enlarged.tobytes() == native.resize((64, 96), Image.Resampling.NEAREST).tobytes()
    assert enlarged.width / enlarged.height == 2 / 3


def test_all_real_ranks_and_suits_have_distinct_corner_labels():
    # Decoration alone must never be the only way to tell two real cards apart.
    labels = [face(card, 'standard', NATIVE).crop((2, 3, 29, 10)).tobytes() for card in STANDARD]
    assert len(set(labels)) == 52
    wizard = face('X1', 'standard', NATIVE).crop((2, 3, 29, 10)).tobytes()
    assert wizard not in labels
    assert face('X1', 'standard', NATIVE).tobytes() == face('X2', 'standard', NATIVE).tobytes()


def test_red7_codes_and_modifier_signs_remain_distinguishable():
    red7 = [face(color + str(rank), 'red7', NATIVE).crop((3, 3, 13, 10)).tobytes()
            for color in 'ROYGBIV' for rank in range(1, 8)]
    assert len(set(red7)) == 49
    modifiers = [face(sign + str(rank), 'modifier', NATIVE).crop((3, 3, 17, 10)).tobytes()
                 for sign in ['+', '-', '±'] for rank in range(1, 7)]
    assert len(set(modifiers)) == 18
    assert face(10, 'modifier', NATIVE).tobytes() != face(1, 'modifier', NATIVE).tobytes()
    assert face(3, 'modifier', NATIVE).tobytes() == face('+3', 'modifier', NATIVE).tobytes()
    tower = [face(value, 'tower', NATIVE).crop((3, 3, 29, 17)).tobytes() for value in range(8)]
    assert len(set(tower)) == 8  # Hero is distinct from each numeric value.


def test_triad_edge_numbers_are_authoritative_and_inputs_are_untouched():
    original = deepcopy(CARDS[0])
    base = face(original, 'triad', NATIVE)
    for edge in ['north', 'east', 'south', 'west']:
        changed = deepcopy(original)
        changed[edge] = 1 if changed[edge] != 1 else 2
        assert face(changed, 'triad', NATIVE).tobytes() != base.tobytes()
    assert original == CARDS[0]
    with_metadata = {**original, 'secret_hand': ['AS', 'KH'], 'name': 'PRIVATE_SECRET', 'deck': [999]}
    assert face(with_metadata, 'triad', NATIVE).tobytes() == base.tobytes()


def test_hidden_cards_use_one_neutral_back_and_returned_images_are_detached():
    from casinogames.card_scene import card
    expected = card(None, NATIVE).tobytes()
    for style in ['standard', 'compact', 'triad', 'red7', 'modifier', 'tower', 'memory']:
        first = face(None, style, NATIVE)
        assert first.tobytes() == expected
        first.paste('#ff00ff', (0, 0, 32, 48))
        assert face(None, style, NATIVE).tobytes() == expected
    # Rendering a secret value previously cannot alter later covered cards.
    face('KH', 'standard', NATIVE)
    face('±6', 'modifier', NATIVE)
    assert face(None, 'standard', NATIVE).tobytes() == expected
    first = face('AS', 'standard', NATIVE)
    before = first.tobytes()
    first.paste('#ff00ff', (0, 0, 32, 48))
    assert face('AS', 'standard', NATIVE).tobytes() == before
