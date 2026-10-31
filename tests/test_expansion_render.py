"""Safe projections, readable layouts, and transition/terminal parity."""
from copy import deepcopy
import io

from PIL import Image, ImageChops, ImageStat
import pytest

from casinogames.blackjack import Blackjack
from casinogames.expansion_render import render_table, _slots
from casinogames.fortune_tower import FortuneTower
from casinogames.thrilling_cards import ThrillingCards


def grid(cols, rows):
    faces=['star','mushroom','flower','cloud','luigi','mario']
    return {'cards': [faces[i%6] if i%3 else None for i in range(cols*rows)],
            'cols':cols,'rows':rows,'selected':[1],'score':27,'stars':3,
            'mistakes':2,'status':'playing','last':'Choose two matching cards'}


def samples():
    return [('memory_master',grid(4,4)),('memory_master',grid(6,3)),
            ('memory_master',grid(5,4)),('pairagone_endless',grid(5,4)),
            ('blackjack',Blackjack(20,shoe=['8S','6H','8D','9C','3H','4C','2H']).public_state()),
            ('fortune_tower',FortuneTower().public_state()),
            ('thrilling_cards',ThrillingCards([11,22,33,44]).view(11))]


@pytest.mark.parametrize('kind,state', samples())
def test_tables_have_native_screen_scale_and_never_mutate_inputs(kind,state):
    before=deepcopy(state)
    with Image.open(render_table(kind,state)) as image:
        assert image.format=='PNG'
        assert image.size==(512,768)
    assert state==before
    for slot in _slots(kind,state).values():
        x,y,w,h=slot.rect
        assert x>=0 and y>=0 and x+w<=256 and y+h<=192


def test_blackjack_hidden_hole_and_future_shoe_have_no_pixel_effect():
    first=Blackjack(20,shoe=['8S','6H','4D','9C','3H','4C','2H'])
    second=Blackjack(20,shoe=['8S','6H','4D','7C','AH','KC','2D'])
    a=render_table('blackjack',first.public_state()).getvalue()
    b=render_table('blackjack',second.public_state()).getvalue()
    assert a==b


def test_tower_hidden_gate_and_deck_have_no_pixel_effect():
    first=FortuneTower(deck=[1,3,4]+[2]*33)
    second=FortuneTower(deck=[7,3,4]+[6]*33)
    assert render_table('fortune_tower',first.public_state()).getvalue()==render_table('fortune_tower',second.public_state()).getvalue()


def test_thrilling_spectators_cannot_infer_any_dealt_card_from_images():
    first=ThrillingCards([11,22],cards=['AS','2H'])
    second=ThrillingCards([11,22],cards=['4D','KC'])
    assert render_table('thrilling_cards',first.view()).getvalue()==render_table('thrilling_cards',second.view()).getvalue()


def test_flip_changes_board_pixels_and_ends_on_matching_static_state():
    before=grid(4,4); before['cards']=[None]*16
    after=deepcopy(before); after['cards'][0]='star'
    with Image.open(render_table('memory_master',after,previous=before,animate=True)) as event:
        assert event.format=='GIF'
        assert event.n_frames>=9
        assert 'loop' not in event.info
        event.seek(0); first=event.convert('RGB').crop((0,384,512,768))
        event.seek(4); middle=event.convert('RGB').crop((0,384,512,768))
        assert ImageChops.difference(first,middle).getbbox() is not None
        event.seek(event.n_frames-1); final=event.convert('RGB')
    with Image.open(render_table('memory_master',after)) as still:
        error=ImageStat.Stat(ImageChops.difference(final,still.convert('RGB')))
        assert max(error.mean)<6


def test_spectator_transition_stays_identical_when_only_private_cards_differ():
    first=ThrillingCards([11,22],cards=['AS','2H'])
    second=ThrillingCards([11,22],cards=['4D','KC'])
    a=render_table('thrilling_cards',first.view(),animate=True).getvalue()
    b=render_table('thrilling_cards',second.view(),animate=True).getvalue()
    assert a==b


def test_unrecognized_fields_are_not_embedded_as_metadata():
    state=grid(4,4)
    image=render_table('memory_master',state).getvalue()
    state['secret']='do-not-put-private-deck-in-image'
    assert render_table('memory_master',state).getvalue()==image


def test_pair_compaction_slides_survivors_without_turning_their_faces(monkeypatch):
    import casinogames.expansion_render as renderer
    before=grid(5,4)
    before['cards']=['star','star']+['mushroom']*18
    before['score']=0
    after=deepcopy(before)
    after.update(cards=['mushroom']*18+['flower','cloud'],score=2,removed=[0,1])
    seen=[]
    draw=renderer._draw_slot
    def capture(board,slot,**kwargs):
        seen.append((slot.face,slot.rect,kwargs.get('squeeze',1)))
        draw(board,slot,**kwargs)
    monkeypatch.setattr(renderer,'_draw_slot',capture)
    renderer.render_table('pairagone_endless',after,previous=before,animate=True)
    mushroom=[(rect,squeeze) for face,rect,squeeze in seen if face=='mushroom']
    assert mushroom and all(squeeze==1 for _,squeeze in mushroom)
    endpoints={s.rect for s in renderer._slots('pairagone_endless',before).values()}
    assert any(rect not in endpoints for rect,_ in mushroom)


def test_full_eight_row_tower_stacks_portrait_cards_with_readable_indices():
    rows=[[(width%2)+1]*width for width in range(2,9)]
    game=FortuneTower(deck=[7]+[c for row in rows for c in row])
    for _ in range(6):
        game.deal_next()
    state=game.public_state()
    slots=_slots('fortune_tower',state)
    assert len(slots)==36
    for slot in slots.values():
        x,y,w,h=slot.rect
        assert 0<=x and x+w<=256 and 0<=y and y+h<=180
        # The 22px header text belongs in the corners beside the Gate.
        assert y>=34 or x>=110 and x+w<=145
    # Upper rows overlap as real cards; their top rank remains exposed.
    for slot in slots.values():
        assert abs(slot.rect[2]/slot.rect[3] - 2/3)<.03
    for row in range(6):
        next_y=min(s.rect[1] for k,s in slots.items() if k.startswith(f'r{row+1}'))
        assert all(s.rect[1]+13<=next_y for k,s in slots.items() if k.startswith(f'r{row}'))
    with Image.open(render_table('fortune_tower',state)) as still:
        assert still.size==(512,768)
