"""
Game-side patching scaffold for Yo-kai Watch 2: Psychic Specters.

STATUS: SCAFFOLD - multiworld generation works without this module; it only
matters once the community wires the world to the actual game.

Why a scaffold?
    Unlike GBA/SNES games, 3DS games are not distributed as a single ROM that
    Archipelago can bsdiff-patch: the game is a CIA/3DS title whose RomFS
    must be dumped (GodMode9 on console, or extracted from a legally dumped
    cart) and modified through Luma3DS LayeredFS (console) or Citra/Azahar
    mods (emulator).  The recommended integration for this world is therefore
    a *client-driven* one (see client.py): the game stays untouched and the
    client reads/writes game memory through the emulator's GDB stub.

What this module provides today:
    * The reference structures a future patch-based integration would use
      (title IDs, RomFS file list, flag layout documentation).
    * A helper that writes a "mod folder" skeleton usable with LayeredFS.

Reverse-engineering TODOs for the community (append findings here):
    * TITLE_ID_EU / TITLE_ID_US            (constants.py)
    * RAM address of the chest-flag bitfield
    * RAM address of the quest-completion table
    * RAM address of the befriended-Yo-kai medallium bits
    * RAM address of money / inventory for traps and received items
"""

import json
import os
from typing import Dict

from .constants import GAME_NAME, TITLE_ID_EU, TITLE_ID_US

# RomFS files a LayeredFS-based integration would likely touch.
# TODO(community): verify against an actual RomFS dump.
ROMFS_FILES_OF_INTEREST = [
    "data/res/character/",   # character/yo-kai parameters
    "data/res/battle/",      # encounter tables
    "data/res/map/",         # chest placements
    "data/res/text/",        # item/dialog text (for shuffled item names)
]


def write_layeredfs_skeleton(output_dir: str,
                             slot_data: Dict[str, object]) -> str:
    """Write a Luma3DS LayeredFS mod skeleton for a generated seed.

    Creates ``luma/titles/<TITLE_ID>/romfs/`` plus an ``apseed.json`` file
    holding the seed's slot data, which a future game-side mod (or the
    client) can consume.  Returns the path of the created mod folder.
    """
    title_id = TITLE_ID_EU if TITLE_ID_EU != "TODO" else "0004000000000000"
    mod_root = os.path.join(output_dir, "luma", "titles", title_id)
    romfs = os.path.join(mod_root, "romfs")
    os.makedirs(romfs, exist_ok=True)
    with open(os.path.join(mod_root, "apseed.json"), "w", encoding="utf-8") as f:
        json.dump({"game": GAME_NAME, "slot_data": slot_data}, f, indent=2)
    return mod_root


__all__ = [
    "GAME_NAME",
    "ROMFS_FILES_OF_INTEREST",
    "TITLE_ID_EU",
    "TITLE_ID_US",
    "write_layeredfs_skeleton",
]
