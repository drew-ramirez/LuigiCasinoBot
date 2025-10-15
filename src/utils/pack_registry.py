from dataclasses import dataclass
from typing import Dict, Set

@dataclass(frozen=True)
class Pack:
    id: str
    name: str
    description: str

# Two top-level packs
REGISTRY: Dict[str, Pack] = {
    "luigi":  Pack("luigi",  "Luigi’s Casino Pack",
                   "Picture Poker, Pair-a-Gone, Memory Match, Lucky Stars."),
    "extras": Pack("extras", "Casino Extras",
                   "Blackjack, Standard Poker, and future table games.")
}

# Ship with Luigi’s pack enabled by default
DEFAULT_ENABLED: Set[str] = {"luigi"}
ALL_PACK_IDS = tuple(REGISTRY.keys())
