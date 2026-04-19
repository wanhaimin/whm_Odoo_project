# -*- coding: utf-8 -*-

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestDiecutQuoteCosts(TransactionCase):
    def test_default_manufacturing_processes_match_quote_sheet(self):
        quote = self.env["diecut.quote"].new({})

        self.assertEqual(
            quote.manufacturing_line_ids.mapped("step_1"),
            ["分条", "贴合", "模切", "排废", "对贴", "折弯", "品检", "包装"],
        )
        die_cut = quote.manufacturing_line_ids.filtered(lambda line: line.step_1 == "模切")
        self.assertEqual(die_cut.mfg_fee, 35.0)
        self.assertEqual(die_cut.workstation_qty, 1)
        self.assertEqual(die_cut.capacity, 100000)
        self.assertEqual(die_cut.yield_rate, 0.97)
        self.assertEqual(quote.profit_rate, 0.15)
        self.assertEqual(quote.transport_rate, 0.01)
        self.assertEqual(quote.management_rate, 0.03)
        self.assertEqual(quote.utility_rate, 0.01)
        self.assertEqual(quote.packaging_rate, 0.01)
        self.assertEqual(quote.depreciation_rate, 0.01)

    def test_manufacturing_cost_matches_excel_formula(self):
        line = self.env["diecut.quote.manufacturing.line"].new(
            {
                "mfg_fee": 35.0,
                "workstation_qty": 1,
                "capacity": 100000,
                "yield_rate": 0.97,
            }
        )

        line._compute_cost()

        self.assertAlmostEqual(line.cost_per_pcs, 35.0 * 1 / 100000 / 0.97, places=4)

    def test_manufacturing_cost_handles_zero_capacity_and_yield(self):
        line = self.env["diecut.quote.manufacturing.line"].new(
            {
                "mfg_fee": 35.0,
                "workstation_qty": 1,
                "capacity": 0,
                "yield_rate": 0.97,
            }
        )
        line._compute_cost()
        self.assertEqual(line.cost_per_pcs, 0.0)

        line.capacity = 100000
        line.yield_rate = 0.0
        line._compute_cost()
        self.assertEqual(line.cost_per_pcs, 0.0)

    def test_material_cost_splits_tax_included_amount(self):
        quote = self.env["diecut.quote"].new({})
        quote.total_material_cost = 113.0

        quote._compute_material_tax_costs()

        self.assertAlmostEqual(quote.total_material_cost_tax_included, 113.0, places=8)
        self.assertAlmostEqual(quote.total_material_cost_excluded, 100.0, places=8)
        self.assertAlmostEqual(quote.material_input_vat, 13.0, places=8)

    def test_overhead_other_final_price_and_ratios_match_tax_quote_logic(self):
        quote = self.env["diecut.quote"].new(
            {
                "transport_rate": 1.0,
                "management_rate": 3.0,
                "utility_rate": 1.0,
                "packaging_rate": 1.0,
                "depreciation_rate": 1.0,
                "sample_cost_input": 1000.0,
                "mold_fee": 4000.0,
                "punch_qty": 100000,
                "profit_rate": 10.0,
            }
        )
        material_cost_tax_included = 0.0373496784587239
        manufacturing_cost = 0.000407731958762887
        quote.total_material_cost = material_cost_tax_included
        quote._compute_material_tax_costs()
        quote.total_manufacturing_cost = manufacturing_cost
        material_cost = quote.total_material_cost_excluded
        manufacturing_cost = quote.total_manufacturing_cost

        quote._compute_overhead_costs()

        overhead_base = material_cost + manufacturing_cost
        self.assertAlmostEqual(quote.transport_cost, overhead_base * 0.01, places=4)
        self.assertAlmostEqual(quote.management_cost, overhead_base * 0.03, places=4)
        self.assertAlmostEqual(quote.utility_cost, overhead_base * 0.01, places=4)
        self.assertAlmostEqual(quote.packaging_cost, overhead_base * 0.01, places=4)
        self.assertAlmostEqual(quote.depreciation_cost, overhead_base * 0.01, places=4)
        self.assertAlmostEqual(quote.total_marketing_cost, overhead_base * 0.07, places=4)

        quote._compute_other_costs()

        self.assertAlmostEqual(quote.sample_unit_cost, 1000.0 / 100000, places=4)
        self.assertAlmostEqual(quote.mold_cost, 4000.0 / 100000, places=4)
        self.assertAlmostEqual(quote.total_other_cost, 5000.0 / 100000, places=4)

        quote._compute_final_price()
        quote._compute_ratios()

        subtotal = (
            material_cost
            + manufacturing_cost
            + quote.total_marketing_cost
            + quote.total_other_cost
        )
        quote_price_excluded = subtotal / (1.0 - 0.10)
        profit = quote_price_excluded - subtotal
        output_vat = quote_price_excluded * 0.13
        final_price = quote_price_excluded + output_vat
        self.assertAlmostEqual(quote.subtotal_cost, subtotal, places=4)
        self.assertAlmostEqual(quote.quote_price_excluded, quote_price_excluded, places=4)
        self.assertAlmostEqual(quote.profit_amount, profit, places=4)
        self.assertAlmostEqual(quote.output_vat, output_vat, places=4)
        self.assertAlmostEqual(
            quote.estimated_vat_payable,
            output_vat - quote.material_input_vat,
            places=4,
        )
        self.assertAlmostEqual(quote.final_unit_price, round(final_price, 4), places=4)
        self.assertAlmostEqual(quote.material_cost_ratio, material_cost / quote_price_excluded, places=4)
        self.assertAlmostEqual(
            quote.manufacturing_cost_ratio, manufacturing_cost / quote_price_excluded, places=4
        )
        self.assertAlmostEqual(
            quote.marketing_cost_ratio, quote.total_marketing_cost / quote_price_excluded, places=4
        )
        self.assertAlmostEqual(quote.other_cost_ratio, quote.total_other_cost / quote_price_excluded, places=4)
        self.assertAlmostEqual(
            quote.profit_cost_ratio, quote.profit_amount / quote_price_excluded, places=4
        )

    def test_other_cost_handles_zero_allocation_quantity(self):
        quote = self.env["diecut.quote"].new(
            {
                "sample_cost_input": 1000.0,
                "mold_fee": 4000.0,
                "punch_qty": 0,
            }
        )

        quote._compute_other_costs()

        self.assertEqual(quote.sample_unit_cost, 0.0)
        self.assertEqual(quote.mold_cost, 0.0)
        self.assertEqual(quote.total_other_cost, 0.0)

    def test_ratio_style_rates_are_supported(self):
        quote = self.env["diecut.quote"].new(
            {
                "transport_rate": 0.01,
                "management_rate": 0.03,
                "utility_rate": 0.01,
                "packaging_rate": 0.01,
                "depreciation_rate": 0.01,
                "profit_rate": 0.10,
            }
        )
        quote.total_material_cost = 1.13
        quote._compute_material_tax_costs()
        quote.total_manufacturing_cost = 1.0

        quote._compute_overhead_costs()
        quote._compute_other_costs()
        quote._compute_final_price()

        expected_quote_price_excluded = quote.subtotal_cost / (1.0 - 0.10)
        self.assertEqual(quote.final_unit_price, round(expected_quote_price_excluded * 1.13, 4))

        self.assertAlmostEqual(quote.total_marketing_cost, 2.0 * 0.07, places=4)
        self.assertAlmostEqual(quote.profit_amount, expected_quote_price_excluded - quote.subtotal_cost, places=4)

    def test_profit_rate_at_or_above_100_percent_returns_zero_quote(self):
        quote = self.env["diecut.quote"].new({"profit_rate": 100.0})
        quote.total_material_cost = 113.0
        quote._compute_material_tax_costs()
        quote.total_manufacturing_cost = 1.0
        quote.total_marketing_cost = 1.0
        quote.total_other_cost = 1.0

        quote._compute_final_price()

        self.assertAlmostEqual(quote.subtotal_cost, 103.0, places=8)
        self.assertEqual(quote.quote_price_excluded, 0.0)
        self.assertEqual(quote.profit_amount, 0.0)
        self.assertEqual(quote.output_vat, 0.0)
        self.assertAlmostEqual(quote.estimated_vat_payable, -13.0, places=8)
        self.assertEqual(quote.final_unit_price, 0.0)

    def test_quote_copy_keeps_material_and_manufacturing_lines(self):
        customer = self.env["res.partner"].create({
            "name": "Copy Test Customer",
            "is_company": True,
            "customer_rank": 1,
        })
        material_a = self.env["product.product"].create({
            "name": "Copy Material A",
            "is_raw_material": True,
            "width": 1200.0,
            "length": 100.0,
            "raw_material_unit_price": 240.0,
        })
        material_b = self.env["product.product"].create({
            "name": "Copy Material B",
            "is_raw_material": True,
            "width": 1000.0,
            "length": 80.0,
            "raw_material_unit_price": 180.0,
        })
        quote = self.env["diecut.quote"].create({
            "customer_id": customer.id,
            "product_name": "Copy Product",
            "project_sn": "P-001",
            "internal_sn": "I-001",
            "terminal": "Terminal",
            "specification": "10*20",
            "moq": 5000,
            "lead_time": 7,
            "transport_rate": 1.0,
            "management_rate": 3.0,
            "utility_rate": 1.0,
            "packaging_rate": 1.0,
            "depreciation_rate": 1.0,
            "sample_cost_input": 1000.0,
            "mold_fee": 4000.0,
            "punch_qty": 100000,
            "profit_rate": 10.0,
            "vat_rate": 13.0,
            "material_line_ids": [
                (0, 0, {
                    "material_id": material_a.id,
                    "is_checked": True,
                    "raw_width": 1200.0,
                    "raw_length": 100000.0,
                    "price_unit_tax_inc": 240.0,
                    "slitting_width": 23.5,
                    "pitch": 23.0,
                    "cavity": 2,
                    "yield_rate": 0.98,
                }),
                (0, 0, {
                    "material_id": material_b.id,
                    "is_checked": True,
                    "raw_width": 1000.0,
                    "raw_length": 80000.0,
                    "price_unit_tax_inc": 180.0,
                    "slitting_width": 20.0,
                    "pitch": 18.0,
                    "cavity": 4,
                    "yield_rate": 0.96,
                }),
            ],
            "manufacturing_line_ids": [
                (0, 0, {
                    "step_1": "Die Cut",
                    "step_2": "Main process",
                    "mfg_fee": 35.0,
                    "workstation_qty": 1,
                    "capacity": 100000,
                    "yield_rate": 0.97,
                }),
                (0, 0, {
                    "step_1": "Packing",
                    "step_2": "Final pack",
                    "mfg_fee": 25.0,
                    "workstation_qty": 2,
                    "capacity": 1000000,
                    "yield_rate": 1.0,
                }),
            ],
        })

        copied = quote.copy()

        self.assertNotEqual(copied.name, quote.name)
        self.assertEqual(copied.customer_id, quote.customer_id)
        self.assertEqual(copied.product_name, quote.product_name)
        self.assertEqual(copied.project_sn, quote.project_sn)
        self.assertEqual(copied.moq, quote.moq)
        self.assertEqual(copied.profit_rate, quote.profit_rate)
        self.assertEqual(copied.vat_rate, quote.vat_rate)

        self.assertEqual(len(copied.material_line_ids), 2)
        self.assertFalse(any(copied.material_line_ids.mapped("is_checked")))
        for original, duplicate in zip(quote.material_line_ids, copied.material_line_ids):
            self.assertEqual(duplicate.material_id, original.material_id)
            self.assertAlmostEqual(duplicate.price_unit_tax_inc, original.price_unit_tax_inc, places=4)
            self.assertAlmostEqual(duplicate.slitting_width, original.slitting_width, places=4)
            self.assertAlmostEqual(duplicate.pitch, original.pitch, places=4)
            self.assertEqual(duplicate.cavity, original.cavity)
            self.assertAlmostEqual(duplicate.yield_rate, original.yield_rate, places=4)

        self.assertEqual(len(copied.manufacturing_line_ids), 2)
        for original, duplicate in zip(quote.manufacturing_line_ids, copied.manufacturing_line_ids):
            self.assertEqual(duplicate.step_1, original.step_1)
            self.assertEqual(duplicate.step_2, original.step_2)
            self.assertAlmostEqual(duplicate.mfg_fee, original.mfg_fee, places=4)
            self.assertEqual(duplicate.workstation_qty, original.workstation_qty)
            self.assertEqual(duplicate.capacity, original.capacity)
            self.assertAlmostEqual(duplicate.yield_rate, original.yield_rate, places=4)

        self.assertAlmostEqual(copied.final_unit_price, quote.final_unit_price, places=4)
