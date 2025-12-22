from odoo import models, fields, api

class MyMaterial(models.Model):
    _name = 'my.material'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'My Material List'
    _rec_name = 'name'

    name = fields.Char(string='材料名', required=True)
    code = fields.Char(string='物料编码', required=True, copy=False, readonly=True, index=True, default=lambda self: 'New')
    
    @api.model_create_multi
    def create(self, vals_list):
        if not isinstance(vals_list, list):
            vals_list = [vals_list]
            
        for vals in vals_list:
            if vals.get('code', 'New') == 'New':
                vals['code'] = self.env['ir.sequence'].next_by_code('my.material.code') or 'New'
        
        return super(MyMaterial, self).create(vals_list)
    
    # Relational Fields
    category_id = fields.Many2one('my.material.category', string='材料类别')
    vendor_id = fields.Many2one('res.partner', string='供应商', domain="[('supplier_rank', '>', 0)]", tracking=True)
    
    # Specifications
    spec = fields.Char(string='规格型号')
    thickness = fields.Float(string='厚度 (mm)', digits=(16, 2))
    width = fields.Float(string='宽度', digits=(16, 0))
    length = fields.Float(string='长度 (M)', digits=(16, 0))
    
    # Pricing & Unit
    uom = fields.Char(string='计量单位')
    unit_price = fields.Float(string='参考单价', digits='Product Price', tracking=True)
    
    description = fields.Text(string='备注')

    # Image
    image_1920 = fields.Image(string='图片')

    # Procurement
    min_order_qty = fields.Float(string='最小起订量 (MOQ)', default=0.0)
    lead_time = fields.Integer(string='采购周期 (天)', default=0)
    purchase_uom = fields.Char(string='采购单位')

    # Inventory
    safety_stock = fields.Float(string='安全库存', tracking=True)
    location = fields.Char(string='存放库位')
    track_batch = fields.Boolean(string='批次管理', default=False)

    # Attributes
    material_type = fields.Char(string='材质/牌号')
    color = fields.Char(string='颜色')
    weight_gram = fields.Float(string='克重 (g)', digits=(16, 2))
