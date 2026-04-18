# -*- coding: utf-8 -*-

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestCatalogSelectionWorkbench(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.category = cls.env.ref("diecut.category_tape_pet_double")
        cls.brand = cls.env["diecut.brand"].create({"name": "Workbench Brand"})
        cls.platform = cls.env["diecut.catalog.brand.platform"].create(
            {"name": "Workbench Platform", "brand_id": cls.brand.id}
        )
        cls.scene = cls.env["diecut.catalog.selection.scene"].create(
            {"name": "LED Bonding Scene", "selection_tip": "LED mounting"}
        )
        cls.series = cls.env["diecut.catalog.series"].create(
            {
                "name": "Workbench Series",
                "brand_id": cls.brand.id,
                "brand_platform_id": cls.platform.id,
                "default_scene_ids": [(6, 0, cls.scene.ids)],
            }
        )
        cls.param_peel = cls.env["diecut.catalog.param"].create(
            {
                "name": "Peel Strength",
                "param_key": "peel_strength",
                "value_type": "float",
                "selection_role": "filter",
                "display_group": "bonding",
                "is_primary_filter": True,
                "unit": "N/25mm",
                "preferred_unit": "N/25mm",
            }
        )
        cls.param_flame = cls.env["diecut.catalog.param"].create(
            {
                "name": "Flame Class",
                "param_key": "flame_class",
                "value_type": "selection",
                "selection_role": "compare",
                "display_group": "environment",
                "selection_options": "UL94 V-0\nUL94 HB",
            }
        )
        cls.param_halogen = cls.env["diecut.catalog.param"].create(
            {
                "name": "Halogen Free",
                "param_key": "halogen_free",
                "value_type": "boolean",
                "selection_role": "filter",
                "display_group": "environment",
            }
        )
        for sequence, param in enumerate((cls.param_peel, cls.param_flame, cls.param_halogen), start=1):
            cls.env["diecut.catalog.spec.def"].create(
                {
                    "categ_id": cls.category.id,
                    "param_id": param.id,
                    "name": param.name,
                    "param_key": param.param_key,
                    "value_type": param.value_type,
                    "sequence": sequence * 10,
                    "show_in_form": True,
                    "active": True,
                }
            )

        cls.item_match = cls.env["diecut.catalog.item"].create(
            {
                "brand_id": cls.brand.id,
                "series_id": cls.series.id,
                "categ_id": cls.category.id,
                "name": "Workbench Match Item",
                "code": "WB-001",
            }
        )
        cls.item_other = cls.env["diecut.catalog.item"].create(
            {
                "brand_id": cls.brand.id,
                "series_id": cls.series.id,
                "categ_id": cls.category.id,
                "name": "Workbench Other Item",
                "code": "WB-002",
            }
        )
        cls.item_match.apply_param_payload(param=cls.param_peel, raw_value="15", unit="N/25mm")
        cls.item_match.apply_param_payload(param=cls.param_flame, raw_value="UL94 V-0")
        cls.item_match.apply_param_payload(param=cls.param_halogen, raw_value="true")

        cls.item_other.apply_param_payload(param=cls.param_peel, raw_value="7", unit="N/25mm")
        cls.item_other.apply_param_payload(param=cls.param_flame, raw_value="UL94 HB")
        cls.item_other.apply_param_payload(param=cls.param_halogen, raw_value="false")

    def test_workbench_bootstrap_contains_filter_params(self):
        bootstrap = self.env["diecut.catalog.item"].get_selection_workbench_bootstrap(self.category.id)
        param_ids = {param["id"] for param in bootstrap["params"]}
        self.assertIn(self.param_peel.id, param_ids)
        self.assertIn(self.param_flame.id, param_ids)
        self.assertIn(self.param_halogen.id, param_ids)

    def test_workbench_results_support_multi_condition_filtering(self):
        result = self.env["diecut.catalog.item"].get_selection_workbench_results(
            {
                "brand_id": self.brand.id,
                "categ_id": self.category.id,
                "scene_ids": [self.scene.id],
                "conditions": [
                    {"param_id": self.param_peel.id, "operator": "gte", "value": 12},
                    {"param_id": self.param_flame.id, "operator": "eq", "value": "UL94 V-0"},
                    {"param_id": self.param_halogen.id, "operator": "eq", "value": True},
                ],
                "compare_param_ids": [self.param_flame.id],
                "sort": "relevance",
                "limit": 10,
            }
        )
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["results"][0]["id"], self.item_match.id)
        self.assertEqual(
            result["results"][0]["compare_values"][str(self.param_flame.id)]["display"],
            "UL94 V-0",
        )
