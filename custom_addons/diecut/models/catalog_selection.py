# -*- coding: utf-8 -*-

import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class DiecutCatalogBrandPlatform(models.Model):
    _name = "diecut.catalog.brand.platform"
    _description = "品牌平台"
    _order = "brand_id, sequence, name, id"

    name = fields.Char(string="平台名称", required=True, index=True)
    brand_id = fields.Many2one("diecut.brand", string="品牌", required=True, index=True)
    code = fields.Char(string="平台编码", index=True)
    alias_text = fields.Text(string="别名/同义词")
    description = fields.Text(string="平台说明")
    application_summary = fields.Text(string="典型应用")
    feature_summary = fields.Text(string="平台特点")
    active = fields.Boolean(string="启用", default=True)
    sequence = fields.Integer(string="排序", default=10)
    note = fields.Text(string="备注")

    _sql_constraints = [
        ("diecut_catalog_brand_platform_brand_name_uniq", "unique(brand_id, name)", "同一品牌下平台名称不能重复。"),
    ]

    @staticmethod
    def _normalize_name(value):
        if not value:
            return False
        text = re.sub(r"\s+", " ", str(value).strip())
        return text or False

    @classmethod
    def _normalize_alias_text(cls, value):
        if not value:
            return False
        parts = re.split(r"[\n,;，；]+", str(value))
        normalized = []
        seen = set()
        for part in parts:
            alias = cls._normalize_name(part)
            if alias and alias.casefold() not in seen:
                seen.add(alias.casefold())
                normalized.append(alias)
        return "\n".join(normalized) if normalized else False

    @classmethod
    def _normalize_optional_text(cls, value):
        text = cls._normalize_name(value)
        return text or False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "name" in vals:
                vals["name"] = self._normalize_name(vals.get("name"))
            if "code" in vals:
                vals["code"] = self._normalize_optional_text(vals.get("code"))
            if "alias_text" in vals:
                vals["alias_text"] = self._normalize_alias_text(vals.get("alias_text"))
            for key in ("description", "application_summary", "feature_summary", "note"):
                if key in vals:
                    vals[key] = self._normalize_optional_text(vals.get(key))
        return super().create(vals_list)

    def write(self, vals):
        vals = dict(vals)
        if "name" in vals:
            vals["name"] = self._normalize_name(vals.get("name"))
        if "code" in vals:
            vals["code"] = self._normalize_optional_text(vals.get("code"))
        if "alias_text" in vals:
            vals["alias_text"] = self._normalize_alias_text(vals.get("alias_text"))
        for key in ("description", "application_summary", "feature_summary", "note"):
            if key in vals:
                vals[key] = self._normalize_optional_text(vals.get(key))
        return super().write(vals)

    @api.constrains("name")
    def _check_name(self):
        for record in self:
            if not record.name:
                raise ValidationError("平台名称不能为空。")

    @api.model
    def _name_search(self, name="", args=None, operator="ilike", limit=100, name_get_uid=None):
        args = list(args or [])
        if name:
            args = [
                "&",
                "|",
                "|",
                ("name", operator, name),
                ("code", operator, name),
                ("alias_text", operator, name),
            ] + args
        model = self.with_user(name_get_uid) if name_get_uid else self
        return model._search(args, limit=limit)

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=100):
        records = self.search(
            list(domain or [])
            + (
                ["|", "|", ("name", operator, name), ("code", operator, name), ("alias_text", operator, name)]
                if name
                else []
            ),
            limit=limit,
        )
        return [(record.id, record.display_name) for record in records]

    def name_get(self):
        return [(record.id, f"{record.brand_id.name} / {record.name}") for record in self]


class DiecutCatalogSelectionScene(models.Model):
    _name = "diecut.catalog.selection.scene"
    _description = "选型场景"
    _order = "parent_path, sequence, name, id"
    _parent_name = "parent_id"
    _parent_store = True
    _rec_name = "complete_name"

    name = fields.Char(string="场景名称", required=True, index=True)
    parent_id = fields.Many2one("diecut.catalog.selection.scene", string="上级场景", index=True, ondelete="restrict")
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many("diecut.catalog.selection.scene", "parent_id", string="下级场景")
    complete_name = fields.Char(string="完整路径", compute="_compute_complete_name", store=True, recursive=True, index=True)
    alias_text = fields.Text(string="别名/同义词")
    description = fields.Text(string="场景说明")
    selection_tip = fields.Text(string="选型提示")
    active = fields.Boolean(string="启用", default=True)
    sequence = fields.Integer(string="排序", default=10)
    note = fields.Text(string="备注")
    is_leaf = fields.Boolean(string="叶子节点", compute="_compute_is_leaf", store=True)

    _sql_constraints = [
        ("diecut_catalog_selection_scene_parent_name_uniq", "unique(parent_id, name)", "同一层级下场景名称不能重复。"),
    ]

    @staticmethod
    def _normalize_name(value):
        if not value:
            return False
        text = re.sub(r"\s+", " ", str(value).strip())
        return text or False

    @classmethod
    def _normalize_alias_text(cls, value):
        if not value:
            return False
        parts = re.split(r"[\n,;，；]+", str(value))
        normalized = []
        seen = set()
        for part in parts:
            alias = cls._normalize_name(part)
            if alias and alias.casefold() not in seen:
                seen.add(alias.casefold())
                normalized.append(alias)
        return "\n".join(normalized) if normalized else False

    @classmethod
    def _normalize_optional_text(cls, value):
        text = cls._normalize_name(value)
        return text or False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "name" in vals:
                vals["name"] = self._normalize_name(vals.get("name"))
            if "alias_text" in vals:
                vals["alias_text"] = self._normalize_alias_text(vals.get("alias_text"))
            for key in ("description", "selection_tip", "note"):
                if key in vals:
                    vals[key] = self._normalize_optional_text(vals.get(key))
        return super().create(vals_list)

    def write(self, vals):
        vals = dict(vals)
        if "name" in vals:
            vals["name"] = self._normalize_name(vals.get("name"))
        if "alias_text" in vals:
            vals["alias_text"] = self._normalize_alias_text(vals.get("alias_text"))
        for key in ("description", "selection_tip", "note"):
            if key in vals:
                vals[key] = self._normalize_optional_text(vals.get(key))
        return super().write(vals)

    @api.depends("name", "parent_id.complete_name")
    def _compute_complete_name(self):
        for record in self:
            if record.parent_id:
                record.complete_name = f"{record.parent_id.complete_name} / {record.name}"
            else:
                record.complete_name = record.name

    @api.depends("child_ids")
    def _compute_is_leaf(self):
        for record in self:
            record.is_leaf = not bool(record.child_ids)

    @api.constrains("name")
    def _check_name(self):
        for record in self:
            if not record.name:
                raise ValidationError("场景名称不能为空。")

    @api.model
    def _name_search(self, name="", args=None, operator="ilike", limit=100, name_get_uid=None):
        args = list(args or [])
        if name:
            args = [
                "&",
                "|",
                "|",
                ("name", operator, name),
                ("complete_name", operator, name),
                ("alias_text", operator, name),
            ] + args
        model = self.with_user(name_get_uid) if name_get_uid else self
        return model._search(args, limit=limit)

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=100):
        records = self.search(
            list(domain or [])
            + (
                ["|", "|", ("name", operator, name), ("complete_name", operator, name), ("alias_text", operator, name)]
                if name
                else []
            ),
            limit=limit,
        )
        return [(record.id, record.display_name) for record in records]
