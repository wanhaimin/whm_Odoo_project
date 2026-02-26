from odoo import models, fields, api

class ResPartner(models.Model):
    _inherit = 'res.partner'
    
    short_name = fields.Char(string='简称', help="用于在物料列表或过滤面板中显示以节省空间")

    @api.depends('is_company', 'name', 'parent_id.display_name', 'type', 'company_name', 'short_name')
    @api.depends_context('show_short_name')
    def _compute_display_name(self):
        super()._compute_display_name()
        if self.env.context.get('show_short_name'):
            for partner in self:
                if partner.is_company and partner.short_name:
                    partner.display_name = partner.short_name
