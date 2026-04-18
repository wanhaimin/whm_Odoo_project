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
        item.spec_line_ids[0].write({"value_raw": "123", "value_kind": "text"})

        with self.assertRaises(ValidationError):
            item.write({"categ_id": self.category_tape_pet_double.id})
        self.assertEqual(item.categ_id, self.category_foam)
        self.assertEqual(
            item.spec_line_ids.mapped("param_key"),
            self.env["diecut.catalog.item"]._get_active_category_params(self.category_foam.id).mapped("param_key"),
        )

    def test_same_param_allows_multiple_conditioned_spec_lines(self):
        item = self.env["diecut.catalog.item"].create(
            {
                "brand_id": self.brand.id,
                "categ_id": self.category_foam.id,
                "name": "条件参数测试",
                "code": "TMP-COND-001",
            }
        )
        spec_def = self.env["diecut.catalog.item"]._get_active_category_params(self.category_foam.id)[:1]
        self.assertTrue(spec_def)

        item.apply_param_payload(
            param=spec_def.param_id,
            raw_value="12.6",
            unit="N/cm",
            test_condition="180°剥离力",
            conditions=[
                {"condition_key": "substrate", "condition_label": "被贴合物", "condition_value": "不锈钢"},
            ],
        )
        item.apply_param_payload(
            param=spec_def.param_id,
            raw_value="9.7",
            unit="N/cm",
            test_condition="180°剥离力",
            conditions=[
                {"condition_key": "substrate", "condition_label": "被贴合物", "condition_value": "ABS"},
            ],
        )

        lines = item.spec_line_ids.filtered(lambda line: line.param_id == spec_def.param_id)
        self.assertEqual(len(lines), 2)
        self.assertSetEqual(set(lines.mapped("condition_summary")), {"不锈钢", "ABS"})
