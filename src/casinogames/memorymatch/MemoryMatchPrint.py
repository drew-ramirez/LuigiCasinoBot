from PIL import Image
import io
from casinogames.assetloader import load_memory_faces, load_memory_backs
from casinogames.memorymatch.MemoryMatch import MemoryMatch
from casinogames.core.BoardRenderer import render_board

faces = load_memory_faces()
backs = load_memory_backs()

def _normalize_sprite(sprite: Image.Image, game: MemoryMatch) -> Image.Image:
    #face/back/flip is resized to the game’s card dimensions
    if sprite.size != (game.CARD_W, game.CARD_H):
        sprite = sprite.resize((game.CARD_W, game.CARD_H), Image.NEAREST)
    return sprite

# tried using this to reduce the blur on image updates but I dont think it works at all
# thoght discord was upscaling the image at first not true
TARGET_WIDTH = 540
def _scale_canvas(img: Image.Image) -> Image.Image:
    """Scale the rendered board up to the target width using nearest-neighbour."""
    if img.width >= TARGET_WIDTH:
        return img
    ratio = TARGET_WIDTH / img.width
    new_height = int(round(img.height * ratio))
    return img.resize((TARGET_WIDTH, new_height), Image.NEAREST)


def render_board_image(game, overrides=None) -> io.BytesIO:
    # Render the current board as a single PNG image
    overrides = overrides or {}

    def sprite_resolver(game, idx):
        symbol, flipped, matched = game.board[idx]
        if idx in overrides:
            sprite = overrides[idx]
        elif matched or flipped:
            sprite = faces.get_face(symbol)
        else:
            sprite = backs.get("back_full")
        return _normalize_sprite(sprite, game)  # resize here

    board = Image.open(render_board(game, sprite_resolver)).convert("RGBA")
    board = _scale_canvas(board)

    out = io.BytesIO()
    board.save(out, format="PNG")
    out.seek(0)
    return out


def make_board_flip_gif(game, pos: int, symbol: str, duration=90) -> io.BytesIO:
    # Build a GIF of the whole board with one slot flipping

    # Frames of the flip: back, edge, half, face
    sequence = [
        backs.get("back_full"),
        backs.get("back_half"),
        backs.get("back_edge"),
        faces.get_flip(symbol),
        faces.get_face(symbol),
    ]

    base_board = Image.open(render_board_image(game)).convert("RGBA")

    slot_x, slot_y, slot_w, slot_h = game.get_slot_rect(pos)

    frames = []
    for frame in sequence:
        frame = _normalize_sprite(frame.convert("RGBA"), game)

        # Start fresh from base
        board_img = base_board.copy()

        # Blank the slot area (green background) so old images don’t overlap
        blank = Image.new("RGBA", (slot_w, slot_h), (0, 128, 0, 255))
        board_img.paste(blank, (slot_x, slot_y))

        # Paste the current frame
        board_img.paste(frame, (slot_x, slot_y), mask=frame)
        frames.append(board_img)

    palette_frames = [
        f.convert("P", palette=Image.ADAPTIVE, dither=Image.NONE) for f in frames
    ]
    out = io.BytesIO()
    palette_frames[0].save(
        out,
        format="GIF",
        save_all=True,
        append_images=palette_frames[1:],
        duration=duration,
        loop=0,
        disposal=2,
        optimize=False,
    )
    out.seek(0)
    return out


def make_board_reverse_flip_gif(
    game, positions: list[int], symbols: list[str], duration=90
) -> io.BytesIO:
    # Flip multiple cards back to facedown with green background normalization

    sequences = []
    for sym in symbols:
        seq = [
            faces.get_face(sym),
            faces.get_flip(sym),
            backs.get("back_edge"),
            backs.get("back_half"),
            backs.get("back_full"),
        ]
        sequences.append(seq)

    base_board = Image.open(render_board_image(game)).convert("RGBA")

    rects = [game.get_slot_rect(p) for p in positions]

    frames = []
    for frame_idx in range(len(sequences[0])):  # all sequences have same length
        step = base_board.copy()
        for seq, (slot_x, slot_y, slot_w, slot_h) in zip(sequences, rects):
            raw = _normalize_sprite(seq[frame_idx].convert("RGBA"), game)

            # Blank the slot area (green background) so old images don’t overlap
            blank = Image.new("RGBA", (slot_w, slot_h), (0, 128, 0, 255))
            step.paste(blank, (slot_x, slot_y))

            # Paste the current frame
            step.paste(raw, (slot_x, slot_y), mask=raw)
        frames.append(step)

    W = max(f.width for f in frames)
    H = max(f.height for f in frames)
    normalized = []
    for f in frames:
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        canvas.paste(f, (0, 0))
        normalized.append(canvas)

    palette_frames = [
        f.convert("P", palette=Image.ADAPTIVE, dither=Image.NONE) for f in normalized
    ]
    out = io.BytesIO()
    palette_frames[0].save(
        out,
        format="GIF",
        save_all=True,
        append_images=palette_frames[1:],
        duration=duration,
        loop=0,
        disposal=2,
        optimize=False,
    )
    out.seek(0)
    return out
