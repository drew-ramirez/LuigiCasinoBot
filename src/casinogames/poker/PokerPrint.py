###########################################################
# File: PokerPrint.py
#
# Description: Text rendering helpers for draw poker.
###########################################################

from __future__ import annotations

import io
from typing import Iterable

from casinogames.cards.standard_deck import Card, format_hand
from casinogames.poker.Poker import Poker

HIDDEN = "🂠"


def _render_hand(hand: Iterable[Card], *, hide: bool = False, use_emoji: bool = True) -> str:
    cards = list(hand)
    if hide:
        return f"{HIDDEN} {format_hand(cards[1:], use_emoji=use_emoji)}"
    return format_hand(cards, use_emoji=use_emoji)


def render_text_board(game: Poker, *, hide_dealer: bool = True, use_emoji: bool = True) -> str:
    """
    Return multiline text:
        Dealer: 🂠 K♦️ 7♣️ ? (hidden)
        You: A♠️ J♥️ 9♣️ 6♦️ 2♠️
    """
    dealer = _render_hand(game.dealer_hand, hide=hide_dealer, use_emoji=use_emoji)
    player = _render_hand(game.player_hand, hide=False, use_emoji=use_emoji)
    status = "(hidden)" if hide_dealer else ""
    lines = [
        f"Dealer: {dealer} {status}".strip(),
        f"You: {player}",
    ]
    return "\n".join(lines)


def render_text_board_file(game: Poker, *, hide_dealer: bool = True, use_emoji: bool = True) -> io.BytesIO:
    out = io.BytesIO(render_text_board(game, hide_dealer=hide_dealer, use_emoji=use_emoji).encode("utf-8"))
    out.seek(0)
    return out
