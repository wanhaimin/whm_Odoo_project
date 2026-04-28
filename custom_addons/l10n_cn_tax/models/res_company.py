# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    cn_taxpayer_type = fields.Selection(
        selection=[
            ('small_scale', '小规模纳税人'),
            ('general', '一般纳税人'),
        ],
        string='增值税纳税人类型',
        default='small_scale',
    )
    cn_is_small_profit = fields.Boolean(
        string='小型微利企业',
        default=True,
        help='勾选后，企业所得税预缴向导按小型微利企业优惠税率（≤100万 5%，100-300万 10%）计算。',
    )
    cn_city_tax_rate = fields.Float(
        string='城建税税率 (%)',
        default=7.0,
        help='默认 7%（城区），县城/镇 5%，其他地区 1%。',
    )
