# -*- coding: utf-8 -*-
from datetime import date
from odoo import models, fields, api

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # --- 标志位 ---
    is_raw_material = fields.Boolean(string="是原材料", default=False)

    @api.onchange('is_raw_material')
    def _onchange_is_raw_material(self):
        """智能默认设置：是原材料 -> 默认可采购、不可销售（但允许用户手动改回）"""
        if self.is_raw_material:
            self.purchase_ok = True
            self.sale_ok = False
        else:
            # 如果取消勾选，通常意味着是成品，默认可销售
            # 但不强制 purchase_ok=False，因为成品也可能外购
            self.sale_ok = True

    # --- 规格型号 ---
    spec = fields.Char(string='规格型号')
    thickness = fields.Float(string='厚度 (mm)', digits=(16, 3))
    width = fields.Float(string='宽度 (mm)', digits=(16, 0))
    length = fields.Float(string='长度 (M)', digits=(16, 3), help="后台统一存储为米")
    length_mm = fields.Float(string='长度 (mm)', compute='_compute_length_mm', inverse='_inverse_length_mm', digits=(16, 0))
    length_smart = fields.Char(string='长度', compute='_compute_length_smart', inverse='_inverse_length_smart', store=True, readonly=False)

    # Temporary fix for migration error: invalid input syntax for type integer: "黑色"
    # This prevents Odoo from trying to convert the existing Char column (containing "黑色") to Integer.
    color = fields.Char(string='Color Fix')

    rs_type = fields.Selection([
        ('R', '卷料'),
        ('S', '片料'),
    ], string='形态(R/S)', default='R')

    @api.depends('length')
    def _compute_length_mm(self):
        for record in self:
            record.length_mm = (record.length or 0.0) * 1000.0

    def _inverse_length_mm(self):
        for record in self:
            record.length = (record.length_mm or 0.0) / 1000.0
    @api.depends('length', 'rs_type')
    def _compute_length_smart(self):
        for record in self:
            l = record.length or 0.0
            if record.rs_type == 'S':
                record.length_smart = f"{l*1000:g} mm"
            else:
                record.length_smart = f"{l:g} m"

    def _inverse_length_smart(self):
        for record in self:
            if not record.length_smart: continue
            # 强化清洗逻辑：移除 'mm', 'm', 空格 以及 逗号(千分位)
            val_str = record.length_smart.lower().replace('mm', '').replace('m', '').replace(' ', '').replace(',', '')
            try:
                val_float = float(val_str)
                record.length = (val_float / 1000.0) if record.rs_type == 'S' else val_float
            except ValueError:
                pass

    # --- 物理特征 ---
    material_color = fields.Char('颜色')
    weight_gram = fields.Float(string='克重 (g)', digits=(16, 2))
    material_type = fields.Char(string='材质/牌号')
    brand = fields.Char('品牌')
    origin = fields.Char('产地')
    density = fields.Float('密度(g/cm³)', digits=(10, 3))
    material_transparency = fields.Selection([
        ('transparent', '透明'), ('translucent', '半透明'), ('opaque', '不透明'),
    ], string='透明度')

    # --- 性能参数 ---
    tensile_strength = fields.Float('拉伸强度(MPa)', digits=(10, 2))
    tear_strength = fields.Float('撕裂强度(N)', digits=(10, 2))
    temp_resistance_min = fields.Float('耐温下限(℃)')
    temp_resistance_max = fields.Float('耐温上限(℃)')
    adhesion = fields.Float('粘性(N/25mm)', digits=(10, 2))

    # --- 价格信息 ---
    raw_material_currency_id = fields.Many2one('res.currency', string="成本币种", default=lambda self: self.env.company.currency_id, compute='_compute_main_vendor_costs', store=True, readonly=False)
    raw_material_unit_price = fields.Monetary(string='原材料单价', currency_field='raw_material_currency_id', compute='_compute_main_vendor_costs', inverse='_inverse_raw_material_unit_price', store=True, readonly=False)
    raw_material_price_m2 = fields.Float(string='单价/m²', digits=(16, 2), compute='_compute_main_vendor_costs', inverse='_inverse_raw_material_price_m2', store=True, readonly=False)
    price_tax_excluded = fields.Float(string='单价（不含税）', digits=(16, 2))
    price_unit = fields.Char(string='价格单位')
    price_usd = fields.Float(string='常用价格 (USD)', digits=(16, 4))
    price_hkd = fields.Float(string='常用价格 (HKD)', digits=(16, 4))
    price_rmb = fields.Float(string='常用价格 (RMB)', digits=(16, 4))
    price_jpy = fields.Float(string='常用价格 (JPY)', digits=(16, 4))
    sales_price_usd = fields.Float(string='营业用价格 (USD)', digits=(16, 4))

    # --- 采购与库存 ---
    main_vendor_id = fields.Many2one('res.partner', string='主要供应商')
    contact_info = fields.Char(string='联络方式')
    incoterms = fields.Char(string='贸易条款')
    quote_date = fields.Date(string='报价日期')
    min_order_qty = fields.Float(string='最小起订量 (MOQ)', compute='_compute_main_vendor_costs', store=True, readonly=False)
    lead_time = fields.Integer(string='采购周期 (天)', compute='_compute_main_vendor_costs', store=True, readonly=False)
    purchase_uom = fields.Char(string='采购单位')
    safety_stock = fields.Float(string='安全库存')
    storage_location_str = fields.Char(string='存放库位(字符)')
    track_batch = fields.Boolean(string='批次管理', default=False)
    datasheet = fields.Binary('规格书')
    datasheet_filename = fields.Char('规格书文件名')
    test_report = fields.Binary('测试报告')
    test_report_filename = fields.Char('测试报告文件名')
    application = fields.Text('应用场景')
    process_note = fields.Text('加工工艺说明')
    caution = fields.Text('注意事项')
    view_count = fields.Integer('浏览次数', default=0, readonly=True)
    inquiry_count = fields.Integer('询价次数', default=0, readonly=True)

    def action_open_detail(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'product.template',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _get_diecut_factors(self):
        self.ensure_one()
        # 1. 统一转换：宽度永远是 mm -> m
        w_m = (self.width or 0.0) / 1000.0
        
        # 2. 智能获取长度：
        # 弃用 length_mm，因为它有 update 延迟。直接读取实时的 length。
        # 增加防御逻辑：其如果是片料(S)且值 > 10 (常理片料不超10米)，说明存的是毫米，我们帮它除1000
        raw_len = self.length or 0.0
        if self.rs_type == 'S' and raw_len > 10:
             l_m = raw_len / 1000.0
        else:
             l_m = raw_len

        area = w_m * l_m
        weight = 0.0
        if area > 0:
            if self.weight_gram > 0:
                weight = (area * self.weight_gram) / 1000.0
            elif self.density > 0 and self.thickness > 0:
                weight = (area * self.density * self.thickness * 1000.0) / 1000.0
        return area, weight

    @api.depends('seller_ids.price', 'seller_ids.price_per_m2', 'seller_ids.partner_id', 'main_vendor_id', 'seller_ids.currency_id', 'seller_ids.delay', 'seller_ids.min_qty')
    def _compute_main_vendor_costs(self):
        for product in self:
            product.raw_material_unit_price = 0.0
            product.raw_material_price_m2 = 0.0
            product.min_order_qty = 0.0
            product.lead_time = 0
            if not product.main_vendor_id: continue
            for seller in product.seller_ids:
                if seller.partner_id == product.main_vendor_id:
                    product.raw_material_unit_price = seller.price
                    product.raw_material_price_m2 = seller.price_per_m2
                    product.raw_material_currency_id = seller.currency_id
                    product.lead_time = seller.delay
                    product.min_order_qty = seller.min_qty
                    break

    def _inverse_raw_material_unit_price(self):
        for product in self:
            if not product.main_vendor_id or not product.seller_ids: continue
            
            # 找到主供应商的记录
            main_seller = product.seller_ids.filtered(lambda s: s.partner_id == product.main_vendor_id)
            if main_seller:
                seller = main_seller[0]
                
                # Update seller price from the product field
                seller.price = product.raw_material_unit_price

                # Re-calculate derivatives (m2, kg) to keep consistency
                area, weight = product._get_diecut_factors()
                
                if area > 0:
                    seller.price_per_m2 = seller.price / area
                
                if weight > 0:
                    seller.price_per_kg = seller.price / weight

    def _inverse_raw_material_price_m2(self):
        for product in self:
            if not product.main_vendor_id or not product.seller_ids: continue
            
            main_seller = product.seller_ids.filtered(lambda s: s.partner_id == product.main_vendor_id)
            if main_seller:
                seller = main_seller[0]
                
                # Update seller m2 price
                seller.price_per_m2 = product.raw_material_price_m2
                
                # Recalculate total price based on area
                area, weight = product._get_diecut_factors()
                if area > 0:
                     seller.price = seller.price_per_m2 * area
                     seller.price_per_kg = (seller.price / weight) if weight > 0 else 0.0

    @api.onchange('raw_material_unit_price')
    def _onchange_raw_material_unit_price_ui(self):
        """UI联动：修改总价 -> 反算单价/m² (仅做前端显示更新，保存时由inverse处理数据库)"""
        for product in self:
            area, _ = product._get_diecut_factors()
            if area > 0:
                product.raw_material_price_m2 = product.raw_material_unit_price / area

    @api.onchange('raw_material_price_m2')
    def _onchange_raw_material_price_m2_ui(self):
        """UI联动：修改单价/m² -> 反算总价 (仅做前端显示更新，保存时由inverse处理数据库)"""
        for product in self:
            area, _ = product._get_diecut_factors()
            if area > 0:
                product.raw_material_unit_price = product.raw_material_price_m2 * area

    @api.onchange('length_smart')
    def _onchange_length_smart_ui(self):
        """UI联动：修改智能长度 -> 1.解析为数字 -> 2.强制触发价格重算"""
        # 1. 解析字符串到 self.length
        self._inverse_length_smart()
        # 2. 手动链路：因为在 onchange 中间接修改字段有时不会自动通过监听触发后续逻辑，这里显式调用价格计算
        self._onchange_specs_force_update_sellers()

    @api.onchange('width', 'length', 'rs_type', 'weight_gram', 'density', 'thickness', 'length_mm')
    def _onchange_specs_force_update_sellers(self):
        """核心反馈：改规格 -> 保持平米单价 -> 刷卷/片价"""
        for product in self:
            w_m = (product.width or 0.0) / 1000.0

            # 2. 获取最实时的长度 (m)
            raw_len_mm = product.length_mm or 0.0
            l_m = raw_len_mm / 1000.0

            # 回写 length 供调试和保存
            product.length = l_m

            # 3. 就地计算面积
            area = w_m * l_m

            # 4. 就地计算重量
            weight = 0.0
            if area > 0:
                if product.weight_gram > 0:
                    weight = (area * product.weight_gram) / 1000.0
                elif product.density > 0 and product.thickness > 0:
                    weight = (area * product.density * product.thickness * 1000.0) / 1000.0

            if area <= 0: continue

            # 5. 更新子表
            for seller in product.seller_ids:
                # 关键：推送最新面积到缓存
                seller.calc_area_cache = area
                
                # 安全处理：仅当 calc_weight_cache 存在时才赋值
                if hasattr(seller, 'calc_weight_cache'):
                    seller.calc_weight_cache = weight
                else:
                    # 若字段不存在，可考虑动态添加或跳过
                    continue

                # 确保 price_per_m2 存在再计算
                if seller.price_per_m2 > 0:
                    new_roll_price = seller.price_per_m2 * area
                    seller.price = new_roll_price
                    seller.price_per_kg = (new_roll_price / weight) if weight > 0 else 0.0

    @api.onchange('track_batch')
    def _onchange_track_batch(self):
        self.tracking = 'lot' if self.track_batch else 'none'

    @api.model_create_multi
    def create(self, vals_list):
        records = super(ProductTemplate, self).create(vals_list)
        for record in records:
            if record.is_raw_material and record.main_vendor_id:
                # 检查供应商列表是否已有该供应商
                existing = record.seller_ids.filtered(lambda s: s.partner_id == record.main_vendor_id)
                if not existing:
                    area, weight = record._get_diecut_factors()
                    self.env['product.supplierinfo'].create({
                        'product_tmpl_id': record.id,
                        'partner_id': record.main_vendor_id.id,
                        'price': record.raw_material_unit_price or 0.0,
                        'price_per_m2': record.raw_material_price_m2 or 0.0,
                        'currency_id': record.raw_material_currency_id.id or self.env.company.currency_id.id,
                        'delay': record.lead_time or 0,
                        'min_qty': record.min_order_qty or 0.0,
                        'calc_area_cache': area,
                        'calc_weight_cache': weight,
                    })
        return records

    def write(self, vals):
        res = super(ProductTemplate, self).write(vals)
        for record in self:
            if not record.is_raw_material:
                continue

            main_vendor_id = vals.get('main_vendor_id', record.main_vendor_id.id)
            if not main_vendor_id:
                continue
            main_vendor = self.env['res.partner'].browse(main_vendor_id)

            price = vals.get('raw_material_unit_price', record.raw_material_unit_price) or 0.0
            price_per_m2 = vals.get('raw_material_price_m2', record.raw_material_price_m2) or 0.0
            currency_id = vals.get('raw_material_currency_id', record.raw_material_currency_id.id or self.env.company.currency_id.id)
            delay = vals.get('lead_time', record.lead_time) or 0
            min_qty = vals.get('min_order_qty', record.min_order_qty) or 0.0

            seller = record.seller_ids.filtered(lambda s: s.partner_id == main_vendor)
            area, weight = record._get_diecut_factors()
            if not seller:
                self.env['product.supplierinfo'].create({
                    'product_tmpl_id': record.id,
                    'partner_id': main_vendor.id,
                    'price': price,
                    'price_per_m2': price_per_m2,
                    'currency_id': currency_id,
                    'delay': delay,
                    'min_qty': min_qty,
                    'calc_area_cache': area,
                    'calc_weight_cache': weight,
                })
                continue

            seller = seller[0]
            seller.write({
                'price': price,
                'price_per_m2': price_per_m2,
                'currency_id': currency_id,
                'delay': delay,
                'min_qty': min_qty,
                'calc_area_cache': area,
                'calc_weight_cache': weight,
            })
        return res


class ProductSupplierinfo(models.Model):
    _inherit = 'product.supplierinfo'

    price_per_m2 = fields.Float(string='单价/m²', digits=(16, 2))
    price_per_kg = fields.Float(string='单价/kg', digits=(16, 2))
    is_main_vendor = fields.Boolean(compute='_compute_is_main_vendor', string="是否主选")
    
    # 影子字段：接收父表实时传递过来的最新面积（解决未保存时的上下文隔离问题）
    # 当父表触发onchange时，将算好的面积写入此字段，子表计算优先读它
    calc_area_cache = fields.Float(string="实时面积缓存", default=0.0)

    # 新增：重量缓存
    calc_weight_cache = fields.Float(string="实时重量缓存", default=0.0)

    @api.depends('product_tmpl_id.main_vendor_id', 'partner_id')
    def _compute_is_main_vendor(self):
        for record in self:
            record.is_main_vendor = bool(record.product_tmpl_id and record.partner_id and record.partner_id == record.product_tmpl_id.main_vendor_id)
    
    @api.onchange('price')
    def _onchange_price_roll(self):
        for record in self:
            # 优先读缓存，没有缓存才去读父表(可能读到旧值)
            db_area, db_weight = record.product_tmpl_id._get_diecut_factors() if record.product_tmpl_id else (0,0)
            area = record.calc_area_cache if record.calc_area_cache > 0 else db_area
            
            # Weight 暂时没有缓存，如果是卷料/片料通常只看面积
            weight = db_weight 

            record.price_per_m2 = (record.price / area) if area > 0 else 0.0
            record.price_per_kg = (record.price / weight) if weight > 0 else 0.0

    @api.onchange('price_per_m2')
    def _onchange_price_m2(self):
        for record in self:
            db_area, db_weight = record.product_tmpl_id._get_diecut_factors() if record.product_tmpl_id else (0,0)
            area = record.calc_area_cache if record.calc_area_cache > 0 else db_area
            
            weight = db_weight

            if area > 0:
                record.price = record.price_per_m2 * area
                record.price_per_kg = (record.price / weight) if weight > 0 else 0.0

    @api.onchange('price_per_kg')
    def _onchange_price_kg(self):
        for record in self:
            db_area, db_weight = record.product_tmpl_id._get_diecut_factors() if record.product_tmpl_id else (0,0)
            # Area 也用缓存吗？Kg计算通常依赖 weight。暂不改动逻辑，因为主需求是按面积
            area = record.calc_area_cache if record.calc_area_cache > 0 else db_area
            weight = db_weight
            
            if weight > 0:
                record.price = record.price_per_kg * weight
                record.price_per_m2 = (record.price / area) if area > 0 else 0.0

    def action_set_as_main(self):
        self.ensure_one()
        if self.product_tmpl_id:
            self.product_tmpl_id.main_vendor_id = self.partner_id.id
        return {'type': 'ir.actions.client', 'tag': 'reload'}