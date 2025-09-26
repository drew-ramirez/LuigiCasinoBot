from PIL import Image
import io
from casinogames.assetloader import load_memory_faces
from casinogames.pairagone.PairAGone import PairAGone
from casinogames.core.BoardRenderer import render_board

faces = load_memory_faces()

def render_pair_board(game: PairAGone) -> io.BytesIO:
    def sprite_resolver(game, idx):
        symbol = game.board[idx]
        if symbol:
            return faces.get_face(symbol)
        else:
            return Image.new("RGBA", (game.CARD_W, game.CARD_H), (0, 0, 0, 0))
    return render_board(game, sprite_resolver)

def make_pair_flicker_gif(game, positions: list[int], symbols: list[str], duration=150) -> io.BytesIO:
    # Flicker animation for matched cards
    # Uses captured symbols (before gravity) so shifting doesn't break.

    frames = []

    # Base board image (as it looks now)
    base_bytes = render_pair_board(game)
    base_board = Image.open(base_bytes).convert("RGBA")

    for _ in range(3):  # 3 flicker cycles
        # Frame with cards visible (show captured symbols at positions)
        visible = base_board.copy()
        for pos, sym in zip(positions, symbols):
            slot_x, slot_y, slot_w, slot_h = game.get_slot_rect(pos)
            face = faces.get_face(sym)
            visible.paste(face, (slot_x, slot_y), mask=face)
        frames.append(visible)

        # Frame with those positions blanked
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
        loop=0,
        disposal=2,
        optimize=False,
    )
    out.seek(0)
    return out