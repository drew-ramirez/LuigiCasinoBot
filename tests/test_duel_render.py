"""Duel projection privacy, screen geometry and real card transitions."""
from copy import deepcopy
from types import SimpleNamespace

from PIL import Image, ImageChops, ImageStat
import pytest

from casinogames.card_scene import dealer
from casinogames.duel_render import _layout, render_duel, render_sequence
from casinogames.triple_triad import TripleTriad
from casinogames.red7 import Red7
from casinogames.scopa import Scopa
from casinogames.cuttle import Cuttle
from casinogames.pazaak import Pazaak
from casinogames.platoon import Platoon
from casinogames.casino_war import CasinoWar

ENGINES = [TripleTriad,Red7,Scopa,Cuttle,Pazaak,Platoon,CasinoWar]


@pytest.mark.parametrize('engine',ENGINES)
def test_native_geometry_projection_immutability_and_uncovered_dealer(engine):
    game=engine(players=(11,0),seed=7)
    state=game.view(11); saved=deepcopy(state)
    with Image.open(render_duel(state['kind'],state)) as image:
        assert image.format=='PNG'
        assert image.size==(512,768)
        top=image.crop((0,0,512,384)).resize((256,192),Image.Resampling.NEAREST).convert('RGB')
        expected=dealer(SimpleNamespace(GAME_KEY='expansion')).convert('RGB')
        assert ImageChops.difference(top,expected).getbbox() is None
    assert state==saved
    for slot in _layout(state['kind'],state)[0].values():
        x,y,w,h=slot.rect
        assert 0<=x and 0<=y and x+w<=256 and y+h<=192


@pytest.mark.parametrize('engine',[Red7,Scopa,Cuttle,Pazaak,Platoon])
def test_changing_private_cards_without_changing_projection_has_no_pixel_effect(engine):
    game=engine(players=(11,0),seed=17)
    first=game.view()
    # Alter actual hidden hands, keeping only their lengths public.
    if engine is Pazaak:
        game.side_decks['11']=['-6']*10
    else:
        key='11'
        game.hands[key]=list(reversed(game.hands[key]))
    second=game.view()
    assert render_duel(first['kind'],first).getvalue()==render_duel(second['kind'],second).getvalue()
    # Future/deck/known history is not rendered or included in metadata.
    second.update(deck=['SECRET'],rng_state='SECRET',known_hands={'11':['SECRET']})
    assert render_duel(first['kind'],first).getvalue()==render_duel(second['kind'],second).getvalue()


def _move(game):
    player=game.turn
    action=next(a['id'] for a in game.legal_actions(player) if a['id']!='concede')
    game.act(player,action)


@pytest.mark.parametrize('engine',[TripleTriad,Red7,Scopa,Cuttle,Platoon])
def test_action_animation_changes_lower_screen_and_ends_on_static_frame(engine):
    game=engine(players=(11,0),seed=8)
    before=game.view(11)
    _move(game)
    after=game.view(11)
    with Image.open(render_duel(after['kind'],after,previous=before,animate=True)) as event:
        assert event.format=='GIF'
        assert event.n_frames>=8
        assert 'loop' not in event.info
        event.seek(0); first=event.convert('RGB').crop((0,384,512,768))
        event.seek(4); middle=event.convert('RGB').crop((0,384,512,768))
        assert ImageChops.difference(first,middle).getbbox() is not None
        event.seek(event.n_frames-1); final=event.convert('RGB')
    with Image.open(render_duel(after['kind'],after)) as still:
        assert max(ImageStat.Stat(ImageChops.difference(final,still.convert('RGB'))).mean)<6


def test_card_identity_moves_from_hand_to_table_and_removed_card_slides(monkeypatch):
    import casinogames.duel_render as renderer
    before={'kind':'scopa','players':[11,0],'hands':{'11':['3H','5S'],'0':[None]*3},
            'table':['2D'],'scores':{},'remaining_deck':30}
    after=deepcopy(before);after['hands']['11']=['5S'];after['table']=['2D','3H']
    seen=[];original=renderer._draw
    def capture(board,slot,squeeze=1):
        seen.append((slot.face,slot.rect,squeeze));original(board,slot,squeeze)
    monkeypatch.setattr(renderer,'_draw',capture)
    renderer.render_duel('scopa',after,previous=before,animate=True)
    endpoints={v.rect for state in [before,after] for v in _layout('scopa',state)[0].values()}
    assert any(face=='3H' and rect not in endpoints and squeeze==1 for face,rect,squeeze in seen)
    seen.clear()
    captured=deepcopy(after);captured['table']=[]
    renderer.render_duel('scopa',captured,previous=after,animate=True)
    assert any(face=='2D' and squeeze<1 for face,rect,squeeze in seen)


def test_ownership_flip_is_animated_without_changing_triad_card(monkeypatch):
    import casinogames.duel_render as renderer
    game=TripleTriad(players=(11,0),seed=2);_move(game)
    before=game.view();after=deepcopy(before)
    entry=next(e for e in after['table'] if e)
    entry['owner']=0 if entry['owner']==11 else 11
    seen=[];original=renderer._draw
    def capture(board,slot,squeeze=1):
        if slot.style=='triad': seen.append(squeeze)
        original(board,slot,squeeze)
    monkeypatch.setattr(renderer,'_draw',capture)
    renderer.render_duel('triple_triad',after,previous=before,animate=True)
    assert any(s<1 for s in seen)


def test_sequence_includes_multiple_accepted_steps_and_rejects_empty_input():
    game=Scopa(players=(11,0),seed=4)
    states=[game.view(11)]
    for _ in range(2):
        _move(game);states.append(game.view(11))
    with Image.open(render_sequence('scopa',states)) as image:
        assert image.n_frames>=17
    with pytest.raises(ValueError): render_sequence('scopa',[])
    with pytest.raises(ValueError): render_duel('not_a_game',{})


def test_full_public_board_and_formation_cards_stay_in_bounds():
    game=Platoon(players=(11,0),seed=2)
    state=game.view(11)
    assert len([k for k in _layout('platoon',state)[0] if k.startswith('hand:')])==10
    state=Scopa(players=(11,0),seed=3).view(11)
    state['table']=[f'{rank}{suit}' for rank in ['A','2','3','4','5','6','7','J','Q','K'] for suit in 'CDHS']
    for slot in _layout('scopa',state)[0].values():
        x,y,w,h=slot.rect
        assert 0<=x and x+w<=256 and 0<=y and y+h<=192


def test_full_formation_does_not_overlap_its_neighbors():
    state=Platoon(players=(11,0),seed=2).view(11)
    state['formations']['11'][0]['cards']=state['hands']['11']
    state['formations']['11'][0]['count']=10
    slots=_layout('platoon',state)[0]
    piles=[s for k,s in slots.items() if k.startswith('pile:11:0:')]
    assert len(piles)==10
    for slot in piles:
        x,y,w,h=slot.rect
        assert 7<=x and x+w<=51 and y+h<=76


def test_viewer_id_preserves_an_empty_private_hand():
    state=Scopa(players=(11,0),seed=2).view(0)
    state['hands']['0']=[]
    state['viewer_id']=0
    assert not any(k.startswith('hand:') for k in _layout('scopa',state)[0])


def test_sixteen_accepted_steps_fit_upload_limit_and_retain_final_state():
    game=Platoon(players=(11,0),seed=8)
    states=[game.view(11)]
    for _ in range(15):
        game.act(game.turn,game.bot_action());states.append(game.view(11))
    result=render_sequence('platoon',states)
    assert len(result.getvalue())<8_000_000
    with Image.open(result) as animation:
        assert animation.n_frames>=len(states)
        animation.seek(animation.n_frames-1);final=animation.convert('RGB')
    with Image.open(render_duel('platoon',states[-1])) as still:
        assert max(ImageStat.Stat(ImageChops.difference(final,still.convert('RGB'))).mean)<6


@pytest.mark.parametrize('engine',ENGINES)
def test_all_cards_keep_tall_portrait_proportions(engine):
    game=engine(players=(11,0),seed=8)
    for _ in range(50):
        state=game.view(11)
        for slot in _layout(state['kind'],state)[0].values():
            x,y,w,h=slot.rect
            assert .63<=w/h<=.70
            assert 0<=x and x+w<=256 and 0<=y and y+h<=192
        if game.finished: break
        game.act(game.turn,game.bot_action())


def test_crowded_piles_overlap_without_distorting_their_art():
    state=Cuttle(players=(11,0),seed=8).view(11)
    cards=[rank+suit for suit in 'CDHS' for rank in ['A','2','3','4','5','6','7','8','9','10','J','Q','K']]
    state['hands']['11']=cards
    state['points']=[{'card':c,'owner':11,'jacks':[]} for c in cards[:20]]
    state['permanents']=[{'card':c,'owner':11} for c in cards[20:32]]
    for slot in _layout('cuttle',state)[0].values():
        x,y,w,h=slot.rect
        assert .63<=w/h<=.70
        assert 0<=x and x+w<=256 and 0<=y and y+h<=192


def test_platoon_hand_omits_cards_already_assigned_to_a_formation():
    game=Platoon(players=(11,0),seed=8)
    game.act(11,'assign:0:0')
    slots=_layout('platoon',game.view(11))[0]
    assert 'hand:0' not in slots
    assert 'pile:11:0:0' in slots
    assert len([key for key in slots if key.startswith('hand:')])==9
