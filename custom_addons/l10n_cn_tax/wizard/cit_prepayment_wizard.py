# -*- coding: utf-8 -*-
import logging
from datetime import date

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

_QUARTER_DATES = {
    'q1': (1, 1, 3, 31),
    'q2': (4, 1, 6, 30),
    'q3': (7, 1, 9, 30),
    'q4': (10, 1, 12, 31),
}


def _current_quarter():
    m = date.today().month
    if m <= 3:
        return 'q1'
    if m <= 6:
        return 'q2'
    if m <= 9:
        return 'q3'
    return 'q4'


def _calc_cit_rate(annual_profit_estimate, is_small_profit):
    """
    小型微利企业阶梯税率（实际利润法，按年利润估算）：
      ≤ 100万：5%
      100万 < 利润 ≤ 300万：10%（仅超出部分，但简化为全额10%）
      > 300万 或 非小微：25%

    注：实务中一般按累计利润全额适用税率（非超额累进），此处与税务局申报表口径一致。
    """
    if not is_small_profit or annual_profit_estimate > 3_000_000:
        return 0.25
    if annual_profit_estimate <= 1_000_000:
        return 0.05
    return 0.10


class CitPrepaymentWizard(models.TransientModel):
    _name = 'l10n_cn_tax.cit.prepayment'
    _description = '企业所得税季度预缴'

    # --- 申报期间 ---
    fiscal_year = fields.Integer(string='申报年份', default=lambda self: date.today().year)
    quarter = fields.Selection(
        selection=[
            ('q1', '第一季度 (1-3月)'),
            ('q2', '第二季度 (4-6月)'),
            ('q3', '第三季度 (7-9月)'),
            ('q4', '第四季度 (10-12月)'),
        ],
        string='申报季度',
        default=lambda self: _current_quarter(),
        required=True,
    )
    date_from = fields.Date(string='累计起始（年初）', compute='_compute_dates', store=True, readonly=False)
    date_to = fields.Date(string='累计截止', compute='_compute_dates', store=True, readonly=False)

    company_id = fields.Many2one(
        'res.company',
        string='公司',
        default=lambda self: self.env.company,
        required=True,
    )
    currency_id = fields.Many2one(
        related='company_id.currency_id',
        string='货币',
        readonly=True,
    )
    is_small_profit = fields.Boolean(
        related='company_id.cn_is_small_profit',
        string='小型微利企业',
        readonly=False,
    )

    # --- 利润计算 ---
    total_income = fields.Float(string='累计收入总额', digits=(16, 2), readonly=True)
    total_expense = fields.Float(string='累计成本费用总额', digits=(16, 2), readonly=True)
    cumulative_profit = fields.Float(string='累计利润总额', digits=(16, 2), readonly=True)

    # --- 税额计算 ---
    applied_rate = fields.Float(string='适用税率 (%)', digits=(5, 2), readonly=True)
    cumulative_tax = fields.Float(string='累计应纳企业所得税', digits=(16, 2), readonly=True)
    paid_tax = fields.Float(
        string='前期已缴税额',
        digits=(16, 2),
        default=0.0,
        help='本年度之前季度已实际缴纳的企业所得税预缴金额。',
    )
    prepayment_amount = fields.Float(string='本期应预缴税额', digits=(16, 2), readonly=True)

    is_computed = fields.Boolean(default=False)

    @api.depends('fiscal_year', 'quarter')
    def _compute_dates(self):
        for rec in self:
            year = rec.fiscal_year or date.today().year
            q = rec.quarter or _current_quarter()
            _m_from, _d_from, m_to, d_to = _QUARTER_DATES[q]
            rec.date_from = date(year, 1, 1)
            rec.date_to = date(year, m_to, d_to)

    def action_compute(self):
        self.ensure_one()
        company = self.company_id
        date_from = self.date_from
        date_to = self.date_to

        # Income: posted outgoing invoice lines (revenue accounts, type = income)
        income_lines = self.env['account.move.line'].search([
            ('company_id', '=', company.id),
            ('move_id.state', '=', 'posted'),
            ('move_id.move_type', 'in', ['out_invoice', 'out_refund']),
            ('date', '>=', date_from),
            ('date', '<=', date_to),
            ('account_id.account_type', 'in', ['income', 'income_other']),
            ('tax_line_id', '=', False),
        ])
        total_income = 0.0
        for line in income_lines:
            sign = 1.0 if line.move_id.move_type == 'out_invoice' else -1.0
            total_income += sign * (-line.balance)

        # Expenses: posted purchase/vendor bill lines (expense accounts)
        expense_lines = self.env['account.move.line'].search([
            ('company_id', '=', company.id),
            ('move_id.state', '=', 'posted'),
            ('move_id.move_type', 'in', ['in_invoice', 'in_refund', 'entry']),
            ('date', '>=', date_from),
            ('date', '<=', date_to),
            ('account_id.account_type', 'in', ['expense', 'expense_depreciation', 'expense_direct_cost']),
            ('tax_line_id', '=', False),
        ])
        total_expense = 0.0
        for line in expense_lines:
            total_expense += line.balance

        cumulative_profit = total_income - total_expense

        # Estimate annual profit by annualising the cumulative profit
        q = self.quarter
        months_elapsed = {'q1': 3, 'q2': 6, 'q3': 9, 'q4': 12}[q]
        annual_estimate = cumulative_profit * 12.0 / months_elapsed if months_elapsed else cumulative_profit

        rate = _calc_cit_rate(annual_estimate, self.is_small_profit)
        cumulative_tax = max(0.0, cumulative_profit * rate)
        prepayment = max(0.0, cumulative_tax - self.paid_tax)

        self.write({
            'total_income': total_income,
            'total_expense': total_expense,
            'cumulative_profit': cumulative_profit,
            'applied_rate': rate * 100,
            'cumulative_tax': cumulative_tax,
            'prepayment_amount': prepayment,
            'is_computed': True,
        })

        _logger.info(
            'CIT prepayment computed: company=%s, period=%s~%s, profit=%.2f, rate=%.0f%%, prepayment=%.2f',
            company.name, date_from, date_to, cumulative_profit, rate * 100, prepayment,
        )

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
