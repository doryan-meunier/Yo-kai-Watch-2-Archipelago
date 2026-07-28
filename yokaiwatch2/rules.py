"""
Access rules for the Yo-kai Watch 2 Archipelago world.

Everything is driven by the declarative AccessReq attached to locations,
events and entrances, translated here into CollectionState checks.

Softlock safety ("No Softlock" logic):
  * Region access only ever depends on items, story chapters and watch
    ranks - all of which are monotonic (they can never be lost), so no
    reachable state can become unreachable.
  * Story chapters form a strictly increasing chain (events or progressive
    items), preventing out-of-order chapter deadlocks.
  * The trap items never remove progression (money/status only).
"""

from typing import Callable, Dict, Iterable, List, Tuple

from BaseClasses import CollectionState

from .constants import (
    BICYCLE_DISTRICT,
    CHAPTER_COUNT,
    DISTRICT_CHAPTERS,
    FINAL_BOSS_EVENT,
    INFERNO_BOSS_EVENT,
    LEGENDARY_YOKAI,
    MAX_WATCH_RANK,
    PARADISE_BOSS_EVENT,
    PROGRESSIVE_CHAPTER_ITEM,
    PROGRESSIVE_RANK_ITEM,
    RANK_ITEM_NAMES,
    chapter_event_name,
    district_pass_name,
    legendary_medal_name,
)
from .data import AccessReq, LocationCategory
from .items import CRITICAL_KEY_ITEMS_BY_CHAPTER
from .locations import legendary_yokai_of
from .options import Goal, LogicDifficulty
from .regions import CONNECTIONS

# Watch rank margin added by the logic difficulty option.
_DIFFICULTY_ADJUST = {
    LogicDifficulty.option_casual: +1,
    LogicDifficulty.option_normal: 0,
    LogicDifficulty.option_hard: -1,
    LogicDifficulty.option_expert: -2,
}


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------
def has_bicycle(state: CollectionState, world) -> bool:
    if world.options.progressive_bicycle:
        return state.has("Vélo (progressif)", world.player)
    return state.has("Vélo", world.player)


def has_rank(state: CollectionState, world, rank: int) -> bool:
    """rank: 1=D .. 5=S. Individual rank items of a higher tier also count."""
    if rank <= 0:
        return True
    if world.options.progressive_watch_rank:
        return state.has(PROGRESSIVE_RANK_ITEM, world.player, rank)
    return state.has_any(
        {RANK_ITEM_NAMES[r] for r in range(rank, MAX_WATCH_RANK + 1)},
        world.player)


def has_chapter(state: CollectionState, world, chapter: int) -> bool:
    """True when `chapter` story chapters have been completed/unlocked.

    Anti-soft-lock : quand key_item_shuffle est actif (les objets d'histoire sont
    retirés en natif et livrés seulement par AP), franchir le chapitre N exige les
    objets-clés CRITIQUES de tous les chapitres <= N (CRITICAL_KEY_ITEMS_BY_
    CHAPTER). Le fill AP garantit ainsi qu'ils sont atteignables AVANT ce point."""
    if chapter <= 0:
        return True
    if world.options.story_shuffle:
        if not state.has(PROGRESSIVE_CHAPTER_ITEM, world.player, chapter):
            return False
    elif not state.has(chapter_event_name(chapter), world.player):
        return False
    if world.options.key_item_shuffle:
        for _ch, _items in CRITICAL_KEY_ITEMS_BY_CHAPTER.items():
            if _ch <= chapter and not state.has_all(_items, world.player):
                return False
    return True


def required_rank(world, combat_rank: int) -> int:
    """Combat rank adjusted by the logic difficulty, clamped to [0, S]."""
    if combat_rank <= 0:
        return 0
    adjusted = combat_rank + _DIFFICULTY_ADJUST[world.options.logic_difficulty.value]
    return max(0, min(MAX_WATCH_RANK, adjusted))


# ---------------------------------------------------------------------------
# Rule factories
# ---------------------------------------------------------------------------
def make_req_rule(world, req: AccessReq,
                  extra_items: Iterable[str] = ()) -> Callable[[CollectionState], bool]:
    """Build an access rule from a declarative requirement."""
    rank = required_rank(world, req.combat_rank)
    items = tuple(req.items) + tuple(extra_items)
    min_chapter = req.min_chapter
    needs_bicycle = req.needs_bicycle
    player = world.player

    def rule(state: CollectionState) -> bool:
        if min_chapter and not has_chapter(state, world, min_chapter):
            return False
        if rank and not has_rank(state, world, rank):
            return False
        if items and not state.has_all(items, player):
            return False
        if needs_bicycle and not has_bicycle(state, world):
            return False
        return True

    return rule


#: Quartiers/zones débloqués par la « Pile ou passe » au chapitre 2 (Doteos
#: 2026-07-17 : La Corniche + égouts + ruelle ; les AUTRES quartiers restent
#: accessibles sans la pile). Les zones de coffres (Égouts, Allée sinistre)
#: sont gérées via CHEST_ZONE_ACCESS ; ici seule La Corniche est un district.
PILE_GATED_DISTRICTS = frozenset({"La Corniche"})

#: Quartiers gatés par un OBJET-CLÉ hard-gate (RE 2026-07-21) : le client bloque
#: l'accès réel en jeu tant que l'objet AP n'est pas reçu -> il FAUT le refléter
#: dans la logique, sinon le fill place des objets requis plus tôt derrière ce
#: quartier (soft-lock). « Indications de Maman » débloque le Centre-ville (et
#: donc, en cascade, le train -> Ourcival / San Fantastico / Tour Excellence).
DISTRICT_REQUIRED_ITEMS: Dict[str, Tuple[str, ...]] = {
    "Centre-ville de Granval": ("Indications de Maman",),
}


def make_district_rule(world, district: str) -> Callable[[CollectionState], bool]:
    """Quartier de Granval : Passe de quartier (starting_region) OU seuil
    d'histoire. La Corniche attend en plus le vélo sur sa route vanilla, et
    la « Pile ou passe » (elle s'ouvre au chapitre 2 — réalité Doteos). Certains
    quartiers exigent en plus un objet-clé hard-gate (DISTRICT_REQUIRED_ITEMS)."""
    gate = DISTRICT_CHAPTERS[district]
    pass_name = district_pass_name(district)
    needs_bicycle = district == BICYCLE_DISTRICT
    needs_pile = (district in PILE_GATED_DISTRICTS
                  and world.options.key_item_shuffle)
    req_items = (DISTRICT_REQUIRED_ITEMS.get(district, ())
                 if world.options.key_item_shuffle else ())

    def rule(state: CollectionState) -> bool:
        if state.has(pass_name, world.player):
            return True
        if gate and not has_chapter(state, world, gate):
            return False
        if needs_pile and not state.has("Pile ou passe", world.player):
            return False
        if needs_bicycle and not has_bicycle(state, world):
            return False
        for _it in req_items:
            if not state.has(_it, world.player):
                return False
        return True

    return rule


# ---------------------------------------------------------------------------
# Completion conditions
# ---------------------------------------------------------------------------
def _story_completed(world) -> Callable[[CollectionState], bool]:
    if world.options.story_shuffle:
        # All chapters unlocked and the final boss beaten.
        return lambda state: (
            state.has(PROGRESSIVE_CHAPTER_ITEM, world.player, CHAPTER_COUNT - 1)
            and state.has(FINAL_BOSS_EVENT, world.player))
    return lambda state: state.has(chapter_event_name(CHAPTER_COUNT), world.player)


def _all_medals(world) -> Callable[[CollectionState], bool]:
    medals = tuple(legendary_medal_name(y) for y in LEGENDARY_YOKAI)
    return lambda state: state.has_all(medals, world.player)


def make_completion_condition(world) -> Callable[[CollectionState], bool]:
    goal = world.options.goal.value
    player = world.player

    if goal == Goal.option_final_boss:
        return lambda state: state.has(FINAL_BOSS_EVENT, player)
    if goal == Goal.option_story_100:
        return _story_completed(world)
    if goal == Goal.option_infinite_inferno:
        return lambda state: state.has(INFERNO_BOSS_EVENT, player)
    if goal == Goal.option_divine_paradise:
        return lambda state: state.has(PARADISE_BOSS_EVENT, player)
    if goal == Goal.option_all_legendaries:
        return _all_medals(world)

    # all_checks: full clear - story, both postgame bosses, max rank and,
    # when they exist in this seed, all legendary medals.
    parts: List[Callable[[CollectionState], bool]] = [
        _story_completed(world),
        lambda state: state.has_all(
            (INFERNO_BOSS_EVENT, PARADISE_BOSS_EVENT), player),
        lambda state: has_rank(state, world, MAX_WATCH_RANK),
    ]
    if getattr(world, "medals_exist", False):
        parts.append(_all_medals(world))
    return lambda state: all(part(state) for part in parts)


# ---------------------------------------------------------------------------
# Rule application
# ---------------------------------------------------------------------------
def set_ykw2_rules(world) -> None:
    multiworld, player = world.multiworld, world.player

    # Entrances.
    for connection in CONNECTIONS:
        entrance = multiworld.get_entrance(connection.name, player)
        if connection.source == "Menu" and connection.target in DISTRICT_CHAPTERS:
            entrance.access_rule = make_district_rule(world, connection.target)
        else:
            entrance.access_rule = make_req_rule(world, connection.req)
        if connection.bidirectional:
            reverse = multiworld.get_entrance(f"{connection.name} (reverse)", player)
            reverse.access_rule = entrance.access_rule

    # PROLOGUE FILET (Doteos 2026-07-21) : en jeu, on ne peut RIEN faire avant de
    # finir le tuto du tout début, qui EXIGE le Filet (attraper un insecte). On
    # reflète ça en logique : TOUTE location requiert le Filet, SAUF son propre
    # spot natif. Effet : le fill DOIT placer le Filet en sphère 0 -> son check
    # natif (dé-EXCLU) en solo, ou un check précoce d'un autre joueur en multi.
    # (Modèle zéro : bloque l'aventure dès le Ch6 -> gaté au niveau des RÉGIONS
    # Ch6+ dans regions.py/rules.py, pas ici, cf. DISTRICT_REQUIRED_ITEMS étendu.)
    ks = world.options.key_item_shuffle
    prologue = ("Filet à insectes",) if ks else ()

    # Checks.
    for name, data in world.active_location_data.items():
        extra_items = ()
        if data.category == LocationCategory.LEGENDARY \
                and world.options.legendary_shuffle:
            # The seal only opens once its shuffled medal has been received.
            extra_items = (legendary_medal_name(legendary_yokai_of(name)),)
        if name != "Objet-clé : Filet à insectes":
            extra_items += prologue
        location = multiworld.get_location(name, player)
        location.access_rule = make_req_rule(world, data.req, extra_items)

    # Events (chapter clears and goal bosses).
    for name, req in world.event_reqs.items():
        multiworld.get_location(name, player).access_rule = \
            make_req_rule(world, req)

    # Victory.
    multiworld.completion_condition[player] = make_completion_condition(world)
