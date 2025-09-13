from PIL import Image
import io
from casinogames.assetloader import load_memory_faces, load_memory_backs

faces = load_memory_faces()
backs = load_memory_backs()

CARD_W, CARD_H = 136, 207
MARGIN = 10

def render_board_image(game, overrides=None) -> io.BytesIO:
    """Render the current board as a single PNG image.
    If overrides is provided, use those images at specific positions.
    """
    overrides = overrides or {}

    cards = []
    for idx, (symbol, flipped, matched) in enumerate(game.board):
        if idx in overrides:
            sprite = overrides[idx]  # custom override image (can be temp frame, etc.)
        elif matched or flipped:
            sprite = faces.get_face(symbol)
        else:
            sprite = backs.get("back_full")
        cards.append(sprite)

    row_size = 4 if len(cards) <= 12 else 5
    cols = row_size
    rows = (len(cards) + cols - 1) // cols

    canvas_w = cols * (CARD_W + MARGIN) - MARGIN
    canvas_h = rows * (CARD_H + MARGIN) - MARGIN

    canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 128, 0, 255))  # green bg

    for i, card in enumerate(cards):
        col = i % cols
        row = i // cols
        x = col * (CARD_W + MARGIN)
        y = row * (CARD_H + MARGIN)
        canvas.paste(card, (x, y), mask=card)

    out = io.BytesIO()
    canvas.save(out, format="PNG")
    out.seek(0)
    return out


# Helper Function for Animating ONE CARD
def make_flip_gif(symbol: str, forward=True) -> io.BytesIO:
    """Create a flip GIF for one card."""
    sequence = []
    if forward:
        sequence = [
            faces.get_face(symbol),
            faces.get_flip(symbol),
            backs.get("back_edge"),
            backs.get("back_half"),
            backs.get("back_full"),
        ]
    else:
        sequence = [
            backs.get("back_full"),
            backs.get("back_half"),
            backs.get("back_edge"),
            faces.get_flip(symbol),
            faces.get_face(symbol),
        ]

    canvas_w, canvas_h = 136, 207
    normalized = []
    for frame in sequence:
        new_img = Image.new("RGBA", (canvas_w, canvas_h), (255, 255, 255, 255))
        x_offset = (canvas_w - frame.width) // 2
        y_offset = (canvas_h - frame.height) // 2
        new_img.paste(frame, (x_offset, y_offset), mask=frame)
        normalized.append(new_img)

    # Freeze on last frame to fake one-loop
    final_frame = normalized[-1]
    for _ in range(10):
        normalized.append(final_frame)

    byte_arr = io.BytesIO()
    normalized[0].save(
        byte_arr,
        format="GIF",
        save_all=True,
        append_images=normalized[1:],
        duration=100,
        loop=1
    )
    byte_arr.seek(0)
    return byte_arr


def make_board_flip_gif(game, pos: int, symbol: str, duration=120) -> io.BytesIO:
    #Build a GIF of the whole board with one slot flipping

    # Frames of the flip: back, edge, half, face
    frames = [
        backs.get("back_full"),
        backs.get("back_half"),
        backs.get("back_edge"),
        faces.get_face(symbol),
    ]

    board_frames = []
    for frame in frames:
        img_bytes = render_board_image(game, overrides={pos: frame})
        board_img = Image.open(img_bytes).convert("RGBA")
        board_frames.append(board_img)

    # Normalize to same size
    max_w = max(f.width for f in board_frames)
    max_h = max(f.height for f in board_frames)
    normalized = []
    for f in board_frames:
        new_img = Image.new("RGBA", (max_w, max_h), (0, 0, 0, 0))
        x = (max_w - f.width) // 2
        y = (max_h - f.height) // 2
        new_img.paste(f, (x, y))
        normalized.append(new_img)

    out = io.BytesIO()
    normalized[0].save(
        out,
        format="GIF",
        save_all=True,
        append_images=normalized[1:],
        duration=duration,
        loop=0,
        disposal=2,
    )
    out.seek(0)
    return out

def make_board_reverse_flip_gif(game, positions: list[int], symbols: list[str], duration=120) -> io.BytesIO:
    # Make a board-level GIF where multiple cards flip back to facedown simultaneously.
    # Reverse frames: face, edge, back
    frames = [
        faces.get_face(symbols[0]),
        backs.get("back_edge"),
        backs.get("back_half"),
        backs.get("back_full"),
    ]

    board_frames = []
    for f in frames:
        overrides = {}
        for pos, sym in zip(positions, symbols):
            overrides[pos] = f if f != faces.get_face(symbols[0]) else faces.get_face(sym)
        img_bytes = render_board_image(game, overrides=overrides)
        board_frames.append(Image.open(img_bytes).convert("RGBA"))

    out = io.BytesIO()
    board_frames[0].save(
        out,
        format="GIF",
        save_all=True,
        append_images=board_frames[1:],
        duration=duration,
        loop=0,
        disposal=2,
    )
    out.seek(0)
    return out