import unittest

from app.core.constants.macro_categories import (
    MACRO_CATEGORIES_MAPPING,
    MACRO_CATEGORY_ORDER,
    UNCLASSIFIED_MACRO,
    get_categories_for_macro,
    get_macro_category,
    macro_sort_key,
)


class TestMacroCategoriesMapping(unittest.TestCase):
    def test_known_category_maps_to_expected_group(self):
        self.assertEqual(get_macro_category("fighter"), "Fighter / Beat 'em Up")
        self.assertEqual(get_macro_category("shooter"), "Shooter / Shmup")
        self.assertEqual(get_macro_category("ball_paddle"), "Puzzle / Tabletop")
        self.assertEqual(get_macro_category("handheld"), "System / Non-Games")
        self.assertEqual(get_macro_category("arcade"), "Casino / Gambling / Pinball")

    def test_unknown_category_falls_back_to_unclassified(self):
        self.assertEqual(get_macro_category("quiz"), UNCLASSIFIED_MACRO)
        self.assertEqual(get_macro_category("robot"), UNCLASSIFIED_MACRO)
        self.assertEqual(get_macro_category(""), UNCLASSIFIED_MACRO)
        self.assertEqual(get_macro_category(None), UNCLASSIFIED_MACRO)

    def test_lookup_is_case_and_space_insensitive(self):
        self.assertEqual(get_macro_category("  Fighter  "), "Fighter / Beat 'em Up")
        self.assertEqual(get_macro_category("FIGHTER"), "Fighter / Beat 'em Up")

    def test_all_mapping_entries_are_non_empty_strings(self):
        for key, value in MACRO_CATEGORIES_MAPPING.items():
            self.assertIsInstance(key, str)
            self.assertTrue(key)
            self.assertIsInstance(value, str)
            self.assertTrue(value)

    def test_all_mapping_values_are_in_known_order(self):
        # Todo macro-grupo usado no mapeamento precisa estar na ordem de
        # exibição, senão ele apareceria fora de ordem/no final sem ser
        # intencional.
        known_groups = set(MACRO_CATEGORY_ORDER)
        for macro_name in MACRO_CATEGORIES_MAPPING.values():
            self.assertIn(macro_name, known_groups)

    def test_sort_key_orders_known_groups_before_unclassified(self):
        self.assertLess(
            macro_sort_key("System / Non-Games"),
            macro_sort_key(UNCLASSIFIED_MACRO),
        )

    def test_sort_key_unknown_group_goes_last(self):
        self.assertEqual(
            macro_sort_key("Grupo Inexistente"),
            len(MACRO_CATEGORY_ORDER),
        )

    def test_get_categories_for_macro_returns_expected_members(self):
        puzzle_categories = get_categories_for_macro("Puzzle / Tabletop")
        self.assertIn("puzzle", puzzle_categories)
        self.assertIn("board_game", puzzle_categories)
        self.assertIn("card_games", puzzle_categories)
        self.assertNotIn("fighter", puzzle_categories)

    def test_get_categories_for_macro_unknown_group_returns_empty(self):
        self.assertEqual(get_categories_for_macro("Grupo Inexistente"), [])


if __name__ == "__main__":
    unittest.main()
