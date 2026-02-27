
from odoo import models, fields, api

import logging
_logger = logging.getLogger(__name__)

class MyMaterialRequisition(models.Model):
    _name = 'my.material.requisition'
    _description = '领料演示'
    _rec_name = 'material_id'

    material_id = fields.Many2one('product.product', string='选择材料', required=True, domain="[('is_raw_material', '=', True)]")
    
    # Auto-filled fields
    spec = fields.Char(string='规格型号', readonly=True)
    thickness = fields.Float(string='厚度 (mm)', digits=(16, 4), readonly=True)
    width = fields.Float(string='宽度', digits=(16, 4), readonly=True)
    length = fields.Float(string='长度 (M)', digits=(16, 4), readonly=True)
    # uom = fields.Char(string='计量单位', readonly=True) # Product uses uom_id
    uom_name = fields.Char(string='计量单位', readonly=True)
    unit_price = fields.Float(string='参考单价', digits='Product Price', readonly=True)
    
    # Transaction fields
    quantity = fields.Float(string='领用数量', default=1.0)
    total_price = fields.Float(string='总预估价', compute='_compute_total_price')

    @api.onchange('material_id')
    def _onchange_material_id(self):
        if self.material_id:
            self.spec = self.material_id.spec
            self.thickness = self.material_id.thickness
            self.width = self.material_id.width
            self.length = self.material_id.length
            self.uom_name = self.material_id.uom_id.name
            # 底层统一按平米计价，领料参考价也以 m² 单价为准
            self.unit_price = self.material_id.raw_material_price_m2 or self.material_id.standard_price

    @api.depends('quantity', 'unit_price')
    def _compute_total_price(self):
        for record in self:
            record.total_price = record.quantity * record.unit_price

