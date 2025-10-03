###########################################################
# File: PicturePoker.py
#
# Description: Game logic for Luigi’s Casino Picture Poker
###########################################################

import random
from collections import Counter

class PicturePoker:
    SYMBOLS = ["cloud", "mushroom", "flower", "luigi", "mario", "star"]

    #hand ranks in order (lowest to highest)
    HAND_RANKS = {
        "junk": 0,
        "one_pair": 1,
        "two_pair": 2,
        "three_kind": 3,
        "full_house": 4,
        "four_kind": 5,
        "five_kind": 6
    }

    #multiplier for winnings
    MULTIPLIER = {
        "one_pair": 2,
        "two_pair": 3,
        "three_kind": 4,
        "full_house": 6,
        "four_kind": 8,
        "five_kind": 16
    }

    def __init__(self, starting_coins: int = 20, starting_stars: int = 0):
        self.starting_coins = starting_coins
        self.starting_stars = starting_stars
        self.reset()

    def reset(self):
        #reset game state
        self.coins = self.starting_coins
        self.stars = self.starting_stars
        self.round = 0
        self.deck = []
        self.player_hand = []
        self.luigi_hand = []
        self.bet = 0
        self.result = None

    def _build_deck(self):
        #deck has 5 copies of each of the 6 symbols = 30 cards
        self.deck = []
        for sym in self.SYMBOLS:
            self.deck.extend([sym] * 5)
        random.shuffle(self.deck)

    def _draw_cards(self, n: int) -> list[str]:
        #draw n cards from deck
        drawn = self.deck[:n]
        self.deck = self.deck[n:]
        return drawn

    def start_round(self):
        #begin a new round
        self.round += 1
        self._build_deck()
        self.bet = self._min_bet()
        self.player_hand = self._draw_cards(5)
        self.luigi_hand = self._draw_cards(5)
        self.result = None

    def _min_bet(self) -> int:
        #bet increases every 5 stars up to 4
        return min(1 + self.stars // 5, 4)

    def increase_bet(self, amount: int):
        #raise bet if player has enough coins
        if self.coins >= self.bet + amount:
            self.bet += amount

    def player_discard(self, indices: list[int]):
        #discard cards at given indices and replace them
        if not indices:
            return
        for i in indices:
            if 0 <= i < len(self.player_hand):
                self.player_hand[i] = self._draw_cards(1)[0]

    def luigi_discard(self):
        #very simple dealer: keep the most common symbols, discard others
        counts = Counter(self.luigi_hand)
        keep = set([sym for sym, cnt in counts.items() if cnt > 1])
        new_hand = []
        for card in self.luigi_hand:
            if card in keep:
                new_hand.append(card)
            else:
                new_hand.append(self._draw_cards(1)[0])
        self.luigi_hand = new_hand

    def evaluate_hand(self, hand: list[str]) -> tuple[int, str]:
        #return (rank_value, rank_name) for a hand
        counts = Counter(hand).values()
        count_sorted = sorted(counts, reverse=True)

        if 5 in count_sorted:
            return self.HAND_RANKS["five_kind"], "five_kind"
        if 4 in count_sorted:
            return self.HAND_RANKS["four_kind"], "four_kind"
        if 3 in count_sorted and 2 in count_sorted:
            return self.HAND_RANKS["full_house"], "full_house"
        if 3 in count_sorted:
            return self.HAND_RANKS["three_kind"], "three_kind"
        if count_sorted.count(2) == 2:
            return self.HAND_RANKS["two_pair"], "two_pair"
        if 2 in count_sorted:
            return self.HAND_RANKS["one_pair"], "one_pair"
        return self.HAND_RANKS["junk"], "junk"

    def resolve_round(self):
        #evaluate both hands and assign coins/stars
        p_val, p_rank = self.evaluate_hand(self.player_hand)
        l_val, l_rank = self.evaluate_hand(self.luigi_hand)

        if p_val > l_val:
            #player wins
            mult = self.MULTIPLIER.get(p_rank, 0)
            winnings = self.bet * mult
            self.coins += winnings
            self.stars += 1
            self.result = {"outcome": "win", "player_rank": p_rank, "luigi_rank": l_rank, "coins": self.coins, "stars": self.stars}
        elif p_val < l_val:
            #luigi wins
            self.coins -= self.bet
            if self.stars > 0:
                self.stars -= 1
            self.result = {"outcome": "lose", "player_rank": p_rank, "luigi_rank": l_rank, "coins": self.coins, "stars": self.stars}
        else:
            #tie returns bet
            self.result = {"outcome": "tie", "player_rank": p_rank, "luigi_rank": l_rank, "coins": self.coins, "stars": self.stars}

        return self.result

    def is_over(self) -> bool:
        return self.coins <= 0

#test suite prob switch to pytest later but for now just terminal
if __name__ == "__main__":
    game = PicturePoker(starting_coins=20, starting_stars=0)

    print("=== Starting Picture Poker Test ===")
    game.start_round()
    print(f"Round {game.round}, Bet = {game.bet}")
    print("Player Hand:", game.player_hand)
    print("Luigi Hand (hidden):", ["??"] * 5)

    #simulate player discards first two cards
    game.player_discard([0, 1])
    print("Player Hand after discard:", game.player_hand)

    #simulate luigi redraw
    game.luigi_discard()

    #resolve outcome
    result = game.resolve_round()
    print("Result:", result)
    print("Game over?", game.is_over())