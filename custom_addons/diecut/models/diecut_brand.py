# -*- coding: utf-8 -*-

from odoo import fields, models


class DiecutBrand(models.Model):
    _name = 'diecut.brand'
    _description = '品牌'

    _name_uniq = models.Constraint(
        'UNIQUE(name)',
        '品牌名称必须唯一！',
    )

    name = fields.Char(string='品牌名称', required=True)
