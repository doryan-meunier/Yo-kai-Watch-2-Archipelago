"""
Archipelago world for Yo-kai Watch 2: Psychic Specters (Nintendo 3DS).

Module layout:
    constants.py  - shared constants (IDs, ranks, chapters, districts)
    data.py       - shared dataclasses / enums
    items.py      - item tables
    locations.py  - location tables (several hundred checks)
    regions.py    - region graph and option-driven location selection
    rules.py      - access rules, logic difficulty, completion conditions
    options.py    - player YAML options
    rom.py        - game-side patching scaffold (community RE required)
    client.py     - Archipelago client scaffold (Citra/Azahar GDB bridge)
    test/         - unit tests (run inside the Archipelago repository)
"""

import logging
from typing import Any, Dict, List

from BaseClasses import Tutorial
from worlds.AutoWorld import WebWorld, World
from worlds.LauncherComponents import (
    Component,
    Type as ComponentType,
    components,
    launch_subprocess,
)

from .constants import (
    CHAPTER_COUNT,
    GAME_NAME,
    LEGENDARY_YOKAI,
    PROGRESSIVE_CHAPTER_ITEM,
    PROGRESSIVE_RANK_ITEM,
    RANK_ITEM_NAMES,
    district_pass_name,
    legendary_medal_name,
)
from .items import (
    ALL_ITEMS,
    NATIVE_CHEST_ITEM_BY_LOCATION,
    COIN_POOL,
    COMBAT_YOKAI_POOL,
    FILLER_WEIGHTS,
    ITEM_GROUPS,
    ITEM_NAME_TO_ID,
    SHUFFLABLE_KEY_ITEMS,
    TRAP_WEIGHTS,
    VANILLA_BICYCLE_PLACEMENT,
    VANILLA_KEY_PLACEMENTS,
    VANILLA_RANK_PLACEMENTS,
    YKW2Item,
)
from .locations import LOCATION_GROUPS, LOCATION_NAME_TO_ID
from .options import (
    Goal,
    OPTION_GROUPS,
    OPTION_PRESETS,
    STARTING_REGION_TO_DISTRICT,
    YKW2Options,
)
from .regions import create_ykw2_regions, get_active_location_data
from .rules import set_ykw2_rules

APWORLD_VERSION = "0.1.0"

logger = logging.getLogger("YoKaiWatch2")


# ---------------------------------------------------------------------------
# Launcher component (text client / memory bridge, see client.py)
# ---------------------------------------------------------------------------
def _launch_client() -> None:
    from .client import launch
    launch_subprocess(launch, name="YoKaiWatch2Client")


components.append(Component(
    "Yo-kai Watch 2 Client", func=_launch_client,
    component_type=ComponentType.CLIENT))


class YKW2Web(WebWorld):
    theme = "partyTime"
    game_info_languages = ["en", "fr"]
    option_groups = OPTION_GROUPS
    options_presets = OPTION_PRESETS
    tutorials = [
        Tutorial(
            "Multiworld Setup Guide",
            "A guide to setting up Yo-kai Watch 2 for Archipelago multiworlds.",
            "English", "setup_en.md", "setup/en", ["Doteos"],
        ),
        Tutorial(
            "Guide d'installation Multiworld",
            "Un guide pour installer et jouer à Yo-kai Watch 2 avec Archipelago.",
            "Français", "setup_fr.md", "setup/fr", ["Doteos"],
        ),
    ]


class YKW2World(World):
    """Yo-kai Watch 2 is a monster-collecting RPG set in Granval (Springdale),
    where Nathan travels between the present and 60 years in the past to stop
    the wicked Yo-kai and Lady Démona.  Find chests, clear requêtes, defeat
    bosses and befriend Yo-kai to send items across the multiworld."""

    game = GAME_NAME
    web = YKW2Web()
    options_dataclass = YKW2Options
    options: YKW2Options
    topology_present = True
    required_client_version = (0, 5, 0)

    item_name_to_id = ITEM_NAME_TO_ID
    location_name_to_id = LOCATION_NAME_TO_ID
    item_name_groups = ITEM_GROUPS
    location_name_groups = LOCATION_GROUPS

    def __init__(self, multiworld, player: int):
        super().__init__(multiworld, player)
        self.active_location_data: Dict[str, Any] = {}
        self.event_reqs: Dict[str, Any] = {}
        self.force_chests = False
        self.force_ground = False
        self.medals_exist = False

    # ------------------------------------------------------------------
    # Item helpers
    # ------------------------------------------------------------------
    def create_item(self, name: str) -> YKW2Item:
        data = ALL_ITEMS[name]
        return YKW2Item(name, data.classification, data.code, self.player)

    def get_filler_item_name(self) -> str:
        names, weights = zip(*FILLER_WEIGHTS)
        return self.random.choices(names, weights=weights, k=1)[0]

    def _bicycle_item_name(self) -> str:
        return "Vélo (progressif)" if self.options.progressive_bicycle \
            else "Vélo"

    def _rank_item_name(self, rank: int) -> str:
        return PROGRESSIVE_RANK_ITEM if self.options.progressive_watch_rank \
            else RANK_ITEM_NAMES[rank]

    def _progression_pool_names(self) -> List[str]:
        """Progression items that go into the multiworld pool."""
        opts = self.options
        names: List[str] = []
        if opts.key_item_shuffle:
            if opts.progressive_bicycle:
                names += ["Vélo (progressif)"] * 2
            else:
                names.append("Vélo")
            names += [self._rank_item_name(rank) for rank in range(1, 6)]
            names += SHUFFLABLE_KEY_ITEMS
        if opts.story_shuffle:
            names += [PROGRESSIVE_CHAPTER_ITEM] * (CHAPTER_COUNT - 1)
        if opts.legendary_shuffle:
            names += [legendary_medal_name(y) for y in LEGENDARY_YOKAI]
        return names

    def _locked_item_estimate(self) -> int:
        """Locations consumed by locked (vanilla) placements."""
        locked = 0
        if not self.options.key_item_shuffle:
            locked += 1 + 5 + len(SHUFFLABLE_KEY_ITEMS)  # bike + ranks + keys
        if not self.options.legendary_shuffle \
                and self.options.goal.value == Goal.option_all_legendaries:
            locked += len(LEGENDARY_YOKAI)
        return locked

    # ------------------------------------------------------------------
    # Generation steps
    # ------------------------------------------------------------------
    def generate_early(self) -> None:
        opts = self.options

        # Make sure the pool fits into the enabled locations; re-enable
        # location categories if the player disabled too many of them.
        needed = len(self._progression_pool_names()) + self._locked_item_estimate()
        for flag in ("force_chests", "force_ground"):
            if len(get_active_location_data(self)) > needed:
                break
            setattr(self, flag, True)
            logger.warning(
                "Yo-kai Watch 2 (%s): not enough locations for the item pool; "
                "re-enabling %s.", self.player_name,
                "chests" if flag == "force_chests" else "ground items")
        if len(get_active_location_data(self)) <= needed:
            raise ValueError(
                f"Yo-kai Watch 2 ({self.player_name}): option combination "
                "leaves too few locations for the item pool.")

        # Starting district (vanilla start is Les Hauts de Granval).
        district = STARTING_REGION_TO_DISTRICT[opts.starting_region.value]
        if district != "Les Hauts de Granval":
            self.multiworld.push_precollected(
                self.create_item(district_pass_name(district)))

        # Early item hints to the filler algorithm.
        if opts.key_item_shuffle:
            if opts.early_bicycle:
                self.multiworld.early_items[self.player][self._bicycle_item_name()] = 1
            if opts.early_watch_upgrade:
                self.multiworld.early_items[self.player][self._rank_item_name(1)] = 1

    def create_regions(self) -> None:
        create_ykw2_regions(self)

    def create_items(self) -> None:
        opts = self.options
        pool: List[YKW2Item] = [
            self.create_item(name) for name in self._progression_pool_names()]

        # POOL v1 (Doteos 2026-07-15) : 1 de chaque objet-clé de COMBAT Yo-kai
        # (graines/grelots/rouages/Marque) + 1 de chaque PIÈCE YKW2, GARANTIS dans
        # le pool (avant le filler). Uniquement les items accessibles pendant
        # l'histoire (les post-game — Glu spectrale, Orbe Noko — ont count 0 donc
        # n'entrent pas). Le reste des locations sera rempli par des consommables.
        pool += [self.create_item(name) for name in COMBAT_YOKAI_POOL]
        pool += [self.create_item(name) for name in COIN_POOL]

        # ANTI-SOFT-LOCK DU FILET (Doteos 2026-07-21) : le Filet est requis DÈS le
        # tuto du tout début (rules.py : « prologue » -> tout le requiert) -> SPHÈRE 0.
        # HYBRIDE selon le nombre de joueurs :
        #  * SOLO : son seul spot sphère 0 = son check natif -> on l'y VERROUILLE
        #    (early_items échoue parfois car spot unique -> FillError).
        #  * MULTI : d'autres checks précoces existent (autres joueurs) -> `early_items`
        #    (pré-fill AP) pour qu'il PUISSE aller chez un autre joueur (spec Doteos).
        if opts.key_item_shuffle:
            if self.multiworld.players == 1:
                pool = [it for it in pool if it.name != "Filet à insectes"]
                self._place_vanilla_or_precollect(
                    "Filet à insectes", "Objet-clé : Filet à insectes")
            else:
                self.multiworld.early_items[self.player]["Filet à insectes"] = 1

        # Vanilla-ish placements when key items are not shuffled.
        if not opts.key_item_shuffle:
            self._place_vanilla_or_precollect(
                self._bicycle_item_name(), VANILLA_BICYCLE_PLACEMENT)
            for rank, location in VANILLA_RANK_PLACEMENTS.items():
                self._place_vanilla_or_precollect(
                    self._rank_item_name(rank), location)
            for item_name in SHUFFLABLE_KEY_ITEMS:
                # Les objets importants sans placement vanilla connu sont donnés
                # au départ (précollecte) via location_name=None.
                self._place_vanilla_or_precollect(
                    item_name, VANILLA_KEY_PLACEMENTS.get(item_name))

        # Legendary medals outside the pool: lock them at their seals when
        # the goal needs them (vanilla-like behavior).
        if opts.legendary_shuffle:
            self.medals_exist = True
        elif opts.goal.value == Goal.option_all_legendaries:
            for yokai in LEGENDARY_YOKAI:
                self._place_vanilla_or_precollect(
                    legendary_medal_name(yokai), f"Sceau légendaire : {yokai}")
            self.medals_exist = True

        space = len(self.multiworld.get_unfilled_locations(self.player)) - len(pool)
        if space < 0:
            raise ValueError(
                f"Yo-kai Watch 2 ({self.player_name}): item pool larger than "
                "the available locations - please report this seed.")

        # Useful items, as long as there is room.
        useful_names: List[str] = []
        if opts.key_item_shuffle and not opts.progressive_bicycle:
            useful_names.append("Sonnette de vélo")
        for name, data in ALL_ITEMS.items():
            if data.category == "useful":
                useful_names += [name] * data.count
        for name in useful_names[:space]:
            pool.append(self.create_item(name))
        space -= min(space, len(useful_names))

        # Traps + weighted filler for the rest.
        trap_count = space * opts.trap_percentage.value // 100
        if trap_count:
            trap_names, trap_weights = zip(*TRAP_WEIGHTS)
            pool += [self.create_item(name) for name in self.random.choices(
                trap_names, weights=trap_weights, k=trap_count)]
        # Filler = VRAIS contenus natifs des coffres actifs (Doteos 2026-07-19).
        # Les coffres sans item natif connu (noms patchés par le mod) + le
        # complément quand il manque des items -> filler aléatoire.
        filler_needed = space - trap_count
        native = [NATIVE_CHEST_ITEM_BY_LOCATION[loc]
                  for loc in self.active_location_data
                  if loc in NATIVE_CHEST_ITEM_BY_LOCATION]
        self.random.shuffle(native)
        native = native[:filler_needed]
        pool += [self.create_item(n) for n in native]
        pool += [self.create_item(self.get_filler_item_name())
                 for _ in range(filler_needed - len(native))]

        self.multiworld.itempool += pool

    def _place_vanilla_or_precollect(self, item_name: str,
                                     location_name: str) -> None:
        """Lock an item at its vanilla location, or grant it at the start if
        that location is not part of this seed."""
        item = self.create_item(item_name)
        if location_name in self.active_location_data:
            location = self.multiworld.get_location(location_name, self.player)
            if not location.item:
                location.place_locked_item(item)
                return
        self.multiworld.push_precollected(item)

    def set_rules(self) -> None:
        set_ykw2_rules(self)

    # ------------------------------------------------------------------
    # Slot data (sent to the client)
    # ------------------------------------------------------------------
    def fill_slot_data(self) -> Dict[str, Any]:
        slot_data = self.options.as_dict(
            "goal", "logic_difficulty", "starting_region", "story_shuffle",
            "boss_shuffle", "quest_shuffle", "chest_shuffle",
            "ground_item_shuffle", "planque_shuffle", "tablo_shuffle",
            "komasan_shuffle", "criminel_shuffle", "collection_shuffle",
            "yokai_shuffle", "legendary_shuffle", "fusion_shuffle",
            "evolution_shuffle", "key_item_shuffle",
            "progressive_watch_rank", "progressive_bicycle",
            "trap_percentage", "death_link",
        )
        slot_data["apworld_version"] = APWORLD_VERSION
        slot_data["medals_exist"] = self.medals_exist
        return slot_data
