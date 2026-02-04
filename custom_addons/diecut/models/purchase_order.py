from odoo import models, fields, api

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    project_name = fields.Char(string='对应项目', help="例如：华为P70模切专案")
    is_urgent = fields.Boolean(string='是否加急', default=False)
