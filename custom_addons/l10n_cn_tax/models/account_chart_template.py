# -*- coding: utf-8 -*-
from odoo import models
from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template('cn', 'account.tax.group')
    def _get_cn_tax_small_scale_groups(self):
        return self._parse_csv('cn', 'account.tax.group', module='l10n_cn_tax')

    @template('cn', 'account.tax')
    def _get_cn_tax_small_scale(self):
        tax_data = self._parse_csv('cn', 'account.tax', module='l10n_cn_tax')
        self._deref_account_tags('cn', tax_data)
        return tax_data
