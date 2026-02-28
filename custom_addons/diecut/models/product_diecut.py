# -*- coding: utf-8 -*-
from datetime import date
import re
from odoo import models, fields, api
from odoo.exceptions import ValidationError

class DiecutBrand(models.Model):
    _name = 'diecut.brand'
    _description = '品牌'

    name = fields.Char(string='品牌名称', required=True)

class DiecutColor(models.Model):
    _name = 'diecut.color'
    _description = '颜色'

    name = fields.Char(string='颜色名称', required=True)

class ProductTemplate(models.Model):
    _inherit = 'product.template'
    _catalog_source_unique_index = 'diecut_product_template_source_catalog_variant_uidx'

    # --- 标志位 ---
    is_raw_material = fields.Boolean(string="是原材料", default=False)
    is_catalog = fields.Boolean(string="选型目录", default=False, help="勾选后该产品作为选型目录使用，支持变体管理")

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
    catalog_status = fields.Selection([
        ('draft', '草稿'),
        ('review', '评审中'),
        ('published', '已发布'),
        ('deprecated', '已停产'),
    ], string='目录状态', default='draft', tracking=True)
    recommendation_level = fields.Selection([
        ('a', 'A-强推荐'),
        ('b', 'B-备选'),
        ('c', 'C-谨慎/淘汰'),
    ], string='推荐等级', default='b', tracking=True)
    source_catalog_variant_id = fields.Many2one(
        'product.product', string='源选型目录变体',
        help='该ERP产品是从哪个选型目录变体启用而来',
        readonly=True, copy=False,
    )
    replacement_catalog_ids = fields.Many2many(
        'product.template',
        'product_template_catalog_replacement_rel',
        'src_tmpl_id',
        'dst_tmpl_id',
        string='替代系列',
        help='当当前系列不适配或停产时，可推荐的替代系列（目录层）',
    )
    replaced_by_catalog_ids = fields.Many2many(
        'product.template',
        'product_template_catalog_replacement_rel',
        'dst_tmpl_id',
        'src_tmpl_id',
        string='被以下系列替代',
        readonly=True,
    )
    series_name = fields.Char(string='系列名称', help='如：Bond & Detach、PET Double Sided Tape')
    manufacturer_id = fields.Many2one(
        'res.partner', string='生产厂家',
        help='原厂（如 3M, tesa, Sidike），区别于供应商/经销商',
        domain="[('is_company', '=', True)]",
    )
    catalog_base_material = fields.Char(string='基材类型', help='如 PET、PU、PI、铜箔等')
    catalog_adhesive_type = fields.Char(string='胶系', help='如 丙烯酸、合成橡胶、硅胶等')
    variant_thickness_std_index = fields.Char(
        string='厚度',
        compute='_compute_variant_std_index',
        store=True,
        help='系列下所有型号的标准化厚度索引（用于筛选）',
    )
    variant_color_std_index = fields.Char(
        string='颜色',
        compute='_compute_variant_std_index',
        store=True,
        help='系列下所有型号的标准化颜色索引（用于筛选）',
    )
    variant_adhesive_std_index = fields.Char(
        string='胶系',
        compute='_compute_variant_std_index',
        store=True,
        help='系列下所有型号的标准化胶系索引（用于筛选）',
    )
    variant_base_material_std_index = fields.Char(
        string='基材',
        compute='_compute_variant_std_index',
        store=True,
        help='系列下所有型号的标准化基材索引（用于筛选）',
    )
    catalog_features = fields.Text(string='产品特点', help='如：抗拉强度好、耐温耐候性好')
    catalog_applications = fields.Html(string='典型应用', help='如：LCD铭板、手机部件粘接；支持富文本（标题、列表、加粗等）')
    catalog_characteristics = fields.Char(string='特性', help='简短特性标签，如：耐化学腐蚀, 重工性；高粘, 抗冲击')
    catalog_structure_image = fields.Binary(string='产品结构图')
    catalog_ref_price = fields.Float(string='参考单价', digits=(16, 4), help='仅供选型参考，不参与ERP计价')
    catalog_ref_currency_id = fields.Many2one(
        'res.currency', string='参考价币种',
        default=lambda self: self.env.company.currency_id,
    )
    tds_file = fields.Binary(string='TDS技术数据表')
    tds_filename = fields.Char(string='TDS文件名')
    msds_file = fields.Binary(string='MSDS安全数据表')
    msds_filename = fields.Char(string='MSDS文件名')

    @api.constrains('is_catalog', 'is_raw_material')
    def _check_catalog_raw_material_exclusive(self):
        """选型目录和ERP原材料互斥"""
        for record in self:
            if record.is_catalog and record.is_raw_material:
                raise ValidationError('一个产品不能同时是「选型目录」和「原材料」，请只勾选其中一项！')

    @api.constrains('source_catalog_variant_id')
    def _check_source_catalog_variant_unique(self):
        """业务约束：一个目录变体只能映射一个ERP原材料"""
        for record in self.filtered('source_catalog_variant_id'):
            duplicate = self.search_count([
                ('id', '!=', record.id),
                ('source_catalog_variant_id', '=', record.source_catalog_variant_id.id),
            ])
            if duplicate:
                raise ValidationError(
                    '同一个选型目录变体只能映射一个ERP原材料，请检查重复映射后再保存。'
                )

    @api.constrains('replacement_catalog_ids', 'is_catalog')
    def _check_catalog_replacements(self):
        for record in self:
            if not record.is_catalog and record.replacement_catalog_ids:
                raise ValidationError('只有材料选型目录可以设置“替代系列”。')
            if record in record.replacement_catalog_ids:
                raise ValidationError('替代系列不能包含自己。')
            invalid = record.replacement_catalog_ids.filtered(lambda r: not r.is_catalog)
            if invalid:
                raise ValidationError('替代系列中包含非“选型目录”产品，请修正后保存。')

    def init(self):
        """数据库级约束：为 source_catalog_variant_id 创建唯一部分索引。"""
        super().init()
        self._cr.execute("""
            SELECT source_catalog_variant_id, array_agg(id ORDER BY id)
            FROM product_template
            WHERE source_catalog_variant_id IS NOT NULL
            GROUP BY source_catalog_variant_id
            HAVING COUNT(*) > 1
            LIMIT 1
        """)
        duplicate = self._cr.fetchone()
        if duplicate:
            variant_id, tmpl_ids = duplicate
            raise ValidationError(
                '检测到历史重复映射数据：source_catalog_variant_id=%s, product_template_ids=%s。'
                '请先清理重复数据，再升级模块以创建唯一索引。'
                % (variant_id, tmpl_ids)
            )

        self._cr.execute(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS {self._catalog_source_unique_index}
            ON product_template (source_catalog_variant_id)
            WHERE source_catalog_variant_id IS NOT NULL
            """
        )

    def action_view_catalog_source(self):
        """从ERP原材料跳转回源选型目录"""
        self.ensure_one()
        if self.source_catalog_variant_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'product.template',
                'res_id': self.source_catalog_variant_id.product_tmpl_id.id,
                'view_mode': 'form',
                'view_id': self.env.ref('diecut.view_material_catalog_form').id,
                'target': 'current',
            }

    def action_submit_review(self):
        for record in self:
            if record.is_catalog and record.catalog_status == 'draft':
                record.catalog_status = 'review'
        return True

    def _validate_catalog_publish(self):
        self.ensure_one()
        errors = []
        if not self.is_catalog:
            errors.append('仅“选型目录”可执行发布。')
        if not self.brand_id:
            errors.append('品牌不能为空。')
        if not self.categ_id:
            errors.append('材料分类不能为空。')
        if not (self.series_name or self.name):
            errors.append('系列名称不能为空。')
        if not self.catalog_base_material:
            errors.append('基材类型不能为空。')
        if not self.catalog_adhesive_type:
            errors.append('胶系不能为空。')
        if not self.catalog_features:
            errors.append('产品特点不能为空。')
        if not self.catalog_applications:
            errors.append('典型应用不能为空。')
        if not (self.tds_file or self.msds_file or self.datasheet):
            errors.append('至少上传一份技术文档（TDS/MSDS/规格书）。')
        if not self.product_variant_ids:
            errors.append('至少需要一个型号变体。')
        else:
            missing_code_variants = self.product_variant_ids.filtered(lambda v: not v.default_code)
            if missing_code_variants:
                errors.append('存在未填写型号编码的变体。')
        if errors:
            raise ValidationError('发布校验未通过：\n- ' + '\n- '.join(errors))

    def action_publish_catalog(self):
        for record in self:
            record._validate_catalog_publish()
            record.catalog_status = 'published'
        return True

    def action_set_catalog_draft(self):
        for record in self.filtered('is_catalog'):
            record.catalog_status = 'draft'
        return True

    def action_deprecate_catalog(self):
        for record in self.filtered('is_catalog'):
            record.catalog_status = 'deprecated'
        return True

    @api.depends(
        'product_variant_ids',
        'product_variant_ids.variant_thickness_std',
        'product_variant_ids.variant_color_std',
        'product_variant_ids.variant_adhesive_std',
        'product_variant_ids.variant_base_material_std',
    )
    def _compute_variant_std_index(self):
        for record in self:
            thickness_vals = sorted({str(v) for v in record.product_variant_ids.mapped('variant_thickness_std') if v}, key=str)
            color_vals = sorted({str(v) for v in record.product_variant_ids.mapped('variant_color_std') if v}, key=str)
            adhesive_vals = sorted({str(v) for v in record.product_variant_ids.mapped('variant_adhesive_std') if v}, key=str)
            base_material_vals = sorted({str(v) for v in record.product_variant_ids.mapped('variant_base_material_std') if v}, key=str)
            record.variant_thickness_std_index = ', '.join(thickness_vals)
            record.variant_color_std_index = ', '.join(color_vals)
            record.variant_adhesive_std_index = ', '.join(adhesive_vals)
            record.variant_base_material_std_index = ', '.join(base_material_vals)

    def unlink(self):
        """删除ERP原材料时，自动重置对应选型目录变体的启用状态"""
        # 查找所有引用即将删除产品的选型目录变体
        catalog_variants = self.env['product.product'].search([
            ('activated_product_tmpl_id', 'in', self.ids),
            ('is_activated', '=', True),
        ])
        if catalog_variants:
            catalog_variants.write({
                'is_activated': False,
                'activated_product_tmpl_id': False,
            })
        return super().unlink()

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
    color_id = fields.Many2one('diecut.color', string='颜色')
    material_color = fields.Char('颜色备份(原字符字段)', help='历史数据备份')
    weight_gram = fields.Float(string='克重 (g)', digits=(16, 2))
    material_type = fields.Char(string='材质/牌号')
    brand_id = fields.Many2one('diecut.brand', string='品牌')
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


class ProductProduct(models.Model):
    """产品变体扩展 - 选型目录的变体级技术参数"""
    _inherit = 'product.product'
    _variant_std_sync_ctx_key = 'skip_variant_std_sync'
    catalog_categ_id = fields.Many2one(
        'product.category', related='product_tmpl_id.categ_id', store=True, string='分类'
    )
    catalog_brand_id = fields.Many2one(
        'diecut.brand', related='product_tmpl_id.brand_id', store=True, string='品牌'
    )
    catalog_status = fields.Selection(
        related='product_tmpl_id.catalog_status', store=True, string='目录状态'
    )
    recommendation_level = fields.Selection(
        related='product_tmpl_id.recommendation_level', store=True, string='推荐等级'
    )
    catalog_density = fields.Float(
        related='product_tmpl_id.density', store=True, string='密度(g/cm³)'
    )
    # 变体详情/规格页展示用：继承自系列
    catalog_structure_image = fields.Binary(related='product_tmpl_id.catalog_structure_image', string='产品结构图')
    catalog_features = fields.Text(related='product_tmpl_id.catalog_features', string='产品特点')
    catalog_applications = fields.Html(related='product_tmpl_id.catalog_applications', string='典型应用')
    catalog_characteristics = fields.Char(related='product_tmpl_id.catalog_characteristics', string='特性', store=True)
    # 不在变体上做 related diecut_properties，避免创建变体时 Properties 的 definition_record 解析为 None 导致 TypeError（变体表单使用 variant_diecut_properties）
    # 变体自有动态属性：与系列共用分类下的定义，但每个变体可存不同值
    variant_diecut_properties = fields.Properties(
        string='变体物理特性',
        definition='catalog_categ_id.diecut_properties_definition',
        copy=True,
    )
    tds_file = fields.Binary(related='product_tmpl_id.tds_file', string='TDS')
    tds_filename = fields.Char(related='product_tmpl_id.tds_filename')
    msds_file = fields.Binary(related='product_tmpl_id.msds_file', string='MSDS')
    msds_filename = fields.Char(related='product_tmpl_id.msds_filename')

    # ==================== 变体级技术参数（选型目录专用）====================
    # 使用 Char 类型保留原厂数据完整性（公差、条件、双面差异等）
    variant_thickness = fields.Char(string='厚度', help='如：35±5 μm、100±10 μm')
    variant_adhesive_thickness = fields.Char(string='胶厚', help='如：13/13、35/40（双面胶厚）')
    variant_color = fields.Char(string='颜色', help='如：透明、黑色、75蓝')
    variant_peel_strength = fields.Char(string='剥离力', help='如：>800 gf/inch、A>1000 B>800')
    variant_structure = fields.Char(string='结构描述', help='如：胶+PET+胶+白色LXZ')
    variant_adhesive_type = fields.Char(string='胶系(变体)', help='可覆盖模板级胶系')
    variant_base_material = fields.Char(string='基材(变体)', help='可覆盖模板级基材')
    variant_sus_peel = fields.Char(string='SUS面剥离力', help='如：13.0/13.0 N/cm')
    variant_pe_peel = fields.Char(string='PE面剥离力', help='如：7.0/7.0 N/cm')
    variant_dupont = fields.Char(string='DuPont冲击', help='如：0.7/0.1、1.3/1.0 [A×cM]')
    variant_push_force = fields.Char(string='推出力', help='如：229 N')
    variant_removability = fields.Char(string='可移除性', help='如：*、**、***（与同品类比较）')
    variant_tumbler = fields.Char(string='Tumbler滚球', help='如：Upon request、40.0')
    variant_holding_power = fields.Char(string='保持力', help='如：4.0 N/cm')
    variant_note = fields.Text(string='型号备注')
    variant_ref_price = fields.Float(string='参考单价', digits=(16, 4), help='该型号的参考单价')
    # 标准化字段：用于销售/工程筛选，不替代原厂原文字段
    variant_thickness_std = fields.Char(
        string='厚度', help='标准化厚度，如 100um', oldname='variant_thickness_grade'
    )
    variant_color_std = fields.Char(
        string='颜色', help='标准化颜色，如 透明/黑色', oldname='variant_color_grade'
    )
    variant_adhesive_std = fields.Char(
        string='胶系', help='标准化胶系', oldname='variant_adhesive_grade'
    )
    variant_base_material_std = fields.Char(
        string='基材', help='标准化基材', oldname='variant_base_material_grade'
    )

    # ==================== 变体独立：认证与合规、替代建议、附件与资料 ====================
    variant_is_rohs = fields.Boolean(string='ROHS', default=False, help='该型号是否通过ROHS认证')
    variant_is_reach = fields.Boolean(string='REACH', default=False, help='该型号是否通过REACH认证')
    variant_is_halogen_free = fields.Boolean(string='无卤', default=False, help='该型号是否为无卤材料')
    variant_fire_rating = fields.Selection([
        ('ul94_v0', 'UL94 V-0'),
        ('ul94_v1', 'UL94 V-1'),
        ('ul94_v2', 'UL94 V-2'),
        ('ul94_hb', 'UL94 HB'),
        ('none', '无'),
    ], string='防火等级', default='none')
    variant_replacement_catalog_ids = fields.Many2many(
        'product.template',
        'product_product_catalog_replacement_rel',
        'src_variant_id',
        'dst_tmpl_id',
        string='可替代系列',
        help='该型号不适配或停产时可推荐的替代系列（目录层）',
        domain="[('is_catalog', '=', True)]",
    )
    variant_tds_file = fields.Binary(string='TDS技术数据表')
    variant_tds_filename = fields.Char(string='TDS文件名')
    variant_msds_file = fields.Binary(string='MSDS安全数据表')
    variant_msds_filename = fields.Char(string='MSDS文件名')
    variant_datasheet = fields.Binary(string='规格书')
    variant_datasheet_filename = fields.Char(string='规格书文件名')
    variant_catalog_structure_image = fields.Binary(string='产品结构图')

    # ==================== 选型目录溯源字段 ====================
    is_activated = fields.Boolean(
        string='已启用到ERP', default=False, readonly=True, copy=False,
        help='标记该选型目录变体是否已被启用到ERP原材料管理',
    )
    activated_product_tmpl_id = fields.Many2one(
        'product.template', string='已启用的ERP产品',
        readonly=True, copy=False,
        help='该变体启用后对应的ERP原材料产品',
    )

    @staticmethod
    def _normalize_text_std(value):
        if not value:
            return False
        normalized = re.sub(r'\s+', ' ', value).strip()
        return normalized or False

    @staticmethod
    def _normalize_thickness_std(thickness_text):
        """将原始厚度文本归一为标准厚度（默认统一到 um）。"""
        if not thickness_text:
            return False
        s = thickness_text.lower().replace('μm', 'um').replace('µm', 'um').replace(' ', '')
        match = re.search(r'(\d+(?:\.\d+)?)', s)
        if not match:
            return False

        val = float(match.group(1))
        is_um = 'um' in s
        is_mm = 'mm' in s and not is_um

        if is_um:
            um_val = val
        elif is_mm:
            um_val = val * 1000.0
        else:
            # 无单位时沿用既有口径：>10 视作 um，否则视作 mm
            um_val = val if val > 10 else (val * 1000.0)

        rounded = round(um_val, 1)
        if rounded.is_integer():
            return f"{int(rounded)}um"
        return f"{rounded:g}um"

    @classmethod
    def _build_variant_std_vals_from_raw(cls, vals):
        std_vals = {}
        if 'variant_thickness' in vals:
            std_vals['variant_thickness_std'] = cls._normalize_thickness_std(vals.get('variant_thickness'))
        if 'variant_color' in vals:
            std_vals['variant_color_std'] = cls._normalize_text_std(vals.get('variant_color'))
        if 'variant_adhesive_type' in vals:
            std_vals['variant_adhesive_std'] = cls._normalize_text_std(vals.get('variant_adhesive_type'))
        if 'variant_base_material' in vals:
            std_vals['variant_base_material_std'] = cls._normalize_text_std(vals.get('variant_base_material'))
        return std_vals

    def _build_variant_std_vals(self):
        self.ensure_one()
        return self._build_variant_std_vals_from_raw({
            'variant_thickness': self.variant_thickness,
            'variant_color': self.variant_color,
            'variant_adhesive_type': self.variant_adhesive_type,
            'variant_base_material': self.variant_base_material,
        })

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        std_keys = {'variant_thickness_std', 'variant_color_std', 'variant_adhesive_std', 'variant_base_material_std'}
        for idx, record in enumerate(records):
            incoming = vals_list[idx] if idx < len(vals_list) else {}
            if std_keys.intersection(incoming.keys()):
                continue
            auto_vals = record._build_variant_std_vals()
            record.with_context(**{self._variant_std_sync_ctx_key: True}).write(auto_vals)
        return records

    def write(self, vals):
        res = super().write(vals)
        if self.env.context.get(self._variant_std_sync_ctx_key):
            return res

        raw_keys = {'variant_thickness', 'variant_color', 'variant_adhesive_type', 'variant_base_material'}
        std_keys = {'variant_thickness_std', 'variant_color_std', 'variant_adhesive_std', 'variant_base_material_std'}
        if raw_keys.intersection(vals.keys()) and not std_keys.intersection(vals.keys()):
            for record in self:
                auto_vals = record._build_variant_std_vals()
                record.with_context(**{self._variant_std_sync_ctx_key: True}).write(auto_vals)
        return res

    @api.constrains('variant_replacement_catalog_ids', 'product_tmpl_id')
    def _check_variant_replacement_catalog(self):
        for record in self:
            if record.product_tmpl_id and record.product_tmpl_id in record.variant_replacement_catalog_ids:
                raise ValidationError('可替代系列不能包含本型号所属系列。')

    def action_activate_to_erp(self):
        """一键启用到ERP：将选型目录变体转化为独立的ERP原材料产品"""
        self.ensure_one()
        existing_product = self.env['product.template'].search(
            [('source_catalog_variant_id', '=', self.id)],
            limit=1,
        )
        if existing_product:
            if not (self.is_activated and self.activated_product_tmpl_id == existing_product):
                self.write({
                    'is_activated': True,
                    'activated_product_tmpl_id': existing_product.id,
                })
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'product.template',
                'res_id': existing_product.id,
                'view_mode': 'form',
                'target': 'current',
            }
        # 检查是否已启用
        if self.is_activated and self.activated_product_tmpl_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'product.template',
                'res_id': self.activated_product_tmpl_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
        # 打开确认向导
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'diecut.catalog.activate.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_variant_id': self.id,
                'default_catalog_tmpl_id': self.product_tmpl_id.id,
            },
        }

    def action_view_erp_product(self):
        """跳转到已启用的ERP产品"""
        self.ensure_one()
        if self.activated_product_tmpl_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'product.template',
                'res_id': self.activated_product_tmpl_id.id,
                'view_mode': 'form',
                'target': 'current',
            }

    @api.model
    def _load_catalog_variant_data(self, tmpl_xml_id: str, variant_data: list):
        """通用方法：批量填充选型目录变体的技术参数

        Args:
            tmpl_xml_id: 产品模板的完整 XML ID，如 'diecut.catalog_sidike_dst'
            variant_data: 变体数据列表，每项为 (属性值名称, {字段: 值}) 的元组
                示例: [('DST-3', {'default_code': 'DST-3', 'variant_thickness': '35±5 μm'})]
        """
        tmpl = self.env.ref(tmpl_xml_id, raise_if_not_found=False)
        if not tmpl:
            return

        # 构建 属性值名称 → 变体数据 的映射
        data_map = {name: vals for name, vals in variant_data}

        for variant in tmpl.product_variant_ids:
            # 获取该变体对应的属性值名称
            attr_value_names = variant.product_template_attribute_value_ids.mapped(
                'product_attribute_value_id.name'
            )
            for attr_name in attr_value_names:
                if attr_name in data_map:
                    variant.write(data_map[attr_name])
                    break

    @api.model
    def _load_sidike_uv_variant_data(self):
        """Sidike UV失粘胶带系列变体数据（硬编码避免XML转义问题）"""
        variant_data = [
            ('SDK2200UV',      {'default_code': 'SDK2200UV',      'variant_base_material': 'PET',      'variant_adhesive_type': '特殊亚克力胶', 'variant_thickness': '65±5 μm',  'variant_color': '透明', 'variant_peel_strength': '> 1500 gf/inch',       'variant_sus_peel': '≥100 gf/inch',  'variant_pe_peel': '≤15 gf/inch',       'variant_holding_power': '胶面 <10¹¹ 膜面 <10¹¹'}),
            ('SDK2409UV',      {'default_code': 'SDK2409UV',      'variant_base_material': 'PET',      'variant_adhesive_type': '特殊亚克力胶', 'variant_thickness': '100±5 μm', 'variant_color': '透明', 'variant_peel_strength': '1400±400 gf/inch',    'variant_sus_peel': '≥100 gf/inch',  'variant_pe_peel': '≤20 gf/inch',       'variant_holding_power': '胶面 <10⁹ 膜面 <10⁹'}),
            ('SDK2200UV-P-3',  {'default_code': 'SDK2200UV-P-3',  'variant_base_material': 'PET',      'variant_adhesive_type': '特殊亚克力胶', 'variant_thickness': '100±5 μm', 'variant_color': '透明', 'variant_peel_strength': '> 2200 gf/inch',       'variant_sus_peel': '≥100 gf/inch',  'variant_pe_peel': '≤20 gf/inch',       'variant_holding_power': '膜面 <10⁹'}),
            ('SDK2408UV',      {'default_code': 'SDK2408UV',      'variant_base_material': 'PET',      'variant_adhesive_type': '特殊亚克力胶', 'variant_thickness': '100±5 μm', 'variant_color': '透明', 'variant_peel_strength': '> 1000 gf/inch',       'variant_sus_peel': '800±300 gf/inch','variant_pe_peel': '≤15 gf/inch',      'variant_holding_power': '/'}),
            ('SDK2302UV',      {'default_code': 'SDK2302UV',      'variant_base_material': 'PET',      'variant_adhesive_type': '特殊亚克力胶', 'variant_thickness': '155±5 μm', 'variant_color': '透明', 'variant_peel_strength': '1400±400 gf/inch',    'variant_sus_peel': '≥100 gf/inch',  'variant_pe_peel': '≤20 gf/inch',       'variant_holding_power': '/'}),
            ('SDK2100UV',      {'default_code': 'SDK2100UV',      'variant_base_material': 'PET+BOPP', 'variant_adhesive_type': '特殊亚克力胶', 'variant_thickness': '200±5 μm', 'variant_color': '透明', 'variant_peel_strength': '1400±400 gf/inch',    'variant_sus_peel': '≥100 gf/inch',  'variant_pe_peel': '≤20 gf/inch',       'variant_holding_power': '/'}),
            ('SDK2304-1UV',    {'default_code': 'SDK2304-1UV',    'variant_base_material': 'PET+BOPP', 'variant_adhesive_type': '特殊亚克力胶', 'variant_thickness': '215±5 μm', 'variant_color': '透明', 'variant_peel_strength': '200±100 gf/inch',     'variant_sus_peel': '≥100 gf/inch',  'variant_pe_peel': '≤20 gf/inch',       'variant_holding_power': '/'}),
            ('SDK99853UV-F',   {'default_code': 'SDK99853UV-F',   'variant_base_material': 'PO',       'variant_adhesive_type': '特殊亚克力胶', 'variant_thickness': '170±5 μm', 'variant_color': '透明', 'variant_peel_strength': '> 1500 gf/inch',       'variant_sus_peel': '/',             'variant_pe_peel': '<20 gf/inch',       'variant_holding_power': '/'}),
            ('SDK925AU',       {'default_code': 'SDK925AU',       'variant_base_material': 'PET',      'variant_adhesive_type': '特殊亚克力胶', 'variant_thickness': '70±5 μm',  'variant_color': '透明', 'variant_peel_strength': '> 1700 gf/inch',       'variant_sus_peel': '/',             'variant_pe_peel': '≤10 gf/inch',       'variant_holding_power': '/'}),
            ('SDK925AU(三抗)', {'default_code': 'SDK925AU(三抗)', 'variant_base_material': 'PET',      'variant_adhesive_type': '特殊亚克力胶', 'variant_thickness': '70±5 μm',  'variant_color': '透明', 'variant_peel_strength': '> 1700 gf/inch',       'variant_sus_peel': '/',             'variant_pe_peel': '≤10 gf/inch',       'variant_holding_power': '胶面 <10⁹ 膜面 <10⁹ 离型膜背面 <10⁹'}),
            ('SDK9212UV',      {'default_code': 'SDK9212UV',      'variant_base_material': 'PET',      'variant_adhesive_type': '特殊亚克力胶', 'variant_thickness': '50±5 μm',  'variant_color': '透明', 'variant_peel_strength': '双面 > 1500 gf/inch',  'variant_sus_peel': '/',             'variant_pe_peel': '双面 <10 gf/inch',  'variant_holding_power': '/'}),
        ]
        self._load_catalog_variant_data('diecut.catalog_sidike_uv', variant_data)
