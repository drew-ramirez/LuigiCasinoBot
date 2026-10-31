import math
from PIL import Image, ImageChops
import pytest
from casinogames import roulette_dividers_3d as geometry


def test_raised_dividers_rotate_on_pocket_boundaries():
    for rotation in (0,17,90,359):
        faces=geometry.divider_mesh(rotation)
        assert len(faces)==36
        for i in range(12):
            left,tip,ridge=faces[i*3]
            expected=math.radians(-120+i*30-rotation)
            assert tip[:2]==pytest.approx((58*math.cos(expected),58*math.sin(expected)))
            assert ridge[2]>0
            ground=geometry.project((ridge[0],ridge[1],0))
            raised=geometry.project(ridge)
            assert raised[1]<ground[1]  # Height rises out of the wheel plane.


def test_divider_occludes_part_of_ball_in_shared_depth_buffer(monkeypatch):
    base=Image.new('RGBA',(256,192),'#073b18')
    with_ridge=geometry.render_dividers(base,0,0,40)
    ridge_only=geometry.render_dividers(base,0)
    visible_with_ridge=sum(any(p[:3]) for p in ImageChops.difference(with_ridge,ridge_only).getdata())
    monkeypatch.setattr(geometry,'divider_mesh',lambda rotation:[])
    ball_only=geometry.render_dividers(base,0,0,40)
    empty=geometry.render_dividers(base,0)
    visible_without_ridge=sum(any(p[:3]) for p in ImageChops.difference(ball_only,empty).getdata())
    assert 0<visible_with_ridge<visible_without_ridge


def test_divider_inner_ends_are_buried_under_pedestal():
    from casinogames.casino_art import sprite
    mask=sprite('roulette_spindle').getchannel('A')
    for rotation in range(0,360,5):
        for i,face in enumerate(geometry.divider_mesh(rotation)):
            for vertex in face:
                if math.hypot(vertex[0],vertex[1])<20:
                    x,y,_=geometry.project(vertex)
                    assert mask.getpixel((round(x),round(y)))>128
