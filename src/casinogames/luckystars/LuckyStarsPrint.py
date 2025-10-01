###########################################################
# File: LuckyStarsPrint.py
#
# Description: Rendering & animations for Lucky Stars
###########################################################

from PIL import Image
import io, os
from casinogames.assetloader import load_memory_backs, ASSETS_DIR_CARDART
from casinogames.luckystars.LuckyStars import LuckyStars
from casinogames.assetloader import load_memory_backs, load_lucky_assets

backs = load_memory_backs()
assets = load_lucky_assets()  

# Load the Lucky Stars asset sheet
ASSET_PATH = os.path.join(ASSETS_DIR_CARDART, "cards.gif")
SHEET = Image.open(ASSET_PATH).convert("RGBA")

# Crops (based on your provided coords for 256x128)
CARD_BLANK = SHEET.crop((143, 63, 175, 95))   # full blank card
CARD_HALF  = SHEET.crop((175, 63, 191, 95))   # half blank (for flip, optional)
STAR_ICON  = SHEET.crop((32, 0, 48, 16))      # small star

def make_card_with_stars(star_count: int, game) -> Image.Image:
    
    #DS-like layout & scaling:
    #  1: big center
    #  2: vertical column
    #  3: triangle (1 top, 2 bottom)
    #  4: 2x2 grid
    #  5: 2-1-2 (X / pentagon)
    
    card = assets["blank_full"].copy()
    base_star = assets["star"]

    W, H = card.size

    # Size per count (tuned to DS look; tweak if you like)
    size_map = {
        1: int(H * 0.55),
        2: int(H * 0.42),
        3: int(H * 0.30),
        4: int(H * 0.30),
        5: int(H * 0.28),
    }
    S = size_map.get(star_count, int(H * 0.32))  # default fallback
    star_icon = base_star.resize((S, S), Image.NEAREST)

    # Gaps scale with size so it looks balanced at any S
    gap_x = max(2, S // 6)
    gap_y = max(2, S // 6)

    def paste_row(n: int, y: int):
        #Paste a row of n stars centered horizontally at y.
        if n <= 0:
            return
        row_w = n * S + (n - 1) * gap_x
        start_x = (W - row_w) // 2
        for i in range(n):
            x = start_x + i * (S + gap_x)
            card.paste(star_icon, (x, y), mask=star_icon)

    if star_count == 1:
        paste_row(1, (H - S) // 2)

    elif star_count == 2:
        total_h = 2 * S + gap_y
        start_y = (H - total_h) // 2
        paste_row(1, start_y)                     # upper star
        paste_row(1, start_y + S + gap_y)         # lower star

    elif star_count == 3:
        gap_y = 6
        total_h = 2 * S + gap_y
        start_y = (H - total_h) // 2
        paste_row(1, start_y)                  # top
        paste_row(2, start_y + S + gap_y)      # bottom row

    elif star_count == 4:
        total_h = 2 * S + gap_y
        start_y = (H - total_h) // 2
        paste_row(2, start_y)                     # top 2
        paste_row(2, start_y + S + gap_y)         # bottom 2

    elif star_count == 5:
        total_h = 3 * S + 2 * gap_y
        start_y = (H - total_h) // 2
        paste_row(2, start_y)                     # row 1: 2
        paste_row(1, start_y + S + gap_y)         # row 2: 1 (center)
        paste_row(2, start_y + 2 * (S + gap_y))   # row 3: 2

    else:
        # Fallback: single centered row
        row_w = star_count * S + (star_count - 1) * gap_x
        start_x = (W - row_w) // 2
        y = (H - S) // 2
        for i in range(star_count):
            x = start_x + i * (S + gap_x)
            card.paste(star_icon, (x, y), mask=star_icon)

    return card



def render_lucky_board(game: LuckyStars, reveal=False) -> io.BytesIO:

    #Render Lucky Stars board:
    #- Dealer row (top)
    #- Middle row (initial deal)
    #- Player row (bottom)

    width = LuckyStars.CARD_W * 2 + LuckyStars.GAP_X + LuckyStars.MARGIN_X * 2
    height = LuckyStars.CARD_H * 3 + LuckyStars.GAP_Y * 4
    canvas = Image.new("RGBA", (width, height), (0, 128, 0, 255))

    # X positions for two cards
    left_x = LuckyStars.MARGIN_X
    right_x = left_x + LuckyStars.CARD_W + LuckyStars.GAP_X
    x_positions = [left_x, right_x]

    # Y positions for rows
    dealer_y = LuckyStars.MARGIN_Y
    middle_y = dealer_y + LuckyStars.CARD_H + LuckyStars.GAP_Y
    player_y = middle_y + LuckyStars.CARD_H + LuckyStars.GAP_Y

    if not reveal:
        # Before reveal → both cards facedown in the middle
        for i, x in enumerate(x_positions):
            sprite = backs.get("back_full").resize((LuckyStars.CARD_W, LuckyStars.CARD_H), Image.NEAREST)
            canvas.paste(sprite, (x, middle_y), mask=sprite)
    else:
        # After reveal → split into player & dealer rows
        player_idx = game.picked
        dealer_idx = 1 - player_idx
        values = [game.left_card, game.right_card]

        for i, x in enumerate(x_positions):
            val = values[i]
            sprite = make_card_with_stars(val, game)
            y = player_y if i == player_idx else dealer_y
            canvas.paste(sprite, (x, y), mask=sprite)

    out = io.BytesIO()
    canvas.save(out, format="PNG")
    out.seek(0)
    return out

def make_slide_animation(game, duration=200, tail_hold_ms=2500) -> io.BytesIO:
    
    #  Flip + slide animation
    #  duration: per-frame duration in ms
    #  tail_hold_ms: how long to 'freeze' on last frame (ms)
   
    board_w = game.CARD_W * 2 + game.GAP_X + game.MARGIN_X * 2
    board_h = game.CARD_H * 3 + game.GAP_Y * 4
    base = Image.new("RGBA", (board_w, board_h), (0, 128, 0, 255))

    # X/Y positions
    left_x = game.MARGIN_X
    right_x = left_x + game.CARD_W + game.GAP_X
    x_positions = [left_x, right_x]

    dealer_y = game.MARGIN_Y
    middle_y = dealer_y + game.CARD_H + game.GAP_Y
    player_y = middle_y + game.CARD_H + game.GAP_Y

    player_idx = game.picked
    values = [game.left_card, game.right_card]

    frames: list[Image.Image] = []

    # ---- Step 1: Flip at middle (back_full -> half -> edge -> star card) ----
    def _flip_sprite(i: int, stage: int) -> Image.Image:
        if stage == 0: spr = backs.get("back_full")
        elif stage == 1: spr = backs.get("back_half")
        elif stage == 2: spr = backs.get("back_edge")
        else: spr = make_card_with_stars(values[i], game)  # card face
        return spr.resize((game.CARD_W, game.CARD_H), Image.NEAREST)

    for stage in range(4):
        frame = base.copy()
        for i in (0, 1):
            sprite = _flip_sprite(i, stage)
            frame.paste(sprite, (x_positions[i], middle_y), mask=sprite)
        frames.append(frame)

    # ---- Step 2: Slide apart with revealed faces ----
    steps = 8
    for step in range(steps + 1):
        frame = base.copy()
        t = step / steps
        for i in (0, 1):
            target_y = player_y if i == player_idx else dealer_y
            y = int(middle_y + (target_y - middle_y) * t)
            sprite = make_card_with_stars(values[i], game).resize((game.CARD_W, game.CARD_H), Image.NEAREST)
            frame.paste(sprite, (x_positions[i], y), mask=sprite)
        frames.append(frame)

    # ---- Step 3: Hold the last frame ----
    final_frame = frames[-1]
    hold_frames = max(1, int(tail_hold_ms / duration))
    frames.extend([final_frame] * hold_frames)

    # ---- Encode GIF ----
    out = io.BytesIO()
    frames[0].save(
        out,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=duration,
        loop=1,
        disposal=2,
        optimize=False,
    )
    out.seek(0)
    return out



def draw_card_face(star_count: int) -> Image.Image:
    
    #Render a Lucky Stars card with N stars drawn on it.
    #Uses the pre-resized blank_full and star from assetloader.
    
    blank = assets.get("blank_full").copy().convert("RGBA")
    star_icon = assets.get("star").copy().convert("RGBA")

    W, H = blank.size
    star_w, star_h = star_icon.size

    card = Image.new("RGBA", blank.size, (0, 0, 0, 0))
    card.paste(blank, (0, 0), mask=blank)

    # Center stars horizontally
    gap = 4
    total_w = star_count * star_w + (star_count - 1) * gap
    start_x = (W - total_w) // 2
    y = (H - star_h) // 2

    for i in range(star_count):
        x = start_x + i * (star_w + gap)
        card.paste(star_icon, (x, y), mask=star_icon)

    return card
