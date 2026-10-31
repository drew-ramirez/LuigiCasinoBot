"""Raised roulette dividers, orthographic camera and shared ball depth buffer."""
import math
from PIL import Image, ImageDraw, ImageFilter

SCALE=2


def project(vertex):
    x,y,z=vertex
    return (128+1.56*x,102+.93*y-1.25*z,1.25*y+.93*z)


def divider_mesh(rotation):
    """Twelve tapered triangular ridges on the existing pocket boundaries."""
    faces=[]
    for i in range(12):
        angle=math.radians(-120+i*30-rotation)
        def vertex(radius,side,height):
            return (radius*math.cos(angle)-side*math.sin(angle),
                    radius*math.sin(angle)+side*math.cos(angle),height)
        # Bury the inner end beneath the gold silhouette at every rotation.
        # The previous radius left exposed end caps and a strip of green felt.
        left=vertex(8,-9,2)
        right=vertex(8,9,2)
        tip=vertex(58,0,0)
        ridge=vertex(10,0,10)
        faces.extend(((left,tip,ridge),(tip,right,ridge),(right,left,ridge)))
    return faces


def face_color(vertices):
    a,b,c=vertices
    u=[b[i]-a[i] for i in range(3)];v=[c[i]-a[i] for i in range(3)]
    normal=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
    length=math.sqrt(sum(n*n for n in normal))
    # Fixed light in room coordinates; rotating sides change brightness.
    light=(-.45,-.35,.82)
    diffuse=max(0,sum(n*l for n,l in zip(normal,light))/length)
    brightness=.72+.24*diffuse
    return tuple(round(c*brightness) for c in (191,190,157))+(255,)


def render_dividers(top,rotation,ball_angle=None,ball_radius=112):
    """Rasterize ridge faces and ball together so nearer surfaces occlude farther ones."""
    canvas=top.resize((256*SCALE,192*SCALE),Image.Resampling.NEAREST)
    shadow_layer=Image.new('RGBA',canvas.size)
    draw=ImageDraw.Draw(shadow_layer)
    mesh=divider_mesh(rotation)
    # Cast the elevated ridges' shadows onto the felt, away from the light.
    for face in mesh:
        shadow=[]
        for x,y,z in face:
            sx,sy,_=project((x+z*.48,y+z*.35,0))
            shadow.append((sx*SCALE,sy*SCALE))
        draw.polygon(shadow,fill=(8,16,5,65))
    canvas.alpha_composite(shadow_layer.filter(ImageFilter.GaussianBlur(1.6)))
    width,height=canvas.size
    depth=[-math.inf]*(width*height)
    pixels=canvas.load()
    for face in mesh:
        projected=[project(v) for v in face]
        (ax,ay,az),(bx,by,bz),(cx,cy,cz)=projected
        ax*=SCALE;ay*=SCALE;bx*=SCALE;by*=SCALE;cx*=SCALE;cy*=SCALE
        denominator=(by-cy)*(ax-cx)+(cx-bx)*(ay-cy)
        if abs(denominator)<1e-8:continue
        color=face_color(face)
        for y in range(max(0,math.floor(min(ay,by,cy))),min(height,math.ceil(max(ay,by,cy))+1)):
            for x in range(max(0,math.floor(min(ax,bx,cx))),min(width,math.ceil(max(ax,bx,cx))+1)):
                u=((by-cy)*(x+.5-cx)+(cx-bx)*(y+.5-cy))/denominator
                v=((cy-ay)*(x+.5-cx)+(ax-cx)*(y+.5-cy))/denominator
                w=1-u-v
                if min(u,v,w)<0:continue
                z=u*az+v*bz+w*cz
                index=y*width+x
                if z>depth[index]:
                    depth[index]=z;pixels[x,y]=color
    if ball_angle is not None:
        wx=ball_radius*math.cos(ball_angle);wy=ball_radius*math.sin(ball_angle)
        x,y,z=project((wx,wy,6/1.56))
        # Sphere surface shares the same camera depth coordinates as the mesh.
        for py in range(max(0,math.floor((y-6)*SCALE)),min(height,math.ceil((y+6)*SCALE))):
            for px in range(max(0,math.floor((x-6)*SCALE)),min(width,math.ceil((x+6)*SCALE))):
                dx=(px+.5)/SCALE-x;dy=(py+.5)/SCALE-y
                q=36-dx*dx-dy*dy
                if q<0:continue
                front=math.sqrt(q)
                index=py*width+px
                if z+front>depth[index]:
                    light=max(0,(-dx*.35-dy*.5+front*.79)/6)
                    pixels[px,py]=(round(203+52*light),round(201+52*light),round(151+79*light),255)
    return canvas.resize((256,192),Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(.45))
