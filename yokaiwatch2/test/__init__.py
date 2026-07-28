"""
Test base for the Yo-kai Watch 2 world.

These tests must be run from inside an Archipelago source checkout, with
this world installed in `worlds/yokaiwatch2/`:

    python -m pytest worlds/yokaiwatch2/test
    # or the full Archipelago suite:
    python -m unittest discover test
"""

from test.bases import WorldTestBase

from ..constants import GAME_NAME


class YKW2TestBase(WorldTestBase):
    game = GAME_NAME
