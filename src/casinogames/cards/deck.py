###########################################################
# File: deck.py
#
# Description: structure for defining decks
#
###########################################################

from copy import copy
from random import shuffle

# Discord displays (just incase)
HEART = ':heart_suit:'   # ♥
DIAMOND = ':diamond_suit:'   # ♦
CLUB = ':club_suit:'     # ♣
SPADE = ':spade_suit:'   # ♠

# Values
ACE = 'A'
JACK = 'J'
QUEEN = 'Q'
KING = 'K'
JOKER = ':joker:'

# Colors
RED = ':red_circle:'
BLACK = ':black_large_square:'

# Standard deck setup
VALUES = [ACE, '2', '3', '4', '5', '6', '7', '8', '9', '10', JACK, QUEEN, KING]
SUITS = [HEART, DIAMOND, CLUB, SPADE]

RED_SUITS = [HEART, DIAMOND]
BLACK_SUITS = [CLUB, SPADE]


class Card:
    def __init__(self, value, suit):
        self.value = value
        self.suit = suit
    
    def to_int_runs(self):
        if self.value == ACE :
            return 1
        elif self.value == JACK:
            return 11
        elif self.value == QUEEN:
            return 12
        elif self.value == KING:
            return 13
        elif self.value == JOKER:
            return -1
        else:
            return int(self.value)
        
    def to_int_15s(self):
        if self.value == ACE:
            return 1
        elif self.value in [JACK, QUEEN, KING]:
            return 10
        elif self.value == JOKER:
            return -1
        else:
            return int(self.value)
        
    def display(self):
        return f'{self.value} {self.suit}'


class Deck:
    def __init__(self):
        self.reset_deck()
        
    def reset_deck(self):
        # Initialize a full shuffled deck
        self.deck: list[Card] = [Card(value, suit) for suit in SUITS for value in VALUES]
        shuffle(self.deck)

    def get_hands(self, num_hands: int, num_cards: int) -> list[list[Card]]:
        # Deal num_hands of num_cards
        hands = []
        if num_hands * num_cards <= len(self.deck):
            for _ in range(num_hands):
                hand = [self.deck.pop(0) for _ in range(num_cards)]
                hands.append(hand)
        return hands
    
    def get_card(self) -> Card | None:
        # Draw a single card from the top of the deck
        if not self.is_empty():
            return self.deck.pop(0)
        return None
    
    def get_length(self) -> int:
        return len(self.deck)
    
    def is_empty(self) -> bool:
        return len(self.deck) == 0
        
    def get_deck(self) -> list[Card]:
        #Return a shallow copy of the current deck
        return copy(self.deck)
    
    def set_deck(self, cards: list[Card]):
        #Replace the current deck with a copy of another card list
        self.deck = copy(cards)

    