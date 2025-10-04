from PIL import Image
import io
from casinogames.assetloader import load_memory_faces, load_memory_backs
from casinogames.pairagone.PairAGone import PairAGone
from casinogames.core.BoardRenderer import render_board

faces = load_memory_faces()
backs = load_memory_backs()


# ---------- Normal board render ----------
def render_pair_board(game: PairAGone) -> io.BytesIO:
    def sprite_resolver(game, idx):
        symbol = game.board[idx]
        if symbol:
            return faces.get_face(symbol)
        else:
            return Image.new("RGBA", (game.CARD_W, game.CARD_H), (0, 0, 0, 0))

    return render_board(game, sprite_resolver)


# ---------- Render with blanks (for new cards) ----------
def render_pair_board_with_blanks(game, blanks: list[int]) -> io.BytesIO:

    # Render the board but force given slots to be solid green blanks.
    # Used right after compaction so new cards don't spawn face-up instantly.

    def sprite_resolver(game, idx):
        if idx in blanks:
            return Image.new("RGBA", (game.CARD_W, game.CARD_H), (0, 128, 0, 255))
        symbol = game.board[idx]
        if symbol:
            return faces.get_face(symbol)
        return Image.new("RGBA", (game.CARD_W, game.CARD_H), (0, 0, 0, 0))

    return render_board(game, sprite_resolver)


# ---------- Flicker animation ----------
def make_pair_flicker_gif(
    game, positions: list[int], symbols: list[str], duration=150
) -> io.BytesIO:
    frames = []

    base_bytes = render_pair_board(game)
    base_board = Image.open(base_bytes).convert("RGBA")

    for _ in range(3):  # 3 flicker cycles
        # visible
        visible = base_board.copy()
        for pos, sym in zip(positions, symbols):
            slot_x, slot_y, slot_w, slot_h = game.get_slot_rect(pos)
            face = faces.get_face(sym)
            visible.paste(face, (slot_x, slot_y), mask=face)
        frames.append(visible)

        # blanked
        flickered = base_board.copy()
        for pos in positions:
            slot_x, slot_y, slot_w, slot_h = game.get_slot_rect(pos)
            blank = Image.new("RGBA", (slot_w, slot_h), (0, 128, 0, 255))  # green bg
            flickered.paste(blank, (slot_x, slot_y))
        frames.append(flickered)

    out = io.BytesIO()
    frames[0].save(
        out,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=duration,
        loop=0,  # play once
        disposal=2,
        optimize=False,
    )
    out.seek(0)
    return out


# ---------- Dealer flip animation ----------
def make_deal_flip_gif(
    game, pos: int, symbol: str, base_board: Image.Image, duration=120
) -> io.BytesIO:

    backs = load_memory_backs()
    faces = load_memory_faces()

    sequence = [
        backs.get("back_full"),
        backs.get("back_half"),
        backs.get("back_edge"),
        faces.get_flip(symbol),
        faces.get_face(symbol),
    ]
    slot_x, slot_y, slot_w, slot_h = game.get_slot_rect(pos)

    frames = []
    for frame in sequence:
        frame = frame.convert("RGBA")

        # transparent normalize canvas
        # TODO: shouldn't have to normalize?? figure this out later
        norm_frame = Image.new("RGBA", (game.CARD_W, game.CARD_H), (0, 0, 0, 0))
        x_off = (game.CARD_W - frame.width) // 2
        y_off = (game.CARD_H - frame.height) // 2
        norm_frame.paste(frame, (x_off, y_off), mask=frame)

        # Copy base board, clear slot area to green, then paste frame
        board_img = base_board.copy()
        blank = Image.new(
            "RGBA", (slot_w, slot_h), (0, 128, 0, 255)
        )  # green background for slot
        board_img.paste(blank, (slot_x, slot_y))
        board_img.paste(norm_frame, (slot_x, slot_y), mask=norm_frame)
        frames.append(board_img)

    # padding the last frame so Discord "freezes" instead of looping weirdly
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
