# -*- coding: utf-8 -*-
"""
Logic tests: key items must actually gate what they are supposed to gate.

story_shuffle is enabled in these tests so that chapter progression comes
from pool items (events are not collected by assertAccessDependency).
"""

from . import YKW2TestBase


class TestKeyItemGates(YKW2TestBase):
    options = {"story_shuffle": True}

    def test_corniche_requires_bicycle(self) -> None:
        self.assertAccessDependency(
            ["La Corniche - Coffre 01"], [["Vélo"]],
            only_check_listed=True)

    # Note : les billets/tickets de train (Ourcival / San Fantastico / passé
    # « rétro ») s'achètent nativement en jeu -> plus des objets-clés de gating
    # (retirés du pool 2026-07-19). Ces régions ne dépendent que du chapitre.

    def test_limbes_require_cabin_key(self) -> None:
        self.assertAccessDependency(
            ["Limbes éternelles - Coffre 01"], [["Clé de cabane"]],
            only_check_listed=True)

    def test_rank_s_quest_requires_watch_ranks(self) -> None:
        self.assertAccessDependency(
            ["Obtenons le rang S !"], [["Rang de Yo-kai Watch (progressif)"]],
            only_check_listed=True)

    def test_story_gates_on_progressive_chapters(self) -> None:
        self.assertAccessDependency(
            ["Chapitre 11 : Danger au vieux Granval !"],
            [["Chapitre d'histoire (progressif)"]],
            only_check_listed=True)


class TestLegendaryGates(YKW2TestBase):
    options = {"story_shuffle": True, "legendary_shuffle": True}

    def test_seal_requires_its_medal(self) -> None:
        self.assertAccessDependency(
            ["Sceau légendaire : Shogunyan"],
            [["Médaille légendaire : Shogunyan"]],
            only_check_listed=True)


class TestCollectionGates(YKW2TestBase):
    options = {"story_shuffle": True, "collection_shuffle": True}

    # Note : le « Filet à insectes » a été retiré (toujours natif) -> les insectes
    # ne sont plus gatés par un objet, seulement par leur région. Seule la Canne
    # à pêche reste un objet-clé de gating (poissons).

    def test_fish_require_fishing_rod(self) -> None:
        self.assertAccessDependency(
            ["Poisson : Sériole"], [["Canne à pêche"]],
            only_check_listed=True)
