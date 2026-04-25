# -*- coding: utf-8 -*-

import csv
import os
import tempfile

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.diecut.scripts.import_raw_materials import RawMaterialImporter


@tagged("post_install", "-at_install")
class TestRawMaterialImporter(TransactionCase):
    def setUp(self):
        super().setUp()
        self.importer = RawMaterialImporter(self.env)

    def make_csv(self, headers, rows):
        tmp_dir = tempfile.mkdtemp(prefix="diecut_raw_material_import_")
        path = os.path.join(tmp_dir, "materials.csv")
        with open(path, "w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(headers)
            writer.writerows(rows)
        return path, tmp_dir

    def test_import_creates_material_and_related_masters(self):
        category = self.env["product.category"].create({
            "name": "导入测试胶带",
            "parent_id": self.env.ref("diecut.category_tape").id,
        })
        file_path, _tmp_dir = self.make_csv(
            ["编码", "名称", "规格", "分类", "品牌", "颜色", "供应商", "制造商", "宽度", "长度", "厚度", "单价/m²"],
            [[
                "RM-001",
                "3M 导入料",
                "Spec-A",
                category.name,
                "3M",
                "透明",
                "昆山供应商A",
                "制造商A",
                "1200",
                "100m",
                "0.15",
                "18.5",
            ]],
        )

        summary = self.importer.import_file(file_path)

        self.assertEqual(summary["created"], 1)
        product = self.env["product.template"].search([("default_code", "=", "RM-001")], limit=1)
        self.assertTrue(product)
        self.assertTrue(product.is_raw_material)
        self.assertEqual(product.categ_id.id, category.id)
        self.assertEqual(product.rs_type, "R")
        self.assertAlmostEqual(product.length, 100.0, places=4)
        self.assertAlmostEqual(product.raw_material_price_m2, 18.5, places=2)
        self.assertEqual(product.brand_id.name, "3M")
        self.assertEqual(product.color_id.name, "透明")
        self.assertEqual(product.main_vendor_id.name, "昆山供应商A")
        self.assertEqual(product.manufacturer_id.name, "制造商A")
        seller = product.seller_ids.filtered(lambda s: s.partner_id == product.main_vendor_id)
        self.assertTrue(seller)
        self.assertAlmostEqual(seller[0].price, 18.5, places=2)
        self.assertAlmostEqual(seller[0].price_per_m2, 18.5, places=2)

    def test_import_updates_existing_product_by_default_code(self):
        category = self.env["product.category"].create({
            "name": "导入更新分类",
            "parent_id": self.env.ref("diecut.category_tape").id,
        })
        vendor = self.env["res.partner"].create({
            "name": "老供应商",
            "is_company": True,
            "supplier_rank": 1,
        })
        product = self.env["product.template"].create({
            "name": "旧材料",
            "default_code": "RM-002",
            "spec": "旧规格",
            "is_raw_material": True,
            "categ_id": category.id,
            "main_vendor_id": vendor.id,
            "width": 1000.0,
            "length": 50.0,
            "raw_material_price_m2": 10.0,
        })
        file_path, _tmp_dir = self.make_csv(
            ["编码", "名称", "规格", "分类", "供应商", "宽度", "长度(mm)", "单价/m²"],
            [[
                "RM-002",
                "更新后的材料",
                "新规格",
                category.name,
                vendor.name,
                "800",
                "500",
                "25.8",
            ]],
        )

        summary = self.importer.import_file(file_path)

        self.assertEqual(summary["updated"], 1)
        refreshed = product.exists()
        self.assertEqual(refreshed.name, "更新后的材料")
        self.assertEqual(refreshed.spec, "新规格")
        self.assertEqual(refreshed.rs_type, "S")
        self.assertAlmostEqual(refreshed.length, 0.5, places=4)
        self.assertAlmostEqual(refreshed.raw_material_price_m2, 25.8, places=2)
        self.assertEqual(
            self.env["product.template"].search_count([("default_code", "=", "RM-002"), ("is_raw_material", "=", True)]),
            1,
        )

    def test_import_updates_existing_product_by_name_spec_vendor_when_code_missing(self):
        category = self.env["product.category"].create({
            "name": "导入无编码分类",
            "parent_id": self.env.ref("diecut.category_tape").id,
        })
        vendor = self.env["res.partner"].create({
            "name": "无编码供应商",
            "is_company": True,
            "supplier_rank": 1,
        })
        product = self.env["product.template"].create({
            "name": "无编码材料",
            "spec": "A-01",
            "is_raw_material": True,
            "categ_id": category.id,
            "main_vendor_id": vendor.id,
            "width": 900.0,
            "length": 30.0,
        })
        file_path, _tmp_dir = self.make_csv(
            ["名称", "规格", "分类", "供应商", "宽度", "长度", "单价/m²"],
            [[
                "无编码材料",
                "A-01",
                category.name,
                vendor.name,
                "950",
                "40m",
                "12.2",
            ]],
        )

        summary = self.importer.import_file(file_path)

        self.assertEqual(summary["updated"], 1)
        refreshed = product.exists()
        self.assertAlmostEqual(refreshed.width, 950.0, places=2)
        self.assertAlmostEqual(refreshed.length, 40.0, places=2)
        self.assertEqual(
            self.env["product.template"].search_count([("name", "=", "无编码材料"), ("spec", "=", "A-01"), ("is_raw_material", "=", True)]),
            1,
        )

    def test_import_reports_unknown_category_and_writes_failure_file(self):
        file_path, tmp_dir = self.make_csv(
            ["编码", "名称", "分类", "供应商"],
            [["RM-404", "未知分类材料", "不存在的分类", "供应商Z"]],
        )
        fail_output = os.path.join(tmp_dir, "failures.csv")

        summary = self.importer.import_file(file_path, dry_run=True, fail_output_path=fail_output)

        self.assertEqual(summary["failed"], 1)
        self.assertTrue(os.path.exists(fail_output))
        with open(fail_output, "r", encoding="utf-8-sig") as handle:
            content = handle.read()
        self.assertIn("未识别分类", content)

