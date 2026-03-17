# -*- coding: utf-8 -*-

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestCatalogSelectionSearch(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.brand = cls.env["diecut.brand"].create({"name": "检索测试品牌"})
        cls.category = cls.env.ref("diecut.category_tape_pet_double")
        cls.application_tag = cls.env["diecut.catalog.application.tag"].create(
            {
                "name": "测试-LED灯条背胶",
                "alias_text": "灯条固定, light bar mounting",
            }
        )
        cls.feature_tag = cls.env["diecut.catalog.feature.tag"].create(
            {
                "name": "测试-防篡改",
                "alias_text": "tamper evident",
            }
        )
        cls.function_tag = cls.env["product.tag"].create(
            {
                "name": "测试-粘接固定",
                "alias_text": "bonding",
            }
        )
        cls.item = cls.env["diecut.catalog.item"].create(
            {
                "brand_id": cls.brand.id,
                "categ_id": cls.category.id,
                "name": "选型检索测试材料",
                "code": "SEARCH-001",
                "application_tag_ids": [(6, 0, cls.application_tag.ids)],
                "feature_tag_ids": [(6, 0, cls.feature_tag.ids)],
                "function_tag_ids": [(6, 0, cls.function_tag.ids)],
            }
        )

    def test_tag_name_search_supports_aliases(self):
        app_results = self.env["diecut.catalog.application.tag"].name_search("light bar mounting")
        feature_results = self.env["diecut.catalog.feature.tag"].name_search("tamper evident")
        function_results = self.env["product.tag"].name_search("bonding")

        self.assertIn(self.application_tag.id, [tag_id for tag_id, _label in app_results])
        self.assertIn(self.feature_tag.id, [tag_id for tag_id, _label in feature_results])
        self.assertIn(self.function_tag.id, [tag_id for tag_id, _label in function_results])

    def test_catalog_item_search_text_includes_aliases(self):
        search_text = self.item.selection_search_text or ""
        self.assertIn("light bar mounting", search_text)
        self.assertIn("tamper evident", search_text)
        self.assertIn("bonding", search_text)

    def test_catalog_item_name_search_supports_tag_aliases(self):
        item_ids = self.env["diecut.catalog.item"]._name_search("light bar mounting")
        self.assertIn(self.item.id, item_ids)

        ranked_records = self.env["diecut.catalog.item"].search_fetch(
            [("application_tag_ids.alias_text", "ilike", "light bar mounting")],
            field_names=["code"],
            limit=5,
        )
        self.assertEqual(ranked_records[:1].id, self.item.id)
