# -*- coding: utf-8 -*-
import re
from odoo import models, fields, api


class CatalogActivateWizard(models.TransientModel):
    """一键将选型目录变体启用到ERP原材料管理"""
    _name = 'diecut.catalog.activate.wizard'
    _description = '选型目录启用向导'

    # --- 来源信息（自动带入，只读） ---
    variant_id = fields.Many2one('product.product', string='源变体', readonly=True)
    catalog_tmpl_id = fields.Many2one('product.template', string='源选型目录', readonly=True)
    catalog_item_id = fields.Many2one('diecut.catalog.item', string='源选型目录(新)', readonly=True)

    # --- 预填信息（可编辑） ---
    product_name = fields.Char(string='产品名称', required=True)
    default_code = fields.Char(string='内部参考/型号')
    categ_id = fields.Many2one('product.category', string='产品分类', required=True, domain="[('category_type', '=', 'raw')]")
    brand_id = fields.Many2one('diecut.brand', string='品牌')
    material_type = fields.Char(string='材质/牌号')
    thickness = fields.Float(string='厚度 (mm)', digits=(16, 3))

    # --- 用户补填信息 ---
    width = fields.Float(string='宽度 (mm)', digits=(16, 0))
    length = fields.Float(string='长度 (M)', digits=(16, 3))
    rs_type = fields.Selection([
        ('R', '卷料'),
        ('S', '片料'),
    ], string='形态(R/S)', default='R')
    main_vendor_id = fields.Many2one(
        'res.partner', string='主要供应商',
        domain="[('supplier_rank', '>', 0)]",
    )

    @api.model
    def default_get(self, fields_list):
        """从选型目录变体自动预填字段"""
        res = super().default_get(fields_list)
        variant_id = res.get('variant_id') or self.env.context.get('default_variant_id')
        catalog_item_id = res.get('catalog_item_id') or self.env.context.get('default_catalog_item_id')

        if catalog_item_id:
            item = self.env['diecut.catalog.item'].browse(catalog_item_id)
            brand_name = item.brand_id.name or ''
            variant_code = item.code or ''
            base_material = item.variant_base_material or ''
            series_short = item.series_text or ''
            
            res['product_name'] = f"{brand_name} {variant_code} {base_material}{series_short}".strip()
            res['default_code'] = variant_code
            res['categ_id'] = item.categ_id.id if item.categ_id else False
            res['brand_id'] = item.brand_id.id if item.brand_id else False
            res['material_type'] = base_material
            
            thickness_val = item.variant_thickness_std or item.variant_thickness
            res['thickness'] = self._parse_thickness(thickness_val)
        elif variant_id:
            variant = self.env['product.product'].browse(variant_id)
            tmpl = variant.product_tmpl_id

            # 自动拼接产品名称
            brand_name = tmpl.brand_id.name or ''
            variant_code = variant.default_code or ''
            base_material = tmpl.catalog_base_material or ''
            series_short = tmpl.series_name or tmpl.name or ''
            res['product_name'] = f"{brand_name} {variant_code} {base_material}{series_short}".strip()

            # 复制基本信息
            res['default_code'] = variant.default_code or ''
            res['categ_id'] = tmpl.categ_id.id
            res['brand_id'] = tmpl.brand_id.id if tmpl.brand_id else False
            res['material_type'] = tmpl.catalog_base_material or tmpl.material_type or ''

            # 智能解析厚度：从 Char "100±10 μm" 提取中心值并转为 mm
            res['thickness'] = self._parse_thickness(variant.variant_thickness)

        return res

    @staticmethod
    def _parse_thickness(thickness_str: str) -> float:
        """智能解析厚度字符串为 mm 数值
        
        Examples:
            "35±5 μm"    → 0.035
            "100±10 μm"  → 0.100
            "0.15mm"     → 0.150
            "150"        → 0.150 (假设 μm)
        """
        if not thickness_str:
            return 0.0
        
        # 清理空格
        s = thickness_str.strip()
        
        # 检查是否包含 mm 单位
        is_mm = 'mm' in s.lower() and 'μm' not in s.lower() and 'um' not in s.lower()
        
        # 提取第一个数字（中心值）
        match = re.search(r'([\d.]+)', s)
        if not match:
            return 0.0
        
        val = float(match.group(1))
        
        # 如果是 mm 单位，直接返回
        if is_mm:
            return val
        
        # 默认假设 μm，转为 mm
        if val > 10:  # 大于 10 的值几乎肯定是 μm
            return val / 1000.0
        
        # 小于等于 10 的值可能已经是 mm
        return val

    def action_confirm(self):
        """确认启用：创建ERP原材料产品"""
        self.ensure_one()
        variant = self.variant_id
        item = self.catalog_item_id

        if item:
            # 新架构启用分支
            self.env.cr.execute(
                "SELECT id FROM diecut_catalog_item WHERE id = %s FOR UPDATE",
                [item.id],
            )
            item = self.env['diecut.catalog.item'].browse(item.id)

            # 防重复检查
            if item.erp_enabled and item.erp_product_tmpl_id:
                if self.env.context.get('from_gray_catalog_item'):
                    if self.env.context.get('is_split_view_action'):
                        return {'type': 'ir.actions.act_window_close', 'infos': {'noReload': True}}
                    return {'type': 'ir.actions.client', 'tag': 'reload'}
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'product.template',
                    'res_id': item.erp_product_tmpl_id.id,
                    'view_mode': 'form',
                    'target': 'current',
                }
        elif variant:
            # 旧架构启用分支
            tmpl = self.catalog_tmpl_id
            self.env.cr.execute(
                "SELECT id FROM product_product WHERE id = %s FOR UPDATE",
                [variant.id],
            )
            variant = self.env['product.product'].browse(variant.id)
    
            existing_product = self.env['product.template'].search(
                [('source_catalog_variant_id', '=', variant.id)],
                limit=1,
            )
            if existing_product:
                if not (variant.is_activated and variant.activated_product_tmpl_id == existing_product):
                    variant.write({
                        'is_activated': True,
                        'activated_product_tmpl_id': existing_product.id,
                    })
                if self.env.context.get('from_gray_catalog_item'):
                    if self.env.context.get('is_split_view_action'):
                        return {'type': 'ir.actions.act_window_close', 'infos': {'noReload': True}}
                    return {'type': 'ir.actions.client', 'tag': 'reload'}
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'product.template',
                    'res_id': existing_product.id,
                    'view_mode': 'form',
                    'target': 'current',
                }
    
            # 防重复检查
            if variant.is_activated and variant.activated_product_tmpl_id:
                if self.env.context.get('from_gray_catalog_item'):
                    if self.env.context.get('is_split_view_action'):
                        return {'type': 'ir.actions.act_window_close', 'infos': {'noReload': True}}
                    return {'type': 'ir.actions.client', 'tag': 'reload'}
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'product.template',
                    'res_id': variant.activated_product_tmpl_id.id,
                    'view_mode': 'form',
                    'target': 'current',
                }

        # 根据分支提取对应特征参数
        if item:
            density = False
            adhesion = False
            material_transparency = False
            tensile_strength = False
            tear_strength = False
            temp_resistance_min = False
            temp_resistance_max = False
            is_rohs = item.variant_is_rohs
            is_reach = item.variant_is_reach
            is_halogen_free = item.variant_is_halogen_free
            fire_rating = item.variant_fire_rating
            datasheet = item.variant_datasheet
            datasheet_filename = item.variant_datasheet_filename
            application = ""
            process_note = ""
            source_catalog_variant_id = False
        else:
            density = tmpl.density
            adhesion = tmpl.adhesion
            material_transparency = tmpl.material_transparency
            tensile_strength = tmpl.tensile_strength
            tear_strength = tmpl.tear_strength
            temp_resistance_min = tmpl.temp_resistance_min
            temp_resistance_max = tmpl.temp_resistance_max
            is_rohs = tmpl.is_rohs
            is_reach = tmpl.is_reach
            is_halogen_free = tmpl.is_halogen_free
            fire_rating = tmpl.fire_rating
            datasheet = tmpl.datasheet
            datasheet_filename = tmpl.datasheet_filename
            application = tmpl.application
            process_note = tmpl.process_note
            source_catalog_variant_id = variant.id

        # 创建新的 ERP 原材料产品
        new_product_vals = {
            'name': self.product_name,
            'default_code': self.default_code,
            'categ_id': self.categ_id.id,
            'is_raw_material': True,
            'is_catalog': False,
            'purchase_ok': True,
            'sale_ok': False,
            'type': 'consu',
            'is_storable': True,
            # 规格参数
            'thickness': self.thickness,
            'width': self.width,
            'length': self.length,
            'rs_type': self.rs_type,
            # 从模板复制的共性参数
            'brand_id': self.brand_id.id if self.brand_id else False,
            'material_type': self.material_type,
            'density': density,
            'adhesion': adhesion,
            'material_transparency': material_transparency,
            'tensile_strength': tensile_strength,
            'tear_strength': tear_strength,
            'temp_resistance_min': temp_resistance_min,
            'temp_resistance_max': temp_resistance_max,
            # 认证
            'is_rohs': is_rohs,
            'is_reach': is_reach,
            'is_halogen_free': is_halogen_free,
            'fire_rating': fire_rating,
            # 附件
            'datasheet': datasheet,
            'datasheet_filename': datasheet_filename,
            'application': application,
            'process_note': process_note,
            # 溯源
            'source_catalog_variant_id': source_catalog_variant_id,
            # 供应商
            'main_vendor_id': self.main_vendor_id.id if self.main_vendor_id else False,
        }

        # 尝试匹配颜色
        v_color = item.variant_color if item else variant.variant_color
        if v_color:
            color = self.env['diecut.color'].search([('name', 'ilike', v_color.strip())], limit=1)
            if not color:
                color = self.env['diecut.color'].create({'name': v_color.strip()})
            new_product_vals['color_id'] = color.id

        new_product = self.env['product.template'].create(new_product_vals)

        # 标记原变体为已启用
        if item:
            item.with_context(skip_shadow_sync=True).write({
                'erp_enabled': True,
                'erp_product_tmpl_id': new_product.id,
            })
        else:
            variant.write({
                'is_activated': True,
                'activated_product_tmpl_id': new_product.id,
            })

        if self.env.context.get('from_gray_catalog_item'):
            if self.env.context.get('is_split_view_action'):
                return {'type': 'ir.actions.act_window_close', 'infos': {'noReload': True}}
            return {'type': 'ir.actions.client', 'tag': 'reload'}

        # 跳转到新创建的 ERP 产品表单
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'product.template',
            'res_id': new_product.id,
            'view_mode': 'form',
            'target': 'current',
        }
