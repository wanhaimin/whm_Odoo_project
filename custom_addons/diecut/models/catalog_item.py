# -*- coding: utf-8 -*-

import re

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class DiecutCatalogItem(models.Model):
    _name = "diecut.catalog.item"
    _description = "材料选型目录"
    _order = "brand_id, sequence, id"

    name = fields.Char(string="名称", required=True)
    active = fields.Boolean(string="启用", default=True)
    sequence = fields.Integer(string="排序", default=10)

    brand_id = fields.Many2one("diecut.brand", string="品牌", required=True, index=True)
    categ_id = fields.Many2one("product.category", string="材料分类", index=True)

    code = fields.Char(string="型号编码", index=True)
    series_text = fields.Char(string="系列")

    catalog_status = fields.Selection(
        [
            ("draft", "草稿"),
            ("review", "评审中"),
            ("published", "已发布"),
            ("deprecated", "已停产"),
        ],
        string="目录状态",
        default="draft",
        index=True,
    )

    erp_enabled = fields.Boolean(string="已启用ERP", default=False, index=True, readonly=True)
    erp_product_tmpl_id = fields.Many2one("product.template", string="ERP产品", readonly=True, copy=False)
    variant_thickness = fields.Char(string="厚度")
    variant_adhesive_thickness = fields.Char(string="胶厚", help="如：13/13、35/40（双面胶厚）")
    variant_color = fields.Char(string="颜色")
    variant_peel_strength = fields.Char(string="剥离力", help="如：>800 gf/inch、A>1000 B>800")
    variant_structure = fields.Char(string="结构描述", help="如：胶+PET+胶+白色LXZ")
    variant_adhesive_type = fields.Char(string="胶系(变体)")
    variant_base_material = fields.Char(string="基材(变体)")
    variant_sus_peel = fields.Char(string="SUS面剥离力", help="如：13.0/13.0 N/cm")
    variant_pe_peel = fields.Char(string="PE面剥离力", help="如：7.0/7.0 N/cm")
    variant_dupont = fields.Char(string="DuPont冲击", help="如：0.7/0.1、1.3/1.0 [A×cM]")
    variant_push_force = fields.Char(string="推出力", help="如：229 N")
    variant_removability = fields.Char(string="可移除性", help="如：*、**、***（与同品类比较）")
    variant_tumbler = fields.Char(string="Tumbler滚球", help="如：Upon request、40.0")
    variant_holding_power = fields.Char(string="保持力", help="如：4.0 N/cm")
    variant_thickness_std = fields.Char(string="厚度(标准)")
    variant_color_std = fields.Char(string="颜色(标准)")
    variant_adhesive_std = fields.Char(string="胶系(标准)")
    variant_base_material_std = fields.Char(string="基材(标准)")
    variant_ref_price = fields.Float(string="参考单价", digits=(16, 4))
    variant_is_rohs = fields.Boolean(string="ROHS", default=False)
    variant_is_reach = fields.Boolean(string="REACH", default=False)
    variant_is_halogen_free = fields.Boolean(string="无卤", default=False)
    variant_tds_file = fields.Binary(string="TDS技术数据表")
    variant_tds_filename = fields.Char(string="TDS文件名")
    variant_msds_file = fields.Binary(string="MSDS安全数据表")
    variant_msds_filename = fields.Char(string="MSDS文件名")
    variant_datasheet = fields.Binary(string="规格书")
    variant_datasheet_filename = fields.Char(string="规格书文件名")
    variant_catalog_structure_image = fields.Binary(string="产品结构图")
    variant_fire_rating = fields.Selection(
        [
            ("ul94_v0", "UL94 V-0"),
            ("ul94_v1", "UL94 V-1"),
            ("ul94_v2", "UL94 V-2"),
            ("ul94_hb", "UL94 HB"),
            ("none", "无"),
        ],
        string="防火等级",
        default="none",
    )
    is_duplicate_key = fields.Boolean(
        string="编码重复",
        compute="_compute_is_duplicate_key",
        search="_search_is_duplicate_key",
    )

    @api.model
    def _get_duplicate_model_ids(self):
        self.env.cr.execute(
            """
            WITH dup AS (
                SELECT brand_id, lower(trim(code)) AS code_key
                  FROM diecut_catalog_item
                 WHERE code IS NOT NULL
                   AND trim(code) <> ''
                 GROUP BY brand_id, lower(trim(code))
                HAVING COUNT(*) > 1
            )
            SELECT i.id
              FROM diecut_catalog_item i
               JOIN dup d
                 ON d.brand_id = i.brand_id
                AND d.code_key = lower(trim(i.code))
             WHERE i.code IS NOT NULL
               AND trim(i.code) <> ''
            """
        )
        return [row[0] for row in self.env.cr.fetchall()]

    def _compute_is_duplicate_key(self):
        duplicate_ids = set(self._get_duplicate_model_ids())
        for record in self:
            record.is_duplicate_key = bool(record.id in duplicate_ids)

    @api.model
    def _search_is_duplicate_key(self, operator, value):
        if operator not in ("=", "!="):
            raise ValidationError("编码重复筛选仅支持 '=' 或 '!='。")
        duplicate_ids = self._get_duplicate_model_ids()
        positive = (operator == "=" and bool(value)) or (operator == "!=" and not bool(value))
        if positive:
            return [("id", "in", duplicate_ids or [0])]
        return [("id", "not in", duplicate_ids or [0])]

    # ---------- 归一化：原文 -> 标准值（与 product.product 一致，厚度只取标准值） ----------
    _STD_RAW_KEYS = {"variant_thickness", "variant_color", "variant_adhesive_type", "variant_base_material"}
    _STD_KEYS = {"variant_thickness_std", "variant_color_std", "variant_adhesive_std", "variant_base_material_std"}

    @staticmethod
    def _normalize_text_std(value):
        """文本归一化：去多余空白，与旧模型一致。"""
        if not value:
            return False
        normalized = re.sub(r"\s+", " ", (value or "").strip())
        return normalized or False

    @staticmethod
    def _normalize_thickness_std(thickness_text):
        """将原始厚度文本归一为标准厚度（只取数字，统一到 um）。与旧模型一致。"""
        if not thickness_text:
            return False
        s = (thickness_text or "").lower().replace("μm", "um").replace("µm", "um").replace(" ", "")
        match = re.search(r"(\d+(?:\.\d+)?)", s)
        if not match:
            return False
        val = float(match.group(1))
        is_um = "um" in s
        is_mm = "mm" in s and not is_um
        if is_um:
            um_val = val
        elif is_mm:
            um_val = val * 1000.0
        else:
            um_val = val if val > 10 else (val * 1000.0)
        rounded = round(um_val, 1)
        if rounded.is_integer():
            return f"{int(rounded)}μm"
        return f"{rounded:g}μm"

    @classmethod
    def _build_variant_std_vals_from_raw(cls, vals):
        """从原文字段计算标准字段：厚度只取标准值（Xum），颜色/胶系/基材做文本归一化。"""
        std_vals = {}
        if "variant_thickness" in vals:
            std_vals["variant_thickness_std"] = cls._normalize_thickness_std(vals.get("variant_thickness"))
        if "variant_color" in vals:
            std_vals["variant_color_std"] = cls._normalize_text_std(vals.get("variant_color"))
        if "variant_adhesive_type" in vals:
            std_vals["variant_adhesive_std"] = cls._normalize_text_std(vals.get("variant_adhesive_type"))
        if "variant_base_material" in vals:
            std_vals["variant_base_material_std"] = cls._normalize_text_std(vals.get("variant_base_material"))
        return std_vals

    def _build_variant_std_vals(self):
        """当前记录的原文 -> 标准值。"""
        self.ensure_one()
        return self._build_variant_std_vals_from_raw(
            {
                "variant_thickness": self.variant_thickness,
                "variant_color": self.variant_color,
                "variant_adhesive_type": self.variant_adhesive_type,
                "variant_base_material": self.variant_base_material,
            }
        )

    def _ensure_model_record(self):
        self.ensure_one()
        if not self.code:
            raise UserError("仅型号条目支持该操作。")
        return True

    def action_activate_to_erp(self):
        self._ensure_model_record()

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'diecut.catalog.activate.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_catalog_item_id': self.id,
                'from_gray_catalog_item': True,
                'is_split_view_action': self.env.context.get('is_split_view_action', False)
            }
        }

    def action_view_erp_product(self):
        self._ensure_model_record()
        if not self.erp_enabled or not self.erp_product_tmpl_id:
            raise UserError("该型号尚未关联ERP产品。")

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'product.template',
            'res_id': self.erp_product_tmpl_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("code"):
                vals["code"] = vals["code"].strip()
            if vals.get("series_text"):
                vals["series_text"] = vals["series_text"].strip()
        records = super().create(vals_list)
        # 若未显式传入标准字段，则从原文自动归一化（厚度只取标准值）
        for idx, record in enumerate(records):
            incoming = vals_list[idx] if idx < len(vals_list) else {}
            if self._STD_KEYS.intersection(incoming.keys()):
                continue
            auto_vals = self._build_variant_std_vals_from_raw(incoming)
            if auto_vals:
                record.write(auto_vals)
        return records

    def write(self, vals):
        if vals.get("code"):
            vals["code"] = vals["code"].strip()
        if vals.get("series_text"):
            vals["series_text"] = vals["series_text"].strip()
        res = super().write(vals)
        # 修改了原文且未显式传入标准字段时，自动用原文归一化（厚度只取标准值）
        if self._STD_RAW_KEYS.intersection(vals.keys()) and not self._STD_KEYS.intersection(vals.keys()):
            for record in self:
                auto_vals = record._build_variant_std_vals()
                if auto_vals:
                    record.write(auto_vals)
        return res

    @api.constrains("brand_id", "code")
    def _check_structure_rules(self):
        for record in self:
            if not record.code:
                raise ValidationError("型号编码不能为空。")
            if not record.brand_id:
                raise ValidationError("品牌不能为空。")

    def init(self):
        super().init()
        cr = self.env.cr
        cr.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS diecut_catalog_item_model_brand_code_uidx
            ON diecut_catalog_item (brand_id, lower(trim(code)))
            WHERE code IS NOT NULL AND trim(code) <> ''
            """
        )
