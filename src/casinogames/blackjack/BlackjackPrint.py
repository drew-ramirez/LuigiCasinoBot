###########################################################
# File: BlackjackPrint.py
#
# Description: Lightweight rendering helpers for Blackjack.
# Currently text/emoji-only, slotting in image assets later
# once I can find proper art.
###########################################################

from __future__ import annotations

import io
from typing import Iterable

from casinogames.blackjack.Blackjack import Blackjack
from casinogames.cards.standard_deck import Card, format_hand

# Suit/face glyphs used for text output
HIDDEN_CARD = "🂠"


def _render_hand_cards(hand: Iterable[Card], *, reveal: bool = True, use_emoji: bool = True) -> str:
    if not reveal:
        return f"{HIDDEN_CARD} {format_hand(list(hand)[1:], use_emoji=use_emoji)}"
    return format_hand(list(hand), use_emoji=use_emoji)


def render_text_board(game: Blackjack, *, hide_dealer_hole: bool = True, use_emoji: bool = True) -> str:
    """
    Return a simple multiline string summarizing the table state.
    Example:
        Dealer: 🂠 9♦️
        You: A♠️ J♥️ (21)
    """
    dealer_hand = _render_hand_cards(
        game.dealer_hand,
        reveal=not hide_dealer_hole and not game.finished,
        use_emoji=use_emoji,
    )
    player_hand = _render_hand_cards(game.player_hand, reveal=True, use_emoji=use_emoji)

    dealer_total = "??" if (hide_dealer_hole and not game.finished) else game._snapshot(outcome="peek")["dealer_total"]
    player_total = game._snapshot(outcome="peek")["player_total"]

    lines = [
        f"Dealer: {dealer_hand} ({dealer_total})",
        f"You: {player_hand} ({player_total})",
    ]
    return "\n".join(lines)


def render_text_board_file(game: Blackjack, *, hide_dealer_hole: bool = True, use_emoji: bool = True) -> io.BytesIO:
    """Wrap the text board in a BytesIO for Discord file attachments."""
    board_text = render_text_board(game, hide_dealer_hole=hide_dealer_hole, use_emoji=use_emoji)
    out = io.BytesIO(board_text.encode("utf-8"))
    out.seek(0)
    return out
