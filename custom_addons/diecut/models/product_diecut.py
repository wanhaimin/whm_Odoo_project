# -*- coding: utf-8 -*-
from odoo import models, fields, api

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # --- 标志位 ---
    is_raw_material = fields.Boolean(string="是原材料", default=False, help="勾选此项以在原材料库中显示")

    # --- 规格型号 ---
    spec = fields.Char(string='规格型号')
    thickness = fields.Float(string='厚度 (mm)', digits=(16, 3))
    width = fields.Float(string='宽度 (mm)', digits=(16, 0))
    length = fields.Float(string='长度 (M)', digits=(16, 0))
    rs_type = fields.Selection([
        ('R', '卷料'),
        ('S', '片料'),
    ], string='形态(R/S)')

    # --- 物理特征 (合并自 material.py) ---
    color = fields.Char(string='颜色')
    weight_gram = fields.Float(string='克重 (g)', digits=(16, 2))
    material_type = fields.Char(string='材质/牌号')
    brand = fields.Char('品牌')
    origin = fields.Char('产地')
    density = fields.Float('密度(g/cm³)', digits=(10, 3))
    transparency = fields.Selection([
        ('transparent', '透明'),
        ('translucent', '半透明'),
        ('opaque', '不透明'),
    ], string='透明度')

    # --- 性能参数 (合并自 material.py) ---
    tensile_strength = fields.Float('拉伸强度(MPa)', digits=(10, 2))
    tear_strength = fields.Float('撕裂强度(N)', digits=(10, 2))
    temp_resistance_min = fields.Float('耐温下限(℃)')
    temp_resistance_max = fields.Float('耐温上限(℃)')
    adhesion = fields.Float('粘性(N/25mm)', digits=(10, 2))

    # --- 价格信息 (扩展) ---
    raw_material_unit_price = fields.Float(string='原材料单价', digits=(16, 2))
    raw_material_total_price = fields.Float(string='原材料价格（整支）', digits=(16, 2))
    price_tax_excluded = fields.Float(string='单价（不含税）', digits=(16, 4))
    
    price_unit = fields.Char(string='价格单位')
    price_usd = fields.Float(string='常用价格 (USD)', digits=(16, 4))
    price_hkd = fields.Float(string='常用价格 (HKD)', digits=(16, 4))
    price_rmb = fields.Float(string='常用价格 (RMB)', digits=(16, 4))
    price_jpy = fields.Float(string='常用价格 (JPY)', digits=(16, 4))
    
    sales_price_usd = fields.Float(string='营业用价格 (USD)', digits=(16, 4))

    # --- 采购与库存 (扩展) ---
    # 兼容字段，主要用于快速录入。正式流程建议使用 seller_ids
    main_vendor_id = fields.Many2one('res.partner', string='主要供应商', domain="[('supplier_rank', '>', 0)]")
    contact_info = fields.Char(string='联络方式')
    incoterms = fields.Char(string='贸易条款')
    quote_date = fields.Date(string='报价日期')
    
    min_order_qty = fields.Float(string='最小起订量 (MOQ)', default=0.0)
    lead_time = fields.Integer(string='采购周期 (天)', default=0)
    purchase_uom = fields.Char(string='采购单位')
    
    safety_stock = fields.Float(string='安全库存')
    storage_location_str = fields.Char(string='存放库位(字符)', help="简单的文本记录，非原生库位对象")
    track_batch = fields.Boolean(string='批次管理', default=False)

    # --- 文档资料 ---
    datasheet = fields.Binary('规格书')
    datasheet_filename = fields.Char('规格书文件名')
    test_report = fields.Binary('测试报告')
    test_report_filename = fields.Char('测试报告文件名')

    # --- 网站/应用 ---
    application = fields.Text('应用场景', help="用于网站前端展示该材料的典型应用领域")
    process_note = fields.Text('加工工艺说明', help="用于网站前端展示加工建议")
    caution = fields.Text('注意事项')
    
    # 统计字段
    view_count = fields.Integer('浏览次数', default=0, readonly=True)
    inquiry_count = fields.Integer('询价次数', default=0, readonly=True)

    @api.onchange('track_batch')
    def _onchange_track_batch(self):
        """如果开启批次管理，自动设置Odoo原生的追踪字段"""
        if self.track_batch:
            self.tracking = 'lot'
        else:
            self.tracking = 'none'

    def action_open_detail(self):
        """在 editable list 中打开 Form 视图"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'product.template',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }


class ProductSupplierinfo(models.Model):
    _inherit = 'product.supplierinfo'

    # --- 扩展价格字段 ---
    price_per_m2 = fields.Float(string='单价/m²', digits=(16, 4))
    price_per_kg = fields.Float(string='单价/kg', digits=(16, 4))
    
    # 辅助显示，说明当前原生price是基于什么单位
    # 虽然通常跟随产品主单位，但这里明确显示为 "单价/主单位(通常是卷)"
    
    def _get_conversion_factors(self):
        """获取换算系数: 面积(m2/卷), 重量(kg/卷)"""
        self.ensure_one()
        # supplierinfo 关联的是 product_tmpl_id 或 product_id (如果设置了变体)
        product = self.product_tmpl_id
        if self.product_id:
            product = self.product_id
            
        width_mm = product.width or 0.0
        length_m = product.length or 0.0
        
        # 1. 面积 (m2) = 宽(mm)/1000 * 长(m)
        area_m2 = (width_mm / 1000.0) * length_m
        
        # 2. 重量 (kg)
        # 优先使用定义好的 weight_gram (g/m2)
        weight_kg = 0.0
        if area_m2 > 0:
            if product.weight_gram > 0:
                # 总克重 = 面积 * 克重
                weight_kg = (area_m2 * product.weight_gram) / 1000.0
            elif product.density > 0 and product.thickness > 0:
                # 如果没有克重，用密度算: 密度(g/cm3) * 体积
                # 体积(cm3) = 面积(m2)*10000 * 厚度(mm)/10
                # 简化: g/m2 = density * thickness * 1000
                gram_per_m2 = product.density * product.thickness * 1000.0
                weight_kg = (area_m2 * gram_per_m2) / 1000.0
        
        return area_m2, weight_kg

    @api.onchange('price')
    def _onchange_price_roll(self):
        """主单价(卷) 变动 -> 更新 m2 和 kg"""
        for record in self:
            if not record.product_tmpl_id: continue
            
            try:
                area, weight = record._get_conversion_factors()
                
                # Update m2 price
                if area > 0:
                    record.price_per_m2 = record.price / area
                else:
                    record.price_per_m2 = 0.0
                    
                # Update kg price
                if weight > 0:
                    record.price_per_kg = record.price / weight
                else:
                    record.price_per_kg = 0.0
            except Exception:
                pass

    @api.onchange('price_per_m2')
    def _onchange_price_m2(self):
        """m2单价 变动 -> 更新 卷 和 kg"""
        for record in self:
            if not record.product_tmpl_id: continue
            
            try:
                area, weight = record._get_conversion_factors()
                
                # Update Roll price (Main Price)
                if area > 0:
                    record.price = record.price_per_m2 * area
                    
                    # Update kg price derived from new Roll price
                    if weight > 0:
                        record.price_per_kg = record.price / weight
                    else:
                        record.price_per_kg = 0.0
            except Exception:
                pass

    @api.onchange('price_per_kg')
    def _onchange_price_kg(self):
        """kg单价 变动 -> 更新 卷 和 m2"""
        for record in self:
            if not record.product_tmpl_id: continue
            
            try:
                area, weight = record._get_conversion_factors()
                
                # Update Roll price (Main Price)
                if weight > 0:
                    record.price = record.price_per_kg * weight
                    
                    # Update m2 price derived from new Roll price
                    if area > 0:
                        record.price_per_m2 = record.price / area
                    else:
                        record.price_per_m2 = 0.0
            except Exception:
                pass
