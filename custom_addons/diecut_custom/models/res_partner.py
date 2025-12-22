from odoo import models, fields

class ResPartner(models.Model):
    _inherit = 'res.partner'
    
    # 合作伙伴类型
    partner_type = fields.Selection([
        ('customer', '客户'),
        ('supplier', '供应商'),
        ('both', '客户和供应商'),
    ], string='合作伙伴类型', help='明确标识这个联系人是客户还是供应商')
