# -*- coding: utf-8 -*-
"""
Options for the Yo-kai Watch 2 Archipelago world.

Every option is exposed in the player YAML. Common options (accessibility,
progression_balancing, local_items, exclude_locations, start_inventory, ...)
are inherited from PerGameCommonOptions and do not need to be redefined here.
"""

from dataclasses import dataclass

from Options import (
    Choice,
    DeathLink,
    DefaultOnToggle,
    OptionGroup,
    PerGameCommonOptions,
    Range,
    StartInventoryPool,
    Toggle,
)

from .constants import DISTRICTS


# ---------------------------------------------------------------------------
# Général
# ---------------------------------------------------------------------------
class Goal(Choice):
    """The victory condition of your run.

    final_boss:       defeat Lady Démona at the end of the story.
    story_100:        complete all 11 story chapters.
    infinite_inferno: defeat Potofeu in the Limbes éternelles.
    divine_paradise:  defeat Filomène in the Paradis divin.
    all_legendaries:  collect every Médaille légendaire.
    all_checks:       full clear - story, both postgame dungeons and all
                      legendary medals (approximates 100% completion).
    """
    display_name = "Goal"
    option_final_boss = 0
    option_story_100 = 1
    option_infinite_inferno = 2
    option_divine_paradise = 3
    option_all_legendaries = 4
    option_all_checks = 5
    default = 0


class LogicDifficulty(Choice):
    """How much combat preparation the logic expects.

    casual:  the logic expects one watch rank above normal for every fight.
    normal:  balanced expectations.
    hard:    fights are expected one rank earlier than normal.
    expert:  fights are expected two ranks earlier - for players comfortable
             with severely underleveled boss fights.
    """
    display_name = "Logic Difficulty"
    option_casual = 0
    option_normal = 1
    option_hard = 2
    option_expert = 3
    default = 1


class StartingRegion(Choice):
    """The Granval district you can access from the very start.

    You receive the matching Passe de quartier, opening that district before
    its normal story gate. Les Hauts de Granval is the vanilla start and is
    always reachable.
    """
    display_name = "Starting Region"
    option_hauts_de_granval = 0
    option_quartier_des_boutiques = 1
    option_centre_ville = 2
    option_coteau_fleuri = 3
    option_la_corniche = 4
    default = 0


# Maps StartingRegion values to district names (same order as the options).
STARTING_REGION_TO_DISTRICT = {
    StartingRegion.option_hauts_de_granval: "Les Hauts de Granval",
    StartingRegion.option_quartier_des_boutiques: "Quartier des boutiques",
    StartingRegion.option_centre_ville: "Centre-ville de Granval",
    StartingRegion.option_coteau_fleuri: "Coteau fleuri",
    StartingRegion.option_la_corniche: "La Corniche",
}
assert set(STARTING_REGION_TO_DISTRICT.values()) == set(DISTRICTS)


# ---------------------------------------------------------------------------
# Pools de locations (« qu'est-ce qui est un check ? »)
# ---------------------------------------------------------------------------
class StoryShuffle(Toggle):
    """Shuffle story progression.

    When enabled, 10 'Chapitre d'histoire (progressif)' items are added to
    the pool; chapter N of the story only opens once you have received N-1
    of them. When disabled, story chapters unlock by playing the game in
    order (vanilla behavior), but chapter completions are still checks.
    """
    display_name = "Story Shuffle"


class BossShuffle(DefaultOnToggle):
    """Every boss defeated is a check."""
    display_name = "Boss Checks"


class QuestShuffle(DefaultOnToggle):
    """Every requête and service rewards a check (real quest list from the
    French guide)."""
    display_name = "Quest Checks"


class ChestShuffle(DefaultOnToggle):
    """Every treasure chest (present and past) is a check."""
    display_name = "Chest Checks"


class GroundItemShuffle(DefaultOnToggle):
    """Every ground pickup (sparkling item) is a check."""
    display_name = "Ground Item Checks"


class PlanqueShuffle(DefaultOnToggle):
    """Each of the 52 Planques Yo-kai (hidden Yo-kai spots) is a check."""
    display_name = "Planque Checks"


class TabloShuffle(DefaultOnToggle):
    """Each of the 26 Tablo-blabla riddles is a check."""
    display_name = "Tablo-blabla Checks"


class KomasanShuffle(DefaultOnToggle):
    """Each of Komasan's 9 adventure encounters is a check."""
    display_name = "Komasan Checks"


class CriminelShuffle(DefaultOnToggle):
    """Yo-criminel capture milestones (1/5/10/20/30 captures) are checks."""
    display_name = "Yo-criminel Checks"


class CollectionShuffle(Toggle):
    """Every insect (Filet à insectes) and fish (Canne à pêche) of the
    collections is a check - roughly 80 additional grindy checks."""
    display_name = "Collection Checks"


class YokaiShuffle(Choice):
    """Which befriended Yo-kai count as checks.

    none:      befriending Yo-kai is never a check.
    s_rank:    only rank S Yo-kai are checks.
    legendary: only unlocking legendary seals are checks.
    all:       every Yo-kai in the supported roster is a check.
    """
    display_name = "Yo-kai Checks"
    option_none = 0
    option_s_rank = 1
    option_legendary = 2
    option_all = 3
    default = 0


class LegendaryShuffle(Toggle):
    """Shuffle the Médailles légendaires into the item pool.

    When enabled, each legendary seal opens only once you have received its
    'Médaille légendaire' item, and the seal locations are always checks.
    When disabled, seals behave vanilla-like.
    """
    display_name = "Legendary Shuffle"


class FusionShuffle(Toggle):
    """Obtaining each objet de fusion (Épée légendaire chain, Pince de
    glace, ...) is a check."""
    display_name = "Fusion Checks"


class EvolutionShuffle(Toggle):
    """Notable evolutions are checks."""
    display_name = "Evolution Checks"


# ---------------------------------------------------------------------------
# Objets
# ---------------------------------------------------------------------------
class KeyItemShuffle(DefaultOnToggle):
    """Shuffle key items (billets, tickets, clés, outils, rangs de montre,
    vélo) into the multiworld item pool.

    When disabled, these items are placed at their vanilla-ish locations in
    your own world (or granted at the start when the matching location is
    disabled), producing a much more linear game.
    """
    display_name = "Key Item Shuffle"


class ProgressiveWatchRank(DefaultOnToggle):
    """When enabled, watch ranks are 5 'Rang de Yo-kai Watch (progressif)'
    items. When disabled, the 5 individual rank items (D, C, B, A, S) are
    shuffled and can be found in any order."""
    display_name = "Progressive Watch Rank"


class ProgressiveBicycle(Toggle):
    """When enabled, the bicycle is split into 2 'Vélo (progressif)' items
    (first unlocks riding, second upgrades it). When disabled, a single
    'Vélo' item is used."""
    display_name = "Progressive Bicycle"


class EarlyBicycle(Toggle):
    """Guarantee the bicycle appears in an early sphere of the multiworld."""
    display_name = "Early Bicycle"


class EarlyWatchUpgrade(DefaultOnToggle):
    """Guarantee a first watch rank upgrade appears in an early sphere."""
    # Défaut ON (2026-07-16) : la section OBJETS a été retirée des YAML v1
    # (les objets-clés sont TOUJOURS dans le pool) ; on préserve la garantie
    # anti-frustration du 1er rang tôt sans ligne de YAML.
    display_name = "Early Watch Upgrade"


# ---------------------------------------------------------------------------
# Pièges
# ---------------------------------------------------------------------------
class TrapPercentage(Range):
    """Percentage of filler items replaced by traps (perte d'argent,
    envoûtement, embuscade, objet factice)."""
    display_name = "Trap Percentage"
    range_start = 0
    range_end = 100
    default = 10


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------
@dataclass
class YKW2Options(PerGameCommonOptions):
    goal: Goal
    logic_difficulty: LogicDifficulty
    starting_region: StartingRegion

    story_shuffle: StoryShuffle
    boss_shuffle: BossShuffle
    quest_shuffle: QuestShuffle
    chest_shuffle: ChestShuffle
    ground_item_shuffle: GroundItemShuffle
    planque_shuffle: PlanqueShuffle
    tablo_shuffle: TabloShuffle
    komasan_shuffle: KomasanShuffle
    criminel_shuffle: CriminelShuffle
    collection_shuffle: CollectionShuffle
    yokai_shuffle: YokaiShuffle
    legendary_shuffle: LegendaryShuffle
    fusion_shuffle: FusionShuffle
    evolution_shuffle: EvolutionShuffle

    key_item_shuffle: KeyItemShuffle
    progressive_watch_rank: ProgressiveWatchRank
    progressive_bicycle: ProgressiveBicycle
    early_bicycle: EarlyBicycle
    early_watch_upgrade: EarlyWatchUpgrade

    trap_percentage: TrapPercentage
    death_link: DeathLink
    start_inventory_from_pool: StartInventoryPool


# Groupes affichés sur la page d'options du WebHost.
OPTION_GROUPS = [
    OptionGroup("General", [Goal, LogicDifficulty, StartingRegion]),
    OptionGroup("Location Pools", [
        StoryShuffle, BossShuffle, QuestShuffle, ChestShuffle,
        GroundItemShuffle, PlanqueShuffle, TabloShuffle, KomasanShuffle,
        CriminelShuffle, CollectionShuffle, YokaiShuffle, LegendaryShuffle,
        FusionShuffle, EvolutionShuffle,
    ]),
    OptionGroup("Items", [
        KeyItemShuffle, ProgressiveWatchRank, ProgressiveBicycle,
        EarlyBicycle, EarlyWatchUpgrade,
    ]),
    OptionGroup("Traps & Misc", [TrapPercentage, DeathLink]),
]

# Presets sélectionnables sur le WebHost.
OPTION_PRESETS = {
    "Vanilla-ish": {
        "goal": "final_boss",
        "logic_difficulty": "normal",
        "story_shuffle": False,
        "key_item_shuffle": False,
        "yokai_shuffle": "none",
        "collection_shuffle": False,
        "trap_percentage": 0,
    },
    "Chaos": {
        "goal": "all_checks",
        "logic_difficulty": "hard",
        "story_shuffle": True,
        "legendary_shuffle": True,
        "yokai_shuffle": "all",
        "fusion_shuffle": True,
        "evolution_shuffle": True,
        "collection_shuffle": True,
        "trap_percentage": 25,
    },
}
