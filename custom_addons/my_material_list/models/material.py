from xml.etree.ElementPath import xpath_tokenizer
from odoo import models, fields, api, _

class MyMaterial(models.Model):
    _name = 'my.material'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = '材料清单'
    _rec_name = 'name'

    name = fields.Char(string='材料名', required=True)
    code = fields.Char(string='物料编码', required=True, copy=False, readonly=True, index=True, default=lambda self: 'New')
    currency_id = fields.Many2one('res.currency', string='币种', default=lambda self: self.env.company.currency_id)
    
    def write(self, vals):
        res = super(MyMaterial, self).write(vals)
        self._create_or_update_product()
        return res

    @api.model
    def action_sync_all_products(self):
        """Server Action: 手动同步所有材料到产品"""
        materials = self.search([])
        count = 0
        for mat in materials:
            mat._create_or_update_product()
            count += 1
        
        # 自动关闭定时任务 (因为 Odoo 19 移除了 numbercall)
        cron = self.env.ref('my_material_list.ir_cron_sync_materials_to_products', raise_if_not_found=False)
        if cron:
            cron.active = False
            
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('同步完成'),
                'message': _(f'已成功同步 {count} 个材料到库存产品。'),
                'type': 'success',
                'sticky': False,
            }
        }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('code', 'New') == 'New':
                vals['code'] = self.env['ir.sequence'].next_by_code('my.material.code') or 'New'
        
        records = super(MyMaterial, self).create(vals_list) # type: ignore
        for record in records:
            record._create_or_update_product()
        return records

    # Link to Odoo Product
    product_id = fields.Many2one('product.product', string='关联库存产品', readonly=True, help="自动生成的Odoo标准产品，用于采购和库存管理")

    def _create_or_update_product(self):
        """同步创建或更新 product.product"""
        for record in self:
            vals = {
                'name': record.name,
                'default_code': record.code,
                'type': 'consu', # Odoo 19: Goods (Storable/Consumable depends on tracking?) setting as 'consu' (Goods)
                'tracking': 'lot' if record.track_batch else 'none',
                'standard_price': record.raw_material_unit_price,
                'purchase_ok': True,
                'sale_ok': True, # 原材料对应采购和销售
            }
            
            # 尝试映射单位
            if record.uom:
                uom = self.env['uom.uom'].search([('name', '=', record.uom)], limit=1)
                if uom:
                    vals['uom_id'] = uom.id
                    vals['uom_po_id'] = uom.id

            if not record.product_id:
                product = self.env['product.product'].create(vals)
                record.product_id = product.id
            else:
                record.product_id.write(vals)
            
            # 同步供应商信息 (简单的添加逻辑，不重复添加)
            if record.vendor_id:
                # 检查是否已存在该供应商
                existing_seller = record.product_id.seller_ids.filtered(lambda s: s.partner_id == record.vendor_id)
                if not existing_seller:
                     self.env['product.supplierinfo'].create({
                         'product_tmpl_id': record.product_id.product_tmpl_id.id,
                         'partner_id': record.vendor_id.id,
                         'price': record.raw_material_unit_price,
                         'min_qty': record.min_order_qty,
                         'delay': record.lead_time,
                     })
    
    # Relational Fields
    category_id = fields.Many2one('my.material.category', string='材料类别')
    vendor_id = fields.Many2one('res.partner', string='供应商', domain="[('supplier_rank', '>', 0)]", tracking=True)
    contact_info = fields.Char(string='联络方式')
    incoterms = fields.Char(string='贸易条款')
    quote_date = fields.Date(string='报价日期')
    
   
    
    

    # Specifications
    spec = fields.Char(string='规格型号')
    thickness = fields.Float(string='厚度 (mm)', digits=(16, 3))
    width = fields.Float(string='宽度 (mm)', digits=(16, 0))
    length = fields.Float(string='长度 (M)', digits=(16, 0))
    
    # Pricing & Unit
    uom = fields.Char(string='计量单位')
    unit_price = fields.Float(string='参考单价', digits='Product Price', tracking=True)
    
    raw_material_unit_price = fields.Float(string='原材料单价', digits=(16, 2))
    raw_material_total_price = fields.Float(string='原材料价格（整支）', digits=(16, 2))
    price_tax_excluded = fields.Float(string='单价（不含税）', digits=(16, 4))
    
    price_unit = fields.Char(string='价格单位')
    price_usd = fields.Float(string='常用价格 (USD)', digits=(16, 4))
    price_hkd = fields.Float(string='常用价格 (HKD)', digits=(16, 4))
    price_rmb = fields.Float(string='常用价格 (RMB)', digits=(16, 4))
    price_jpy = fields.Float(string='常用价格 (JPY)', digits=(16, 4))
    
    sales_price_usd = fields.Float(string='营业用价格 (USD)', digits=(16, 4))
    
    rs_type = fields.Selection([
        ('R', '卷料'),
        ('S', '片料'),
    ], string='形态(R/S)')

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

    