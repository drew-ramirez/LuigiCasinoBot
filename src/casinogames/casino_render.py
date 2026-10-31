"""Small, nearest-neighbor DS boards and interaction-driven GIFs."""
import io
from PIL import Image, ImageDraw, ImageFont
from casinogames.casino_art import background, paste, badge, sprite
from casinogames.casino_games import Roulette, Slots

FONT = ImageFont.load_default(size=16)

def frame(game, tick=0, *, spinning=False):
    if isinstance(game, Roulette):
        from casinogames.roulette_render import frame as roulette_frame
        return roulette_frame(game, tick, spinning=spinning)
    board = background((768, 900))
    draw = ImageDraw.Draw(board)
    if isinstance(game, Slots):
        paste(board, 'slot_top', (128, 66), 2)
        paste(board, 'slot_bottom', (128, 450), 2)
        # Cabinet's original reel openings, doubled from the source sheet.
        for i, value in enumerate(game.reels):
            x, y = 156 + i * 150, 636
            reel = Image.new('RGBA', (132, 126), '#f2f2f2')
            if value is not None:
                art = sprite('slot_' + value)
                art = art.resize((art.width * 2, art.height * 2), Image.Resampling.NEAREST)
                reel.alpha_composite(art, ((132-art.width)//2, (126-art.height)//2))
            else:
                offset = (tick * 24) % 100
                for j in range(-1, 3):
                    name = Slots.SYMBOLS[(tick // 4 + i + j) % 6]
                    art = sprite('slot_' + name)
                    art = art.resize((art.width*2, art.height*2), Image.Resampling.NEAREST)
                    reel.alpha_composite(art, ((132-art.width)//2, j*100-offset))
            board.alpha_composite(reel, (x, y-12))
        # Result badge overlays the cabinet's empty message panel.
        if game.result is not None:
            badge(board, 'you_win' if game.result['payout'] else 'too_bad', 535, 1)
    return board.crop((128,66,638,832)).resize((512,768),Image.Resampling.NEAREST)

def render(game, animated=False):
    if isinstance(game, Roulette):
        from casinogames.roulette_render import render as roulette_render
        return roulette_render(game, animated)
    out = io.BytesIO()
    if not animated:
        frame(game).save(out, 'PNG')
    else:
        frames = [frame(game, t) for t in range(12)] if game.result is None else [frame(game)]
        durations = [80]*len(frames)
        options = {'loop': 0} if game.result is None else {}
        frames[0].save(out, 'GIF', save_all=True, append_images=frames[1:],
                       duration=durations, disposal=2, **options)
    out.seek(0)
    return out
