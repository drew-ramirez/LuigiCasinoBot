###########################################################
# File: PicturePokerPrint.py
#
# Description: Rendering & animations for Picture Poker
###########################################################

from PIL import Image
import io
from casinogames.assetloader import load_memory_backs, load_memory_faces

backs = load_memory_backs()
faces = load_memory_faces()


def render_hand(hand: list[str], reveal: bool = False) -> list[Image.Image]:
    rendered = []
    for symbol in hand:
        if reveal:
            sprite = faces.get_face(symbol)
        else:
            sprite = backs.get("back_full")
        rendered.append(sprite)
    return rendered


def render_board(game, reveal=False) -> io.BytesIO:
    cols = 5
    width = (game.CARD_W + game.GAP_X) * cols + game.MARGIN_X * 2
    height = (game.CARD_H * 2) + (game.GAP_Y * 5) + game.MARGIN_Y * 2

    board = Image.new("RGBA", (width, height), (0, 128, 0, 255))

    for col in range(cols):
        dx = game.MARGIN_X + col * (game.CARD_W + game.GAP_X)
        dy = game.MARGIN_Y
        if reveal:
            sprite = faces.get_face(game.luigi_hand[col])
        else:
            sprite = backs.get("back_full")
        board.paste(sprite, (dx, dy), mask=sprite)

        px = game.MARGIN_X + col * (game.CARD_W + game.GAP_X)
        py = game.MARGIN_Y + game.CARD_H + (game.GAP_Y * 2)
        sprite = faces.get_face(game.player_hand[col])
        board.paste(sprite, (px, py), mask=sprite)

    out = io.BytesIO()
    board.save(out, format="PNG")
    out.seek(0)
    return out


def render_board_with_hidden(
    game, hidden_player=[], hidden_dealer=[], reveal_dealer=False
) -> io.BytesIO:
    cols = 5
    width = (game.CARD_W + game.GAP_X) * cols + game.MARGIN_X * 2
    height = (game.CARD_H * 2) + (game.GAP_Y * 5) + game.MARGIN_Y * 2
    board = Image.new("RGBA", (width, height), (0, 128, 0, 255))

    for col in range(cols):
        dx = game.MARGIN_X + col * (game.CARD_W + game.GAP_X)
        dy = game.MARGIN_Y
        if not reveal_dealer or col in hidden_dealer:
            sprite = backs.get("back_full")
        else:
            sprite = faces.get_face(game.luigi_hand[col])
        board.paste(sprite, (dx, dy), mask=sprite)

        px = game.MARGIN_X + col * (game.CARD_W + game.GAP_X)
        py = game.MARGIN_Y + game.CARD_H + (game.GAP_Y * 2)
        if col in hidden_player:
            sprite = backs.get("back_full")
        else:
            sprite = faces.get_face(game.player_hand[col])
        board.paste(sprite, (px, py), mask=sprite)

    out = io.BytesIO()
    board.save(out, format="PNG")
    out.seek(0)
    return out


# ---------- Animations ----------


def make_flip_animation(symbol: str, duration=150) -> io.BytesIO:
    sequence = [
        backs.get("back_full"),
        backs.get("back_half"),
        backs.get("back_edge"),
        faces.get_flip(symbol),
        faces.get_face(symbol),
    ]

    frames = []
    for frame in sequence:
        frame = frame.convert("RGBA").resize((136, 207), Image.NEAREST)
        canvas = Image.new("RGBA", (136, 207), (0, 128, 0, 255))
        canvas.paste(frame, (0, 0), mask=frame)
        frames.append(canvas)

    out = io.BytesIO()
    frames[0].save(
        out,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=duration,
        loop=0,
        disposal=2,
        optimize=False,
    )
    out.seek(0)
    return out


def make_deal_flip_gif(
    game,
    pos: int,
    symbol: str,
    base_board: Image.Image,
    duration: int = 150,
    dealer: bool = False,
) -> io.BytesIO:
    sequence = [
        backs.get("back_full"),
        backs.get("back_half"),
        backs.get("back_edge"),
        faces.get_flip(symbol),
        faces.get_face(symbol),
    ]

    slot_x, slot_y, slot_w, slot_h = game.get_slot_rect(pos, dealer=dealer)

    frames = []
    for frame in sequence:
        frame = frame.convert("RGBA")
        norm = Image.new("RGBA", (slot_w, slot_h), (0, 0, 0, 0))
        x_off = (slot_w - frame.width) // 2
        y_off = (slot_h - frame.height) // 2
        norm.paste(frame, (x_off, y_off), mask=frame)

        step = base_board.copy()
        blank = Image.new("RGBA", (slot_w, slot_h), (0, 128, 0, 255))
        step.paste(blank, (slot_x, slot_y))
        step.paste(norm, (slot_x, slot_y), mask=norm)
        frames.append(step)

    final_frame = frames[-1]
    for _ in range(8):
        frames.append(final_frame)

    out = io.BytesIO()
    frames[0].save(
        out,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=duration,
        loop=0,
        disposal=2,
        optimize=False,
    )
    out.seek(0)
    return out


def render_board_with_dealer_revealed(game, revealed_slots: list[int]) -> io.BytesIO:
    cols = 5
    width = (game.CARD_W + game.GAP_X) * cols + game.MARGIN_X * 2
    height = (game.CARD_H * 2) + (game.GAP_Y * 5) + game.MARGIN_Y * 2
    board = Image.new("RGBA", (width, height), (0, 128, 0, 255))

    for col in range(cols):
        x = game.MARGIN_X + col * (game.CARD_W + game.GAP_X)
        y = game.MARGIN_Y
        if col in revealed_slots:
            sprite = faces.get_face(game.luigi_hand[col])
        else:
            sprite = backs.get("back_full")
        board.paste(sprite, (x, y), mask=sprite)

        px = game.MARGIN_X + col * (game.CARD_W + game.GAP_X)
        py = game.MARGIN_Y + game.CARD_H + (game.GAP_Y * 2)
        sprite = faces.get_face(game.player_hand[col])
        board.paste(sprite, (px, py), mask=sprite)

    out = io.BytesIO()
    board.save(out, format="PNG")
    out.seek(0)
    return out


def reveal_final(game) -> io.BytesIO:
    return render_board_with_hidden(game, reveal_dealer=True)


def make_discard_flicker_gif(
    game, pos: int, base_board: Image.Image, duration: int = 120, dealer: bool = True
) -> io.BytesIO:
    slot_x, slot_y, slot_w, slot_h = game.get_slot_rect(pos, dealer=dealer)

    overlay_red = Image.new("RGBA", (slot_w, slot_h), (255, 0, 0, 128))
    blank = Image.new("RGBA", (slot_w, slot_h), (0, 128, 0, 255))
    back = backs.get("back_full").convert("RGBA")

    sequence = [overlay_red, blank, back]

    frames = []
    for frame in sequence:
        step = base_board.copy()
        step.paste(frame, (slot_x, slot_y), mask=frame)
        frames.append(step)

    out = io.BytesIO()
    frames[0].save(
        out,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=duration,
        loop=0,
        disposal=2,
        optimize=False,
    )
    out.seek(0)
    return out


def make_final_reveal_gif(self, duration=150) -> io.BytesIO:
    cols = 5
    width = (self.CARD_W + self.GAP_X) * cols + self.MARGIN_X * 2
    height = (self.CARD_H * 2) + (self.GAP_Y * 5) + self.MARGIN_Y * 2
    base_board = Image.new("RGBA", (width, height), (0, 128, 0, 255))

    # player row (always face-up)
    for col in range(cols):
        px = self.MARGIN_X + col * (self.CARD_W + self.GAP_X)
        py = self.MARGIN_Y + self.CARD_H + (self.GAP_Y * 2)
        sprite = faces.get_face(self.player_hand[col])
        base_board.paste(sprite, (px, py), mask=sprite)

    sequence = [
        backs.get("back_full"),
        backs.get("back_half"),
        backs.get("back_edge"),
        "face",
    ]

    frames = []
    for frame in sequence:
        board = base_board.copy()
        for col in range(cols):
            dx = self.MARGIN_X + col * (self.CARD_W + self.GAP_X)
            dy = self.MARGIN_Y
            if frame == "face":
                sprite = faces.get_face(self.luigi_hand[col])
            else:
                sprite = frame
            board.paste(sprite, (dx, dy), mask=sprite)
        frames.append(board)

    final_frame = frames[-1]
    for _ in range(8):
        frames.append(final_frame)

    out = io.BytesIO()
    frames[0].save(
        out,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=duration,
        loop=1,  # play once, freeze on last frame
        disposal=2,
        optimize=False,
    )
    out.seek(0)
    return out
