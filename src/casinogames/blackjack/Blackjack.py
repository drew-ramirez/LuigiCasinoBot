###########################################################
# File: Blackjack.py
#
# Description: Core blackjack model
# Handles dealing, hit/stand/double, dealer play, and
# payout, currently 3:2 for player blackjack.
###########################################################

from __future__ import annotations

from typing import Dict, List, Optional

from casinogames.cards.standard_deck import (
    Card,
    best_blackjack_total,
    build_deck,
    draw_cards,
)


class Blackjack:
    GAME_KEY = "blackjack"

    def __init__(self, bet: int, *, dealer_hits_soft_17: bool = False):
        self.base_bet = max(1, int(bet))
        self.dealer_hits_soft_17 = bool(dealer_hits_soft_17)
        self.deck: List[Card] = build_deck()
        self.player_hand: List[Card] = draw_cards(self.deck, 2)
        self.dealer_hand: List[Card] = draw_cards(self.deck, 2)
        self.doubled = False
        self.finished = False
        self.result: Optional[Dict] = None

    # -----------------------------------------------------
    # Derived values
    # -----------------------------------------------------
    @property
    def stake(self) -> int:
        return self.base_bet * (2 if self.doubled else 1)

    @staticmethod
    def _is_blackjack(hand: List[Card]) -> bool:
        total, _ = best_blackjack_total(hand)
        return len(hand) == 2 and total == 21

    def player_total(self):
        return best_blackjack_total(self.player_hand)

    def dealer_total(self):
        return best_blackjack_total(self.dealer_hand)

    # -----------------------------------------------------
    # Player actions
    # -----------------------------------------------------
    def hit(self) -> Dict:
        self._assert_active()
        draw_cards(self.deck, 0)  # ensure deck exists even if empty
        self.player_hand.extend(draw_cards(self.deck, 1))
        total, _ = best_blackjack_total(self.player_hand)
        if total > 21:
            return self._finalize("bust", payout=0)
        return self._snapshot(outcome="in_progress")

    def stand(self) -> Dict:
        self._assert_active()
        return self._resolve_showdown()

    def double_down(self) -> Dict:
        self._assert_active()
        if self.doubled or len(self.player_hand) != 2:
            raise ValueError("Double down only allowed on initial hand.")
        self.doubled = True
        self.player_hand.extend(draw_cards(self.deck, 1))
        total, _ = best_blackjack_total(self.player_hand)
        if total > 21:
            return self._finalize("bust", payout=0)
        return self._resolve_showdown()

    # -----------------------------------------------------
    # Dealer + outcome resolution
    # -----------------------------------------------------
    def _dealer_play(self) -> None:
        while True:
            total, is_soft = best_blackjack_total(self.dealer_hand)
            if total < 17:
                self.dealer_hand.extend(draw_cards(self.deck, 1))
                continue
            if total == 17 and is_soft and self.dealer_hits_soft_17:
                self.dealer_hand.extend(draw_cards(self.deck, 1))
                continue
            break

    def _resolve_showdown(self) -> Dict:
        player_total, _ = best_blackjack_total(self.player_hand)
        dealer_total, _ = best_blackjack_total(self.dealer_hand)

        player_bj = self._is_blackjack(self.player_hand)
        dealer_bj = self._is_blackjack(self.dealer_hand)

        if player_bj and dealer_bj:
            return self._finalize("push", payout=self.stake)
        if player_bj:
            payout = int(round(self.base_bet * 2.5))
            return self._finalize("blackjack", payout=payout)
        if dealer_bj:
            return self._finalize("lose", payout=0)

        self._dealer_play()
        dealer_total, _ = best_blackjack_total(self.dealer_hand)

        if dealer_total > 21:
            return self._finalize("win", payout=self.stake * 2)
        player_total, _ = best_blackjack_total(self.player_hand)

        if player_total > dealer_total:
            return self._finalize("win", payout=self.stake * 2)
        if player_total < dealer_total:
            return self._finalize("lose", payout=0)
        return self._finalize("push", payout=self.stake)

    # -----------------------------------------------------
    # Helpers
    # -----------------------------------------------------
    def _snapshot(self, *, outcome: str) -> Dict:
        player_total, player_soft = best_blackjack_total(self.player_hand)
        dealer_total, dealer_soft = best_blackjack_total(self.dealer_hand)
        return {
            "outcome": outcome,
            "stake": self.stake,
            "base_bet": self.base_bet,
            "player_total": player_total,
            "player_soft": player_soft,
            "dealer_total": dealer_total,
            "dealer_soft": dealer_soft,
            "player_hand": list(self.player_hand),
            "dealer_hand": list(self.dealer_hand),
        }

    def _finalize(self, outcome: str, *, payout: int) -> Dict:
        if self.finished:
            return self.result or {}
        self.finished = True
        snapshot = self._snapshot(outcome=outcome)
        snapshot["payout"] = int(payout)
        snapshot["net"] = int(payout - self.stake)
        # cache totals for timeout/cleanup metadata
        self.player_total_cached = snapshot.get("player_total")
        self.dealer_total_cached = snapshot.get("dealer_total")
        self.result = snapshot
        return snapshot

    def _assert_active(self) -> None:
        if self.finished:
            raise RuntimeError("Round already finished.")
