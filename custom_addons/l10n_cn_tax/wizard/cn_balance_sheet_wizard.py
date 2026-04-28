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


class CnBalanceSheetWizard(models.TransientModel):
    _name = 'l10n_cn_tax.balance.sheet'
    _description = '资产负债表（小企业会计准则）'

    company_id = fields.Many2one('res.company', string='公司',
                                  default=lambda self: self.env.company, required=True)
    fiscal_year = fields.Integer(string='会计年度', default=lambda self: date.today().year)
    quarter = fields.Selection([
        ('q1', '第一季度 (1-3月)'),
        ('q2', '第二季度 (4-6月)'),
        ('q3', '第三季度 (7-9月)'),
        ('q4', '第四季度 (10-12月)'),
    ], string='报表期间', default=lambda self: _current_quarter(), required=True)
    as_of_date = fields.Date(string='报表基准日', compute='_compute_as_of_date',
                              store=True, readonly=False)
    currency_id = fields.Many2one(related='company_id.currency_id', readonly=True)
    is_computed = fields.Boolean(default=False)

    # 流动资产
    monetary_funds = fields.Float('货币资金', digits=(16, 2))
    short_term_investment = fields.Float('短期投资', digits=(16, 2))
    notes_receivable = fields.Float('应收票据', digits=(16, 2))
    accounts_receivable = fields.Float('应收账款', digits=(16, 2))
    prepayments = fields.Float('预付账款', digits=(16, 2))
    dividend_receivable = fields.Float('应收股利', digits=(16, 2))
    interest_receivable = fields.Float('应收利息', digits=(16, 2))
    other_receivables = fields.Float('其他应收款', digits=(16, 2))
    inventories = fields.Float('存货', digits=(16, 2))
    other_current_assets = fields.Float('其他流动资产', digits=(16, 2))
    total_current_assets = fields.Float('流动资产合计', digits=(16, 2))

    # 非流动资产
    long_term_equity_inv = fields.Float('长期股权投资', digits=(16, 2))
    fixed_assets_net = fields.Float('固定资产净值', digits=(16, 2))
    construction_in_progress = fields.Float('在建工程', digits=(16, 2))
    disposal_fixed_assets = fields.Float('固定资产清理', digits=(16, 2))
    intangible_assets_net = fields.Float('无形资产净值', digits=(16, 2))
    long_term_deferred_exp = fields.Float('长期待摊费用', digits=(16, 2))
    other_non_current_assets = fields.Float('其他非流动资产', digits=(16, 2))
    total_non_current_assets = fields.Float('非流动资产合计', digits=(16, 2))
    total_assets = fields.Float('资产总计', digits=(16, 2))

    # 流动负债
    short_term_loans = fields.Float('短期借款', digits=(16, 2))
    notes_payable = fields.Float('应付票据', digits=(16, 2))
    accounts_payable = fields.Float('应付账款', digits=(16, 2))
    advance_from_customers = fields.Float('预收账款', digits=(16, 2))
    payroll_payable = fields.Float('应付职工薪酬', digits=(16, 2))
    tax_payable = fields.Float('应交税费', digits=(16, 2))
    interest_payable = fields.Float('应付利息', digits=(16, 2))
    profit_payable = fields.Float('应付利润', digits=(16, 2))
    other_payables = fields.Float('其他应付款', digits=(16, 2))
    other_current_liab = fields.Float('其他流动负债', digits=(16, 2))
    total_current_liab = fields.Float('流动负债合计', digits=(16, 2))

    # 非流动负债
    long_term_loans = fields.Float('长期借款', digits=(16, 2))
    long_term_payables = fields.Float('长期应付款', digits=(16, 2))
    deferred_income = fields.Float('递延收益', digits=(16, 2))
    other_non_current_liab = fields.Float('其他非流动负债', digits=(16, 2))
    total_non_current_liab = fields.Float('非流动负债合计', digits=(16, 2))
    total_liabilities = fields.Float('负债合计', digits=(16, 2))

    # 所有者权益
    paid_in_capital = fields.Float('实收资本', digits=(16, 2))
    capital_reserve = fields.Float('资本公积', digits=(16, 2))
    surplus_reserve = fields.Float('盈余公积', digits=(16, 2))
    retained_earnings = fields.Float('未分配利润', digits=(16, 2))
    total_equity = fields.Float('所有者权益合计', digits=(16, 2))
    total_liabilities_equity = fields.Float('负债和所有者权益合计', digits=(16, 2))

    @api.depends('fiscal_year', 'quarter')
    def _compute_as_of_date(self):
        for rec in self:
            year = rec.fiscal_year or date.today().year
            q = rec.quarter or _current_quarter()
            m, d = _QUARTER_END[q]
            rec.as_of_date = date(year, m, d)

    def _bal(self, prefixes, date_to, flip=False):
        """
        Return net account balance for the given code prefixes up to date_to.
        flip=True negates the result — use for credit-normal accounts (liabilities, equity)
        so the returned value is positive when the account has a normal credit balance.
        """
        if not prefixes:
            return 0.0
        domain = [
            ('company_id', '=', self.company_id.id),
            ('move_id.state', '=', 'posted'),
            ('date', '<=', date_to),
        ]
        conds = [('account_id.code', '=like', p + '%') for p in prefixes]
        domain += (['|'] * (len(conds) - 1) + conds) if len(conds) > 1 else conds
        lines = self.env['account.move.line'].search(domain)
        balance = sum(lines.mapped('balance'))
        return -balance if flip else balance

    def action_compute(self):
        self.ensure_one()
        d = self.as_of_date
        b = self._bal

        # 流动资产
        monetary_funds = b(['1001', '1002', '1012'], d)
        short_term_investment = b(['1101'], d)
        notes_receivable = b(['1121'], d)
        accounts_receivable = b(['1122'], d)
        prepayments = b(['1123'], d)
        dividend_receivable = b(['1131'], d)
        interest_receivable = b(['1132'], d)
        other_receivables = b(['1221'], d)
        inventories = b(['1401', '1402', '1403', '1404', '1405',
                          '1406', '1407', '1408', '1411', '1421'], d)
        other_current_assets = b(['1231', '1901'], d)
        total_current_assets = (monetary_funds + short_term_investment + notes_receivable +
                                  accounts_receivable + prepayments + dividend_receivable +
                                  interest_receivable + other_receivables +
                                  inventories + other_current_assets)

        # 非流动资产
        # 1602 累计折旧 and 1702 累计摊销 are contra accounts with credit balance
        # (negative in Odoo's balance field), so adding them to gross gives net value
        long_term_equity_inv = b(['1511'], d)
        fixed_assets_net = b(['1601'], d) + b(['1602'], d)
        construction_in_progress = b(['1604', '1605'], d)
        disposal_fixed_assets = b(['1606'], d)
        intangible_assets_net = b(['1701'], d) + b(['1702'], d)
        long_term_deferred_exp = b(['1801'], d)
        other_non_current_assets = b(['1802'], d)
        total_non_current_assets = (long_term_equity_inv + fixed_assets_net +
                                     construction_in_progress + disposal_fixed_assets +
                                     intangible_assets_net + long_term_deferred_exp +
                                     other_non_current_assets)
        total_assets = total_current_assets + total_non_current_assets

        # 流动负债
        short_term_loans = b(['2001'], d, flip=True)
        notes_payable = b(['2201'], d, flip=True)
        accounts_payable = b(['2202'], d, flip=True)
        advance_from_customers = b(['2203'], d, flip=True)
        payroll_payable = b(['2211'], d, flip=True)
        tax_payable = b(['2221'], d, flip=True)
        interest_payable = b(['2231'], d, flip=True)
        profit_payable = b(['2232'], d, flip=True)
        other_payables = b(['2241'], d, flip=True)
        other_current_liab = b(['2301'], d, flip=True)
        total_current_liab = (short_term_loans + notes_payable + accounts_payable +
                               advance_from_customers + payroll_payable + tax_payable +
                               interest_payable + profit_payable + other_payables +
                               other_current_liab)

        # 非流动负债
        long_term_loans = b(['2501'], d, flip=True)
        long_term_payables = b(['2701'], d, flip=True)
        deferred_income = b(['2401'], d, flip=True)
        other_non_current_liab = b(['2801'], d, flip=True)
        total_non_current_liab = (long_term_loans + long_term_payables +
                                   deferred_income + other_non_current_liab)
        total_liabilities = total_current_liab + total_non_current_liab

        # 所有者权益
        paid_in_capital = b(['3001'], d, flip=True)
        capital_reserve = b(['3002'], d, flip=True)
        surplus_reserve = b(['3101'], d, flip=True)
        # 3103 本年利润 + 3104 利润分配 = 未分配利润合计
        retained_earnings = b(['3103', '3104'], d, flip=True)
        total_equity = paid_in_capital + capital_reserve + surplus_reserve + retained_earnings
        total_liabilities_equity = total_liabilities + total_equity

        self.write({
            'monetary_funds': monetary_funds,
            'short_term_investment': short_term_investment,
            'notes_receivable': notes_receivable,
            'accounts_receivable': accounts_receivable,
            'prepayments': prepayments,
            'dividend_receivable': dividend_receivable,
            'interest_receivable': interest_receivable,
            'other_receivables': other_receivables,
            'inventories': inventories,
            'other_current_assets': other_current_assets,
            'total_current_assets': total_current_assets,
            'long_term_equity_inv': long_term_equity_inv,
            'fixed_assets_net': fixed_assets_net,
            'construction_in_progress': construction_in_progress,
            'disposal_fixed_assets': disposal_fixed_assets,
            'intangible_assets_net': intangible_assets_net,
            'long_term_deferred_exp': long_term_deferred_exp,
            'other_non_current_assets': other_non_current_assets,
            'total_non_current_assets': total_non_current_assets,
            'total_assets': total_assets,
            'short_term_loans': short_term_loans,
            'notes_payable': notes_payable,
            'accounts_payable': accounts_payable,
            'advance_from_customers': advance_from_customers,
            'payroll_payable': payroll_payable,
            'tax_payable': tax_payable,
            'interest_payable': interest_payable,
            'profit_payable': profit_payable,
            'other_payables': other_payables,
            'other_current_liab': other_current_liab,
            'total_current_liab': total_current_liab,
            'long_term_loans': long_term_loans,
            'long_term_payables': long_term_payables,
            'deferred_income': deferred_income,
            'other_non_current_liab': other_non_current_liab,
            'total_non_current_liab': total_non_current_liab,
            'total_liabilities': total_liabilities,
            'paid_in_capital': paid_in_capital,
            'capital_reserve': capital_reserve,
            'surplus_reserve': surplus_reserve,
            'retained_earnings': retained_earnings,
            'total_equity': total_equity,
            'total_liabilities_equity': total_liabilities_equity,
            'is_computed': True,
        })

        _logger.info('Balance sheet computed: company=%s, date=%s, assets=%.2f, liab+eq=%.2f',
                     self.company_id.name, d, total_assets, total_liabilities_equity)

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_print(self):
        self.ensure_one()
        return self.env.ref('l10n_cn_tax.action_report_balance_sheet').report_action(self)
