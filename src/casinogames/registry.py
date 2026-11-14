"""Stable game identities shared by commands, visibility and practice tables."""
from dataclasses import dataclass
from importlib import import_module
from types import MappingProxyType


@dataclass(frozen=True)
class Game:
    title: str
    practice: bool = False
    engine_name: str | None = None

    @property
    def command_label(self):
        return self.title + (' (practice)' if self.practice else '')


GAMES = MappingProxyType({
    'memorymatch': Game('Memory Match'),
    'pairagone': Game('Pair-a-Gone'),
    'luckystars': Game('Lucky Stars'),
    'picturepoker': Game('Picture Poker'),
    'roulette': Game('Mushroom Roulette'),
    'slots': Game('Super Mario Slot'),
    'memory_master': Game('Memory Master'),
    'pairagone_endless': Game('Pair-a-Gone and On'),
    'blackjack': Game('Blackjack'),
    'fortune_tower': Game('Fortune Tower', True),
    'thrilling_cards': Game('Thrilling Cards', True),
    'triple_triad': Game('Triple Triad', True, 'TripleTriad'),
    'red7': Game('Red7', True, 'Red7'),
    'scopa': Game('Scopa', True, 'Scopa'),
    'cuttle': Game('Cuttle', True, 'Cuttle'),
    'platoon': Game('Platoon', True, 'Platoon'),
    'pazaak': Game('Pazaak', True, 'Pazaak'),
    'casino_war': Game('Casino War', True, 'CasinoWar'),
})
DUEL_GAMES = MappingProxyType({key: game for key, game in GAMES.items() if game.engine_name})


def duel_engines():
    return {key: getattr(import_module(f'casinogames.{key}'), game.engine_name)
            for key, game in DUEL_GAMES.items()}
