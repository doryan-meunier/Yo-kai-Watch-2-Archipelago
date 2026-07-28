"""
Static data validation: IDs, names, groups and cross-references.

These tests do not need a generated multiworld.
"""

import unittest

from ..constants import (
    BASE_ID,
    CHAPTER_REGIONS,
    LEGENDARY_YOKAI,
)
from ..data import LocationCategory
from ..items import (
    ALL_ITEMS,
    FILLER_WEIGHTS,
    ITEM_GROUPS,
    ITEM_NAME_TO_ID,
    SHUFFLABLE_KEY_ITEMS,
    TRAP_WEIGHTS,
    VANILLA_KEY_PLACEMENTS,
    VANILLA_RANK_PLACEMENTS,
)
from ..locations import ALL_LOCATIONS, LOCATION_GROUPS, LOCATION_NAME_TO_ID
from ..regions import CONNECTIONS, REGION_NAMES


class TestStaticData(unittest.TestCase):
    def test_location_ids_unique(self) -> None:
        ids = list(LOCATION_NAME_TO_ID.values())
        self.assertEqual(len(ids), len(set(ids)))

    def test_item_ids_unique(self) -> None:
        ids = list(ITEM_NAME_TO_ID.values())
        self.assertEqual(len(ids), len(set(ids)))

    def test_ids_use_base(self) -> None:
        for code in list(LOCATION_NAME_TO_ID.values()) + list(ITEM_NAME_TO_ID.values()):
            self.assertGreaterEqual(code, BASE_ID)
            self.assertLess(code, BASE_ID + 10_000)

    def test_location_count_is_substantial(self) -> None:
        """The world advertises several hundred checks."""
        self.assertGreaterEqual(len(LOCATION_NAME_TO_ID), 400)

    def test_locations_reference_existing_regions(self) -> None:
        for name, data in ALL_LOCATIONS.items():
            self.assertIn(data.region, REGION_NAMES, name)

    def test_connections_reference_existing_regions(self) -> None:
        for connection in CONNECTIONS:
            self.assertIn(connection.source, REGION_NAMES, connection.name)
            self.assertIn(connection.target, REGION_NAMES, connection.name)

    def test_connection_items_exist(self) -> None:
        for connection in CONNECTIONS:
            for item in connection.req.items:
                self.assertIn(item, ALL_ITEMS, connection.name)

    def test_location_req_items_exist(self) -> None:
        for name, data in ALL_LOCATIONS.items():
            for item in data.req.items:
                self.assertIn(item, ALL_ITEMS, name)

    def test_chapter_regions_exist(self) -> None:
        for region in CHAPTER_REGIONS.values():
            self.assertIn(region, REGION_NAMES)

    def test_vanilla_placements_valid(self) -> None:
        for item, location in VANILLA_KEY_PLACEMENTS.items():
            self.assertIn(item, ALL_ITEMS)
            self.assertIn(location, ALL_LOCATIONS)
        for location in VANILLA_RANK_PLACEMENTS.values():
            self.assertIn(location, ALL_LOCATIONS)
        for item in SHUFFLABLE_KEY_ITEMS:
            self.assertIn(item, VANILLA_KEY_PLACEMENTS, item)

    def test_groups_reference_existing_names(self) -> None:
        for group, names in ITEM_GROUPS.items():
            for name in names:
                self.assertIn(name, ALL_ITEMS, f"{group}: {name}")
        for group, names in LOCATION_GROUPS.items():
            for name in names:
                self.assertIn(name, ALL_LOCATIONS, f"{group}: {name}")

    def test_weighted_tables_reference_existing_items(self) -> None:
        for name, weight in FILLER_WEIGHTS + TRAP_WEIGHTS:
            self.assertIn(name, ALL_ITEMS)
            self.assertGreater(weight, 0)

    def test_every_legendary_has_a_seal_location(self) -> None:
        for yokai in LEGENDARY_YOKAI:
            self.assertIn(f"Sceau légendaire : {yokai}", ALL_LOCATIONS)
            self.assertIn(f"Médaille légendaire : {yokai}", ALL_ITEMS)

    def test_every_region_has_content_or_purpose(self) -> None:
        regions_with_locations = {d.region for d in ALL_LOCATIONS.values()}
        for region in REGION_NAMES:
            if region == "Menu":
                continue
            connected = any(region in (c.source, c.target) for c in CONNECTIONS)
            self.assertTrue(
                connected or region in regions_with_locations, region)

    def test_categories_all_used(self) -> None:
        used = {data.category for data in ALL_LOCATIONS.values()}
        self.assertEqual(used, set(LocationCategory))
