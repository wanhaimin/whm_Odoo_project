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


class VatDeclarationWizard(models.TransientModel):
    _name = 'l10n_cn_tax.vat.declaration'
    _description = '增值税申报汇总'

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
    date_from = fields.Date(string='起始日期', compute='_compute_dates', store=True, readonly=False)
    date_to = fields.Date(string='截止日期', compute='_compute_dates', store=True, readonly=False)

    # --- 纳税人类型（只读，来自公司） ---
    taxpayer_type = fields.Selection(
        related='company_id.cn_taxpayer_type',
        string='纳税人类型',
        readonly=True,
    )
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

    # --- 销售汇总 ---
    taxable_amount = fields.Float(string='不含税销售额', digits=(16, 2), readonly=True)
    vat_amount = fields.Float(string='应纳增值税', digits=(16, 2), readonly=True)
    input_vat_amount = fields.Float(
        string='可抵扣进项税额',
        digits=(16, 2),
        readonly=True,
        help='仅一般纳税人适用',
    )
    net_vat_amount = fields.Float(string='实际应纳增值税', digits=(16, 2), readonly=True)

    # --- 附加税 ---
    city_tax_amount = fields.Float(string='城建税', digits=(16, 2), readonly=True)
    education_surcharge = fields.Float(string='教育费附加', digits=(16, 2), readonly=True)
    local_education_surcharge = fields.Float(string='地方教育费附加', digits=(16, 2), readonly=True)
    total_surcharge = fields.Float(string='附加税合计', digits=(16, 2), readonly=True)

    # --- 合计 ---
    total_payable = fields.Float(string='本期合计应缴税款', digits=(16, 2), readonly=True)

    # --- 状态 ---
    is_computed = fields.Boolean(default=False)

    @api.depends('fiscal_year', 'quarter')
    def _compute_dates(self):
        for rec in self:
            year = rec.fiscal_year or date.today().year
            q = rec.quarter or _current_quarter()
            m_from, d_from, m_to, d_to = _QUARTER_DATES[q]
            rec.date_from = date(year, m_from, d_from)
            rec.date_to = date(year, m_to, d_to)

    def action_compute(self):
        self.ensure_one()
        company = self.company_id
        date_from = self.date_from
        date_to = self.date_to

        moves = self.env['account.move'].search([
            ('company_id', '=', company.id),
            ('move_type', 'in', ['out_invoice', 'out_refund']),
            ('state', '=', 'posted'),
            ('invoice_date', '>=', date_from),
            ('invoice_date', '<=', date_to),
        ])

        total_untaxed = 0.0
        total_output_vat = 0.0

        for move in moves:
            sign = 1.0 if move.move_type == 'out_invoice' else -1.0
            total_untaxed += sign * move.amount_untaxed
            total_output_vat += sign * move.amount_tax

        input_vat = 0.0
        if company.cn_taxpayer_type == 'general':
            in_moves = self.env['account.move'].search([
                ('company_id', '=', company.id),
                ('move_type', 'in', ['in_invoice', 'in_refund']),
                ('state', '=', 'posted'),
                ('invoice_date', '>=', date_from),
                ('invoice_date', '<=', date_to),
            ])
            for move in in_moves:
                sign = 1.0 if move.move_type == 'in_invoice' else -1.0
                input_vat += sign * move.amount_tax

        net_vat = total_output_vat - input_vat
        city_rate = (company.cn_city_tax_rate or 7.0) / 100.0
        city_tax = net_vat * city_rate
        edu_surcharge = net_vat * 0.03
        local_edu = net_vat * 0.02
        total_surcharge = city_tax + edu_surcharge + local_edu

        self.write({
            'taxable_amount': total_untaxed,
            'vat_amount': total_output_vat,
            'input_vat_amount': input_vat,
            'net_vat_amount': net_vat,
            'city_tax_amount': city_tax,
            'education_surcharge': edu_surcharge,
            'local_education_surcharge': local_edu,
            'total_surcharge': total_surcharge,
            'total_payable': net_vat + total_surcharge,
            'is_computed': True,
        })

        _logger.info(
            'VAT declaration computed: company=%s, period=%s~%s, net_vat=%.2f, total=%.2f',
            company.name, date_from, date_to, net_vat, net_vat + total_surcharge,
        )

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
