# -*- coding: utf-8 -*-
"""通过 _inherit 给 diecut.catalog.item 加 Dify 同步字段和动作。

设计：
- 字段命名 dify_* 前缀，避免和 catalog 已有字段冲突
- 标 pending 用 write 钩子（仅当业务字段变化时）
- 动作不抛异常：失败仅写 dify_sync_error
"""

from odoo import api, fields, models

# 写入这些字段时才触发 sync_status -> pending（避免内部状态字段写入引发循环）
_BUSINESS_FIELDS = {
    "name", "code", "brand_id", "series_id", "categ_id", "manufacturer_id",
    "thickness", "thickness_std", "adhesive_thickness",
    "color_id", "adhesive_type_id", "base_material_id",
    "is_rohs", "is_reach", "is_halogen_free", "fire_rating",
    "catalog_status", "active",
    "product_features", "product_description", "main_applications",
    "special_applications", "equivalent_type",
    "spec_line_ids",
    "function_tag_ids", "application_tag_ids", "feature_tag_ids",
}

_INTERNAL_FIELDS = {
    "dify_sync_status", "dify_dataset_id", "dify_document_id",
    "dify_last_sync_at", "dify_sync_error",
}


class DiecutCatalogItem(models.Model):
    _inherit = "diecut.catalog.item"

    dify_sync_status = fields.Selection(
        [
            ("pending", "待同步"),
            ("synced", "已同步"),
            ("failed", "同步失败"),
            ("skipped", "已跳过"),
        ],
        string="Dify 同步状态",
        default="pending",
        index=True,
        copy=False,
    )
    dify_dataset_id = fields.Char(string="Dify 知识库ID", readonly=True, copy=False)
    dify_document_id = fields.Char(string="Dify 文档ID", readonly=True, copy=False)
    dify_last_sync_at = fields.Datetime(string="最近同步时间", readonly=True, copy=False)
    dify_sync_error = fields.Text(string="同步错误", readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault("dify_sync_status", "pending")
        return super().create(vals_list)

    def write(self, vals):
        triggers_sync = bool(_BUSINESS_FIELDS & set(vals.keys())) and not (
            set(vals.keys()) <= _INTERNAL_FIELDS
        )
        result = super().write(vals)
        if triggers_sync:
            for record in self:
                if record.dify_sync_status == "synced":
                    super(DiecutCatalogItem, record).write({"dify_sync_status": "pending"})
        return result

    def action_dify_sync_now(self):
        """立即同步当前选中的产品到 Dify。"""
        from ..services.dify_product_sync import DifyProductSync

        sync = DifyProductSync(self.env)
        ok_count, fail_count, skip_count = 0, 0, 0
        for item in self:
            result = sync.sync_item(item)
            if result.get("action") == "skip":
                skip_count += 1
            elif result.get("ok"):
                ok_count += 1
            else:
                fail_count += 1
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "产品 → Dify 同步",
                "message": f"成功 {ok_count} 个 / 失败 {fail_count} 个 / 跳过 {skip_count} 个",
                "type": "success" if fail_count == 0 else "warning",
                "sticky": False,
            },
        }

    def action_dify_mark_pending(self):
        self.write({"dify_sync_status": "pending"})
        return True

    def action_open_ai_advisor(self):
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "diecut_ai_advisor",
            "params": {
                "model": self._name,
                "record_id": self.id,
                "record_name": f"[{self.brand_id.name or ''}] {self.code or ''} {self.name or ''}".strip(),
            },
        }

    @api.model
    def cron_dify_sync_pending_items(self):
        from ..services.dify_product_sync import DifyProductSync

        return DifyProductSync(self.env).sync_pending()
