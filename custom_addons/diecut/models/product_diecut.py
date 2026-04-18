# -*- coding: utf-8 -*-
from datetime import date
import re
from odoo import models, fields, api, Command
import logging
from odoo.exceptions import ValidationError

class DiecutColor(models.Model):
    _name = 'diecut.color'
    _description = '颜色'

    name = fields.Char(string='颜色名称', required=True)

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    def _collect_color_usage_ids(self):
        return set(self.with_context(active_test=False).mapped('color_id').ids)

    @api.model
    def _refresh_color_usage_counts(self, color_ids):
        if color_ids:
            self.env['diecut.color'].sudo().browse(list(color_ids))._refresh_usage_counts()
        return True

    # --- 标志位 ---
    is_raw_material = fields.Boolean(string="是原材料", default=False)

    raw_material_categ_id = fields.Many2one(
        'product.category',
        related='categ_id',
        string="原材料分类",
        store=True,
        domain="[('category_type', '=', 'raw')]"
    )

    # ==================== 动态属性字段 ====================
    diecut_properties = fields.Properties(
        string='物理特性参数',
        definition='categ_id.diecut_properties_definition',
        copy=True,
    )

    # ==================== 选型目录专用字段 ====================
    def unlink(self):
        color_ids = self._collect_color_usage_ids()
        """删除ERP原材料时，自动重置对应选型目录变体的启用状态"""
        # 1. 自动重置新架构 (Phase 4) 的选型目录条目启用状态
        catalog_items = self.env['diecut.catalog.item'].search([
            ('erp_product_tmpl_id', 'in', self.ids),
            ('erp_enabled', '=', True),
        ])
        if catalog_items:
            catalog_items.with_context(skip_shadow_sync=True).write({
                'erp_enabled': False,
                'erp_product_tmpl_id': False,
            })
                    
        result = super().unlink()
        self._refresh_color_usage_counts(color_ids)
        return result

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

    @api.model
    def search_panel_select_multi_range(self, field_name, **kwargs):
        res = super(ProductTemplate, self).search_panel_select_multi_range(field_name, **kwargs)
        if field_name == 'raw_material_categ_id':
            allowed_cats = self.env['product.category'].search([('category_type', '=', 'raw')])
            allowed_ids = set(allowed_cats.ids)
            
            if isinstance(res, list):
                res = [r for r in res if isinstance(r, dict) and (r.get('id') in allowed_ids or r.get('parent_id') in allowed_ids)]
            elif isinstance(res, dict) and 'values' in res and isinstance(res['values'], list):
                res['values'] = [r for r in res['values'] if isinstance(r, dict) and (r.get('id') in allowed_ids or r.get('parent_id') in allowed_ids)]
        elif field_name == 'main_vendor_id':
            partner_ids = []
            if isinstance(res, list):
                partner_ids = [r['id'] for r in res if isinstance(r, dict) and r.get('id') is not None]
            elif isinstance(res, dict) and 'values' in res and isinstance(res['values'], list):
                partner_ids = [r['id'] for r in res['values'] if isinstance(r, dict) and r.get('id') is not None]
                
            if partner_ids:
                partners = self.env['res.partner'].sudo().browse(partner_ids)
                short_map = {p.id: p.short_name or p.name for p in partners}
                if isinstance(res, list):
                    for i in range(len(res)):
                        r = res[i]
                        if isinstance(r, dict) and r.get('id') in short_map:
                            r['display_name'] = short_map[r['id']]
                elif isinstance(res, dict) and 'values' in res and isinstance(res['values'], list):
                    for i in range(len(res['values'])):
                        r = res['values'][i]
                        if isinstance(r, dict) and r.get('id') in short_map:
                            r['display_name'] = short_map[r['id']]
        return res

    @api.model
    def search_panel_select_range(self, field_name, **kwargs):
        res = super(ProductTemplate, self).search_panel_select_range(field_name, **kwargs)
        if field_name == 'raw_material_categ_id':
            allowed_cats = self.env['product.category'].search([('category_type', '=', 'raw')])
            allowed_ids = set(allowed_cats.ids)
            
            if isinstance(res, list):
                res = [r for r in res if isinstance(r, dict) and (r.get('id') in allowed_ids or r.get('parent_id') in allowed_ids)]
            elif isinstance(res, dict) and 'values' in res and isinstance(res['values'], list):
                res['values'] = [r for r in res['values'] if isinstance(r, dict) and (r.get('id') in allowed_ids or r.get('parent_id') in allowed_ids)]
        elif field_name == 'main_vendor_id':
            partner_ids = []
            if isinstance(res, list):
                partner_ids = [r['id'] for r in res if isinstance(r, dict) and r.get('id') is not None]
            elif isinstance(res, dict) and 'values' in res and isinstance(res['values'], list):
                partner_ids = [r['id'] for r in res['values'] if isinstance(r, dict) and r.get('id') is not None]
                
            if partner_ids:
                partners = self.env['res.partner'].sudo().browse(partner_ids)
                short_map = {p.id: p.short_name or p.name for p in partners}
                if isinstance(res, list):
                    for i in range(len(res)):
                        r = res[i]
                        if isinstance(r, dict) and r.get('id') in short_map:
                            r['display_name'] = short_map[r['id']]
                elif isinstance(res, dict) and 'values' in res and isinstance(res['values'], list):
                    for i in range(len(res['values'])):
                        r = res['values'][i]
                        if isinstance(r, dict) and r.get('id') in short_map:
                            r['display_name'] = short_map[r['id']]
        return res

    # --- 规格型号 ---
    spec = fields.Char(string='规格型号')
    thickness = fields.Float(string='厚度 (mm)', digits=(16, 3))
    width = fields.Float(string='宽度 (mm)', digits=(16, 0))
    length = fields.Float(string='长度 (M)', digits=(16, 3), help="后台统一存储为米")
    length_mm = fields.Float(string='长度 (mm)', compute='_compute_length_mm', inverse='_inverse_length_mm', digits=(16, 0))
    length_smart = fields.Char(string='长度', compute='_compute_length_smart', inverse='_inverse_length_smart', store=True, readonly=False)

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
    color_id = fields.Many2one('diecut.color', string='颜色')
    material_color = fields.Char('颜色备份(原字符字段)', help='历史数据备份')
    adhesive_type_id = fields.Many2one('diecut.catalog.adhesive.type', string='胶系')
    base_material_id = fields.Many2one('diecut.catalog.base.material', string='基材')
    adhesive_thickness = fields.Char(string='胶厚')
    thickness_std = fields.Char(string='标准厚度')
    weight_gram = fields.Float(string='克重 (g)', digits=(16, 2))
    material_type = fields.Char(string='材质/牌号')
    brand_id = fields.Many2one('diecut.brand', string='品牌')
    manufacturer_id = fields.Many2one(
        'res.partner',
        string='制造商',
        domain="[('is_company', '=', True)]",
    )
    brand = fields.Char('品牌备份(原字符字段)', help='历史数据备份')
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

    # --- 认证与合规 ---
    is_rohs = fields.Boolean(string='ROHS', default=False, help='是否通过ROHS认证')
    is_reach = fields.Boolean(string='REACH', default=False, help='是否通过REACH认证')
    is_halogen_free = fields.Boolean(string='无卤', default=False, help='是否为无卤材料')
    fire_rating = fields.Selection([
        ('ul94_v0', 'UL94 V-0'),
        ('ul94_v1', 'UL94 V-1'),
        ('ul94_v2', 'UL94 V-2'),
        ('ul94_hb', 'UL94 HB'),
        ('none', '无'),
    ], string='防火等级', default='none')
    ref_price = fields.Float(string='参考单价', digits=(16, 4))
    catalog_structure_image = fields.Binary(string='产品结构图')

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
                    area, _ = product._get_diecut_factors()
                    # 底层统一：price / price_per_m2 都表示平米单价
                    price_m2 = seller.price_per_m2 or seller.price or 0.0
                    product.raw_material_price_m2 = price_m2
                    product.raw_material_unit_price = (price_m2 * area) if area > 0 else 0.0
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
                
                # 如果在前台填的是整卷参考价，我们反算平米价并赋值给供应商原生 price
                area, weight = product._get_diecut_factors()

                price_m2 = (product.raw_material_unit_price / area) if area > 0 else 0.0
                seller.price_per_m2 = price_m2
                seller.price = price_m2

                if weight > 0:
                    seller.price_per_kg = product.raw_material_unit_price / weight
                else:
                    seller.price_per_kg = 0.0

    def _inverse_raw_material_price_m2(self):
        for product in self:
            if not product.main_vendor_id or not product.seller_ids: continue
            
            main_seller = product.seller_ids.filtered(lambda s: s.partner_id == product.main_vendor_id)
            if main_seller:
                seller = main_seller[0]
                
                # 新范式：由于采购按平米计价，供应商的价格表直接使用平米单价
                seller.price_per_m2 = product.raw_material_price_m2
                seller.price = product.raw_material_price_m2

                area, weight = product._get_diecut_factors()
                if weight > 0:
                    seller.price_per_kg = (product.raw_material_price_m2 * area / weight) if area > 0 else 0.0
                else:
                    seller.price_per_kg = 0.0

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
            # 统一使用 _get_diecut_factors 以保证和其它计算用的是同一个长度
            area, weight = product._get_diecut_factors()

            if area <= 0: continue

            # ### 关键需求：修改材料长宽时，每平米价格不变，只改变每卷(每件)的价格 ###
            if product.raw_material_price_m2 > 0:
                product.raw_material_unit_price = product.raw_material_price_m2 * area

            # 5. 更新子表
            for seller in product.seller_ids:
                # 关键：推送最新面积到缓存
                seller.calc_area_cache = area
                
                # 安全处理：仅当 calc_weight_cache 存在时才赋值
                if hasattr(seller, 'calc_weight_cache'):
                    seller.calc_weight_cache = weight
                else:
                    continue

                # 确保 price_per_m2 存在再同步
                if seller.price_per_m2 > 0:
                    # 改版后，price 就是平米单价，不再乘以 area!
                    seller.price = seller.price_per_m2

                    # 重新计算 kg 价格 (假设整件的费用 / 重量)
                    roll_total_price = seller.price_per_m2 * area
                    seller.price_per_kg = (roll_total_price / weight) if weight > 0 else 0.0
                elif seller.price > 0:
                    # 兼容历史数据：若仅维护了 price，也视作平米价
                    seller.price_per_m2 = seller.price
                    roll_total_price = seller.price * area
                    seller.price_per_kg = (roll_total_price / weight) if weight > 0 else 0.0

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
                    price_m2 = record.raw_material_price_m2 or ((record.raw_material_unit_price / area) if area > 0 else 0.0)
                    self.env['product.supplierinfo'].create({
                        'product_tmpl_id': record.id,
                        'partner_id': record.main_vendor_id.id,
                        'price': price_m2,
                        'price_per_m2': price_m2,
                        'currency_id': record.raw_material_currency_id.id or self.env.company.currency_id.id,
                        'delay': record.lead_time or 0,
                        'min_qty': record.min_order_qty or 0.0,
                        'calc_area_cache': area,
                        'calc_weight_cache': weight,
                    })
        records._refresh_color_usage_counts(records._collect_color_usage_ids())
        return records

    def write(self, vals):
        old_color_ids = self._collect_color_usage_ids() if 'color_id' in vals else set()
        res = super(ProductTemplate, self).write(vals)
        for record in self:
            if not record.is_raw_material:
                continue

            main_vendor_id = vals.get('main_vendor_id', record.main_vendor_id.id)
            if not main_vendor_id:
                continue
            main_vendor = self.env['res.partner'].browse(main_vendor_id)

            # 由于采购系统现在按平米数计价，所以供应商的原生 price 现在完全等于平米单价
            # 放弃整卷价！
            area, weight = record._get_diecut_factors()
            if 'raw_material_price_m2' in vals:
                price_m2 = vals.get('raw_material_price_m2') or 0.0
            elif 'raw_material_unit_price' in vals:
                price_m2 = ((vals.get('raw_material_unit_price') or 0.0) / area) if area > 0 else 0.0
            else:
                price_m2 = record.raw_material_price_m2 or 0.0

            currency_id = vals.get('raw_material_currency_id', record.raw_material_currency_id.id or self.env.company.currency_id.id)
            delay = vals.get('lead_time', record.lead_time) or 0
            min_qty = vals.get('min_order_qty', record.min_order_qty) or 0.0

            seller = record.seller_ids.filtered(lambda s: s.partner_id == main_vendor)
            price_per_kg = (price_m2 * area / weight) if (area > 0 and weight > 0) else 0.0
            if not seller:
                self.env['product.supplierinfo'].create({
                    'product_tmpl_id': record.id,
                    'partner_id': main_vendor.id,
                    'price': price_m2,     # 改版：price 就是 平米价
                    'price_per_m2': price_m2,
                    'price_per_kg': price_per_kg,
                    'currency_id': currency_id,
                    'delay': delay,
                    'min_qty': min_qty,
                    'calc_area_cache': area,
                    'calc_weight_cache': weight,
                })
                continue

            seller = seller[0]
            seller.write({
                'price': price_m2,         # 改版：price 就是 平米价
                'price_per_m2': price_m2,
                'price_per_kg': price_per_kg,
                'currency_id': currency_id,
                'delay': delay,
                'min_qty': min_qty,
                'calc_area_cache': area,
                'calc_weight_cache': weight,
            })
        if 'color_id' in vals:
            self._refresh_color_usage_counts(old_color_ids | self._collect_color_usage_ids())
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
            # 现在 price 就是平米单价，和 price_per_m2 同步即可
            record.price_per_m2 = record.price

            db_area, db_weight = record.product_tmpl_id._get_diecut_factors() if record.product_tmpl_id else (0,0)
            area = record.calc_area_cache if record.calc_area_cache > 0 else db_area
            weight = record.calc_weight_cache if record.calc_weight_cache > 0 else db_weight
            record.price_per_kg = (record.price * area / weight) if (area > 0 and weight > 0) else 0.0

    @api.onchange('price_per_m2')
    def _onchange_price_m2(self):
        for record in self:
            # 同步
            record.price = record.price_per_m2

            db_area, db_weight = record.product_tmpl_id._get_diecut_factors() if record.product_tmpl_id else (0,0)
            area = record.calc_area_cache if record.calc_area_cache > 0 else db_area
            weight = record.calc_weight_cache if record.calc_weight_cache > 0 else db_weight
            record.price_per_kg = (record.price_per_m2 * area / weight) if (area > 0 and weight > 0) else 0.0

    @api.onchange('price_per_kg')
    def _onchange_price_kg(self):
        for record in self:
            db_area, db_weight = record.product_tmpl_id._get_diecut_factors() if record.product_tmpl_id else (0,0)
            area = record.calc_area_cache if record.calc_area_cache > 0 else db_area
            weight = record.calc_weight_cache if record.calc_weight_cache > 0 else db_weight

            if weight > 0 and area > 0:
                total_price = record.price_per_kg * weight
                record.price_per_m2 = total_price / area
                record.price = record.price_per_m2

    def action_set_as_main(self):
        self.ensure_one()
        if self.product_tmpl_id:
            self.product_tmpl_id.main_vendor_id = self.partner_id.id
        return {'type': 'ir.actions.client', 'tag': 'reload'}

