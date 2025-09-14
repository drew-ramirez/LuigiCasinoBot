from PIL import Image
import io
from casinogames.assetloader import load_memory_faces, load_memory_backs
from casinogames.memorymatch.MemoryMatch import MemoryMatch

faces = load_memory_faces()
backs = load_memory_backs()

def render_board_image(game, overrides=None) -> io.BytesIO:
    # Render the current board as a single PNG image
    overrides = overrides or {}
    cards = []
    for idx, (symbol, flipped, matched) in enumerate(game.board):
        if idx in overrides:
            sprite = overrides[idx]
        elif matched or flipped:
            sprite = faces.get_face(symbol)
        else:
            sprite = backs.get("back_full")
        cards.append(sprite)

    cols = game.COLS
    rows = (len(cards) + cols - 1) // cols
    canvas_w = cols * (game.CARD_W + game.GAP_X) - game.GAP_X + 2 * game.MARGIN_X
    canvas_h = rows * (game.CARD_H + game.GAP_Y) - game.GAP_Y + 2 * game.MARGIN_Y

    canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 128, 0, 255))  # green bg

    for i, card in enumerate(cards):
        col = i % cols
        row = i // cols
        x = game.MARGIN_X + col * (game.CARD_W + game.GAP_X)
        y = game.MARGIN_Y + row * (game.CARD_H + game.GAP_Y)
        canvas.paste(card, (x, y), mask=card)

    out = io.BytesIO()
    canvas.save(out, format="PNG")
    out.seek(0)
    return out

def make_board_flip_gif(game, pos: int, symbol: str, duration=120) -> io.BytesIO:
    #Build a GIF of the whole board with one slot flipping

    # Frames of the flip: back, edge, half, face
    
    sequence = [
        backs.get("back_full"),
        backs.get("back_half"),
        backs.get("back_edge"),
        faces.get_flip(symbol),
        faces.get_face(symbol),
    ]

    bg_bytes = render_board_image(game)
    base_board = Image.open(bg_bytes).convert("RGBA")

    slot_x, slot_y, slot_w, slot_h = game.get_slot_rect(pos)

    frames = []
    for frame in sequence:
        frame = frame.convert("RGBA")

        # Normalize frame onto white canvas same size as card
        norm_frame = Image.new("RGBA", (game.CARD_W, game.CARD_H), (255, 255, 255, 255))
        x_off = (game.CARD_W - frame.width) // 2
        y_off = (game.CARD_H - frame.height) // 2
        norm_frame.paste(frame, (x_off, y_off), mask=frame)

        # Compose on board
        board_img = base_board.copy()
        board_img.paste(norm_frame, (slot_x, slot_y), mask=norm_frame)
        frames.append(board_img)

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

def make_board_reverse_flip_gif(game, positions: list[int], symbols: list[str], duration=120) -> io.BytesIO:
    # Flip multiple cards back to facedown with white background normalization
    
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

    bg_bytes = render_board_image(game)
    base_board = Image.open(bg_bytes).convert("RGBA")

    rects = [game.get_slot_rect(p) for p in positions]

    frames = []
    for frame_idx in range(len(sequences[0])):  # all sequences have same length
        step = base_board.copy()
        for seq, (slot_x, slot_y, slot_w, slot_h) in zip(sequences, rects):
            raw = seq[frame_idx].convert("RGBA")

            # normalize to CARD_W x CARD_H with white background
            norm_frame = Image.new("RGBA", (game.CARD_W, game.CARD_H), (255, 255, 255, 255))
            x_off = (game.CARD_W - raw.width) // 2
            y_off = (game.CARD_H - raw.height) // 2
            norm_frame.paste(raw, (x_off, y_off), mask=raw)

            # paste onto board
            step.paste(norm_frame, (slot_x, slot_y), mask=norm_frame)
        frames.append(step)

    W = max(f.width for f in frames)
    H = max(f.height for f in frames)
    normalized = []
    for f in frames:
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        canvas.paste(f, (0, 0))
        normalized.append(canvas)

    out = io.BytesIO()
    normalized[0].save(
        out,
        format="GIF",
        save_all=True,
        append_images=normalized[1:],
        duration=duration,
        loop=0,
        disposal=2,
        optimize=False,
    )
    out.seek(0)
    return out