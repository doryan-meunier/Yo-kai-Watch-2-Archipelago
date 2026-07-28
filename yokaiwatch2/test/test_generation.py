"""
Smoke tests: every meaningful option combination must generate and fill.

WorldTestBase automatically runs its standard battery (fill completes,
all-state reaches everything, empty state reaches something) for each
subclass below.
"""

from . import YKW2TestBase


class TestDefaultOptions(YKW2TestBase):
    options = {}


class TestStoryShuffle(YKW2TestBase):
    options = {"story_shuffle": True}


class TestVanillaKeyItems(YKW2TestBase):
    options = {"key_item_shuffle": False}


class TestIndividualRanksAndProgressiveBicycle(YKW2TestBase):
    options = {
        "progressive_watch_rank": False,
        "progressive_bicycle": True,
    }


class TestMinimalLocations(YKW2TestBase):
    """Disabling every optional pool must trigger the safety fallback that
    re-enables chests instead of failing generation."""
    options = {
        "boss_shuffle": False,
        "quest_shuffle": False,
        "chest_shuffle": False,
        "ground_item_shuffle": False,
        "planque_shuffle": False,
        "tablo_shuffle": False,
        "komasan_shuffle": False,
        "criminel_shuffle": False,
        "yokai_shuffle": "none",
    }


class TestEverythingEnabled(YKW2TestBase):
    options = {
        "goal": "all_checks",
        "logic_difficulty": "hard",
        "story_shuffle": True,
        "yokai_shuffle": "all",
        "legendary_shuffle": True,
        "fusion_shuffle": True,
        "evolution_shuffle": True,
        "collection_shuffle": True,
        "trap_percentage": 50,
    }


class TestGoalStory100(YKW2TestBase):
    options = {"goal": "story_100"}


class TestGoalInfiniteInferno(YKW2TestBase):
    options = {"goal": "infinite_inferno"}


class TestGoalDivineParadise(YKW2TestBase):
    options = {"goal": "divine_paradise"}


class TestGoalAllLegendaries(YKW2TestBase):
    """Without legendary_shuffle the medals must be locked vanilla-style."""
    options = {"goal": "all_legendaries"}


class TestGoalAllLegendariesShuffled(YKW2TestBase):
    options = {"goal": "all_legendaries", "legendary_shuffle": True}


class TestStartingRegionCorniche(YKW2TestBase):
    options = {"starting_region": "la_corniche", "logic_difficulty": "expert"}


class TestCasualWithEarlyItems(YKW2TestBase):
    options = {
        "logic_difficulty": "casual",
        "early_bicycle": True,
        "early_watch_upgrade": True,
    }
