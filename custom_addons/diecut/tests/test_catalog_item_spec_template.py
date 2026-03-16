# -*- coding: utf-8 -*-

# -*- coding: utf-8 -*-

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestCatalogItemSpecTemplate(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.brand = cls.env["diecut.brand"].create({"name": "测试品牌"})
        cls.category_foam = cls.env.ref("diecut.category_foam")
        cls.category_tape_pet_double = cls.env.ref("diecut.category_tape_pet_double")

    def test_blank_template_rebuilds_when_category_changes(self):
        expected_foam_keys = self.env["diecut.catalog.item"]._get_active_category_params(
            self.category_foam.id
        ).mapped("param_key")
        expected_tape_keys = self.env["diecut.catalog.item"]._get_active_category_params(
            self.category_tape_pet_double.id
        ).mapped("param_key")
        item = self.env["diecut.catalog.item"].new(
            {
                "brand_id": self.brand.id,
                "categ_id": self.category_foam.id,
                "name": "模板切换测试",
                "code": "TMP-SWITCH-001",
            }
        )
        item._onchange_categ_id_fill_spec_lines()

        self.assertEqual(item.categ_id, self.category_foam)
        self.assertEqual(item.spec_line_ids.mapped("param_key"), expected_foam_keys)

        item.categ_id = self.category_tape_pet_double
        result = item._onchange_categ_id_fill_spec_lines()

        self.assertFalse(result and result.get("warning"))
        self.assertEqual(item.categ_id, self.category_tape_pet_double)
        self.assertEqual(item.spec_line_ids.mapped("param_key"), expected_tape_keys)

    def test_filled_template_blocks_category_change_on_write(self):
        item = self.env["diecut.catalog.item"].create(
            {
                "brand_id": self.brand.id,
                "categ_id": self.category_foam.id,
                "name": "模板保护测试",
                "code": "TMP-SWITCH-002",
            }
        )
        item.spec_line_ids[0].value_text = "123"

        with self.assertRaises(ValidationError):
            item.write({"categ_id": self.category_tape_pet_double.id})
        self.assertEqual(item.categ_id, self.category_foam)
        self.assertEqual(
            item.spec_line_ids.mapped("param_key"),
            self.env["diecut.catalog.item"]._get_active_category_params(self.category_foam.id).mapped("param_key"),
        )
