from odoo import models, fields, api

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    project_name = fields.Char(string='对应项目', help="例如：华为P70模切专案")
    is_urgent = fields.Boolean(string='是否加急', default=False)


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    product_spec = fields.Char(string='规格')

    @api.onchange('product_id')
    def _onchange_product_id_spec(self):
        try:
            if self.product_id and self.product_id.is_raw_material:
                # Use robust access
                t = self.product_id.thickness or 0
                w = self.product_id.width or 0
                l_val = self.product_id.length or 0 
                
                rs_type = self.product_id.rs_type or 'R'
                
                if rs_type == 'S':
                    l_mm = l_val * 1000.0
                    self.product_spec = f"{t:g}mm * {w:g}mm * {l_mm:g}mm"
                else:
                    self.product_spec = f"{t:g}mm * {w:g}mm * {l_val:g}M"
            else:
                self.product_spec = ""
        except Exception as e:
            # Fallback in case of any detailed error during catalog quick-add
            self.product_spec = ""
