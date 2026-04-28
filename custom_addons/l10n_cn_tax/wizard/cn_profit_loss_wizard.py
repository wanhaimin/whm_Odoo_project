# -*- coding: utf-8 -*-
import logging
from datetime import date

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

_QUARTER_END = {'q1': (3, 31), 'q2': (6, 30), 'q3': (9, 30), 'q4': (12, 31)}


def _current_quarter():
    m = date.today().month
    if m <= 3: return 'q1'
    if m <= 6: return 'q2'
    if m <= 9: return 'q3'
    return 'q4'


class CnProfitLossWizard(models.TransientModel):
    _name = 'l10n_cn_tax.profit.loss'
    _description = '利润表（小企业会计准则）'

    company_id = fields.Many2one('res.company', string='公司',
                                  default=lambda self: self.env.company, required=True)
    fiscal_year = fields.Integer(string='会计年度', default=lambda self: date.today().year)
    quarter = fields.Selection([
        ('q1', '第一季度 (1-3月)'),
        ('q2', '第二季度 (4-6月)'),
        ('q3', '第三季度 (7-9月)'),
        ('q4', '第四季度 (10-12月)'),
    ], string='报表期间', default=lambda self: _current_quarter(), required=True)
    date_from = fields.Date(string='期间起始（年初）', compute='_compute_dates',
                             store=True, readonly=False)
    date_to = fields.Date(string='期间截止', compute='_compute_dates',
                           store=True, readonly=False)
    currency_id = fields.Many2one(related='company_id.currency_id', readonly=True)
    is_computed = fields.Boolean(default=False)

    # 利润表行项
    operating_revenue = fields.Float('一、营业收入', digits=(16, 2))
    operating_cost = fields.Float('减：营业成本', digits=(16, 2))
    business_tax_surcharge = fields.Float('营业税金及附加', digits=(16, 2))
    selling_expenses = fields.Float('销售费用', digits=(16, 2))
    admin_expenses = fields.Float('管理费用', digits=(16, 2))
    financial_expenses = fields.Float('财务费用', digits=(16, 2))
    investment_income = fields.Float('加：投资收益', digits=(16, 2))
    operating_profit = fields.Float('二、营业利润', digits=(16, 2))
    non_operating_income = fields.Float('加：营业外收入', digits=(16, 2))
    non_operating_expenses = fields.Float('减：营业外支出', digits=(16, 2))
    total_profit = fields.Float('三、利润总额', digits=(16, 2))
    income_tax_expense = fields.Float('减：所得税费用', digits=(16, 2))
    net_profit = fields.Float('四、净利润', digits=(16, 2))

    @api.depends('fiscal_year', 'quarter')
    def _compute_dates(self):
        for rec in self:
            year = rec.fiscal_year or date.today().year
            q = rec.quarter or _current_quarter()
            m, d = _QUARTER_END[q]
            rec.date_from = date(year, 1, 1)
            rec.date_to = date(year, m, d)

    def _bal(self, prefixes, date_from, date_to, flip=False):
        """
        Return net account balance for the given code prefixes within the period.
        flip=True negates the result — use for credit-normal accounts (revenue, other income)
        so the returned value is positive when the account has a normal credit balance.
        """
        if not prefixes:
            return 0.0
        domain = [
            ('company_id', '=', self.company_id.id),
            ('move_id.state', '=', 'posted'),
            ('date', '>=', date_from),
            ('date', '<=', date_to),
        ]
        conds = [('account_id.code', '=like', p + '%') for p in prefixes]
        domain += (['|'] * (len(conds) - 1) + conds) if len(conds) > 1 else conds
        lines = self.env['account.move.line'].search(domain)
        balance = sum(lines.mapped('balance'))
        return -balance if flip else balance

    def action_compute(self):
        self.ensure_one()
        df = self.date_from
        dt = self.date_to
        b = self._bal

        # Revenue — credit normal → flip=True for positive display
        operating_revenue = b(['5001', '5051'], df, dt, flip=True)
        # Expenses — debit normal → flip=False
        operating_cost = b(['5401', '5402'], df, dt)
        business_tax_surcharge = b(['5403'], df, dt)
        selling_expenses = b(['5601'], df, dt)
        admin_expenses = b(['5602'], df, dt)
        financial_expenses = b(['5603'], df, dt)
        # Investment income — credit normal
        investment_income = b(['5111'], df, dt, flip=True)

        operating_profit = (operating_revenue - operating_cost - business_tax_surcharge -
                             selling_expenses - admin_expenses - financial_expenses +
                             investment_income)

        non_operating_income = b(['5301'], df, dt, flip=True)
        non_operating_expenses = b(['5711'], df, dt)
        total_profit = operating_profit + non_operating_income - non_operating_expenses

        income_tax_expense = b(['5801'], df, dt)
        net_profit = total_profit - income_tax_expense

        self.write({
            'operating_revenue': operating_revenue,
            'operating_cost': operating_cost,
            'business_tax_surcharge': business_tax_surcharge,
            'selling_expenses': selling_expenses,
            'admin_expenses': admin_expenses,
            'financial_expenses': financial_expenses,
            'investment_income': investment_income,
            'operating_profit': operating_profit,
            'non_operating_income': non_operating_income,
            'non_operating_expenses': non_operating_expenses,
            'total_profit': total_profit,
            'income_tax_expense': income_tax_expense,
            'net_profit': net_profit,
            'is_computed': True,
        })

        _logger.info('P&L computed: company=%s, period=%s~%s, revenue=%.2f, net_profit=%.2f',
                     self.company_id.name, df, dt, operating_revenue, net_profit)

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_print(self):
        self.ensure_one()
        return self.env.ref('l10n_cn_tax.action_report_profit_loss').report_action(self)
