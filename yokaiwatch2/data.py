"""
Shared datatypes for the Yo-kai Watch 2 Archipelago world.

Only *types* live here (dataclasses and enums used by the data tables).
The actual data tables live in items.py, locations.py and regions.py so that
each list can be extended independently.
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional, Tuple

from BaseClasses import ItemClassification


class LocationCategory(Enum):
    """Category of a location; used to enable/disable groups via options."""
    STORY = auto()        # story chapter completion
    WATCH_RANK = auto()   # watch rank quests ("Obtenons le rang X !")
    BOSS = auto()         # boss defeats
    QUEST = auto()        # requêtes and services
    CHEST = auto()        # treasure chests
    GROUND = auto()       # ground pickups (sparkles)
    YOKAI = auto()        # befriending a Yo-kai
    LEGENDARY = auto()    # unlocking a legendary seal
    FUSION = auto()       # obtaining a fusion item ("objet de fusion")
    EVOLUTION = auto()    # witnessing a notable evolution
    PLANQUE = auto()      # Yo-kai hideouts ("planques")
    TABLO = auto()        # Tablo-blabla riddles
    KOMASAN = auto()      # Komasan's adventures encounters
    CRIMINEL = auto()     # Yo-criminel capture milestones
    INSECTE = auto()      # insect collection (needs Filet à insectes)
    POISSON = auto()      # fish collection (needs Canne à pêche)
    NATIVE_KEY = auto()   # spot natif d'un objet-clé (shuffle dur) : check filler
    EVENT = auto()        # événement d'histoire détecté par FLAG mémoire


@dataclass(frozen=True)
class AccessReq:
    """
    Declarative access requirement, shared by locations and entrances.

    min_chapter:  number of completed story chapters required (0 = none).
    combat_rank:  watch rank the logic expects for the fights involved
                  (0 = none, 1 = D ... 5 = S). Adjusted by logic difficulty.
    items:        Archipelago item names that must be collected.
    needs_bicycle: True if the bicycle is logically required.
    """
    min_chapter: int = 0
    combat_rank: int = 0
    items: Tuple[str, ...] = ()
    needs_bicycle: bool = False


# A requirement that is always satisfied.
FREE = AccessReq()


@dataclass(frozen=True)
class YKW2LocationData:
    """Static data for one location (check)."""
    code: Optional[int]           # Archipelago ID (None for events)
    region: str                   # region the location belongs to
    category: LocationCategory
    req: AccessReq = FREE         # requirement *on top of* the region access
    yokai_rank: str = ""          # only for YOKAI locations: "E".."S"


@dataclass(frozen=True)
class YKW2ItemData:
    """Static data for one item."""
    code: int
    classification: ItemClassification
    category: str                 # free-form group label ("key", "filler"...)
    count: int = 0                # default copies placed in the pool
                                  # (0 = only placed via special handling,
                                  #  e.g. weighted filler or option-dependent)


@dataclass(frozen=True)
class ConnectionData:
    """Static data for one entrance between two regions."""
    name: str                     # unique entrance name
    source: str
    target: str
    req: AccessReq = FREE
    bidirectional: bool = False   # also create target -> source


@dataclass(frozen=True)
class YokaiData:
    """Static data for one befriendable Yo-kai."""
    name: str
    rank: str                     # "E".."S"
    region: str
    min_chapter: int = 0
