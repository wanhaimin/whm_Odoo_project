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

        self.assertAlmostEqual(line.cost_per_pcs, 35.0 * 1 / 100000 / 0.97, places=8)

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

    def test_overhead_other_final_price_and_ratios_match_excel_logic(self):
        quote = self.env["diecut.quote"].new(
            {
                "transport_rate": 1.0,
                "management_rate": 3.0,
                "utility_rate": 1.0,
                "packaging_rate": 1.0,
                "depreciation_rate": 1.0,
                "sample_cost_input": 1000.0,
                "mold_fee": 4000.0,
                "punch_qty": 20000000,
                "profit_rate": 10.0,
            }
        )
        material_cost = 0.0373496784587239
        manufacturing_cost = 0.000407731958762887
        quote.total_material_cost = material_cost
        quote.total_manufacturing_cost = manufacturing_cost
        material_cost = quote.total_material_cost
        manufacturing_cost = quote.total_manufacturing_cost

        quote._compute_overhead_costs()

        overhead_base = material_cost + manufacturing_cost
        self.assertAlmostEqual(quote.transport_cost, overhead_base * 0.01, places=8)
        self.assertAlmostEqual(quote.management_cost, overhead_base * 0.03, places=8)
        self.assertAlmostEqual(quote.utility_cost, overhead_base * 0.01, places=8)
        self.assertAlmostEqual(quote.packaging_cost, overhead_base * 0.01, places=8)
        self.assertAlmostEqual(quote.depreciation_cost, overhead_base * 0.01, places=8)
        self.assertAlmostEqual(quote.total_marketing_cost, overhead_base * 0.07, places=8)

        quote._compute_other_costs()

        self.assertAlmostEqual(quote.sample_unit_cost, 1000.0 / 20000000, places=8)
        self.assertAlmostEqual(quote.mold_cost, 4000.0 / 20000000, places=8)
        self.assertAlmostEqual(quote.total_other_cost, 5000.0 / 20000000, places=8)

        quote._compute_final_price()
        quote._compute_ratios()

        subtotal = (
            material_cost
            + manufacturing_cost
            + quote.total_marketing_cost
            + quote.total_other_cost
        )
        profit = subtotal * 0.10
        final_price = subtotal + profit
        self.assertAlmostEqual(quote.subtotal_cost, subtotal, places=8)
        self.assertAlmostEqual(quote.profit_amount, profit, places=8)
        self.assertAlmostEqual(quote.final_unit_price, round(final_price, 4), places=4)
        self.assertAlmostEqual(quote.material_cost_ratio, material_cost / quote.final_unit_price, places=8)
        self.assertAlmostEqual(
            quote.manufacturing_cost_ratio, manufacturing_cost / quote.final_unit_price, places=8
        )
        self.assertAlmostEqual(
            quote.marketing_cost_ratio, quote.total_marketing_cost / final_price, places=8
        )
        self.assertAlmostEqual(quote.other_cost_ratio, quote.total_other_cost / final_price, places=8)
        self.assertAlmostEqual(
            quote.profit_cost_ratio, quote.profit_amount / quote.final_unit_price, places=8
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
        quote.total_material_cost = 1.0
        quote.total_manufacturing_cost = 1.0

        quote._compute_overhead_costs()
        quote._compute_other_costs()
        quote._compute_final_price()

        self.assertEqual(quote.final_unit_price, round(quote.subtotal_cost * 1.10, 4))

        self.assertAlmostEqual(quote.total_marketing_cost, 2.0 * 0.07, places=8)
        self.assertAlmostEqual(quote.profit_amount, quote.subtotal_cost * 0.10, places=8)
