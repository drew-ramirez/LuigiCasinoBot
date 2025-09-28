###########################################################
# File: BoardRenderer.py
#
# Description: Shared rendering helper for card grid games
# (used by MemoryMatch, Pair-a-Gone, etc.)
###########################################################

from PIL import Image
import io

def render_board(game, sprite_resolver) -> io.BytesIO:
    ################################################################
    #Render the current board to a PNG image.

    #:param game: Instance of a game subclassing BaseGame
    #:param sprite_resolver: function (game, idx) -> Image
    #       Returns the sprite to draw for each board position
    #:return: BytesIO containing PNG data
    ################################################################
    cards = []
    num_cards = game.COLS * game.ROWS
    for idx in range(num_cards):
        cards.append(sprite_resolver(game, idx))

    canvas_w = game.COLS * (game.CARD_W + game.GAP_X) - game.GAP_X + 2 * game.MARGIN_X
    canvas_h = game.ROWS * (game.CARD_H + game.GAP_Y) - game.GAP_Y + 2 * game.MARGIN_Y
    canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 128, 0, 255))

    for i, card in enumerate(cards):
        col = i % game.COLS
        row = i // game.COLS
        x = game.MARGIN_X + col * (game.CARD_W + game.GAP_X)
        y = game.MARGIN_Y + row * (game.CARD_H + game.GAP_Y)
        canvas.paste(card, (x, y), mask=card)

    out = io.BytesIO()
    canvas.save(out, format="PNG")
    out.seek(0)
    return out
