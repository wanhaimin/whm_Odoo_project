# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    diecut_kb_dify_base_url = fields.Char(
        string="Dify API 地址",
        config_parameter="diecut_knowledge.dify_base_url",
        help="例如：http://dify.local:5001 或 https://api.dify.ai",
    )
    diecut_kb_dify_api_key = fields.Char(
        string="Dify Dataset API Key",
        config_parameter="diecut_knowledge.dify_api_key",
        help="在 Dify → Knowledge → API Access 中获取（dataset-xxxx）",
    )
    diecut_kb_dify_timeout = fields.Integer(
        string="请求超时(秒)",
        config_parameter="diecut_knowledge.dify_timeout",
        default=30,
    )
    diecut_kb_dify_retries = fields.Integer(
        string="重试次数",
        config_parameter="diecut_knowledge.dify_retries",
        default=2,
    )
    diecut_kb_dify_batch_limit = fields.Integer(
        string="单次定时同步上限",
        config_parameter="diecut_knowledge.dify_batch_limit",
        default=20,
    )
    diecut_kb_attachment_batch_limit = fields.Integer(
        string="附件解析单次上限",
        config_parameter="diecut_knowledge.attachment_batch_limit",
        default=10,
        help="cron 自动扫描时，一次最多解析多少个附件。",
    )
    diecut_kb_dify_products_dataset_id = fields.Char(
        string="产品库 Dify Dataset ID",
        config_parameter="diecut_knowledge.dify_products_dataset_id",
        help="所有 catalog.item（材料目录型号）会同步到此 Dataset。建议在 Dify 中单独建一个 KB-Products。",
    )
    diecut_kb_dify_products_batch_limit = fields.Integer(
        string="产品同步单次上限",
        config_parameter="diecut_knowledge.dify_products_batch_limit",
        default=50,
    )
    diecut_kb_dify_products_min_status = fields.Selection(
        [
            ("draft", "草稿及以上"),
            ("review", "评审中及以上"),
            ("published", "仅已发布"),
        ],
        string="同步阈值",
        config_parameter="diecut_knowledge.dify_products_min_status",
        default="published",
        help="只同步 catalog_status 达到此阈值的产品。",
    )

    diecut_kb_dify_chat_app_url = fields.Char(
        string="Dify Chat App API 地址",
        config_parameter="diecut_knowledge.dify_chat_app_url",
        help="（Phase 3 用）AI 抽屉对话应用入口，留空则禁用问答。",
    )
    diecut_kb_dify_chat_api_key = fields.Char(
        string="Dify Chat App API Key",
        config_parameter="diecut_knowledge.dify_chat_api_key",
        help="（Phase 3 用）应用级 API Key（app-xxxx）。",
    )

    def action_test_dify_connection(self):
        """点击「测试连接」时调一次 list_datasets，把结果反馈给用户。"""
        self.ensure_one()
        from ..services.dify_client import DifyClient

        base_url = self.diecut_kb_dify_base_url or self.env["ir.config_parameter"].sudo().get_param(
            "diecut_knowledge.dify_base_url"
        )
        api_key = self.diecut_kb_dify_api_key or self.env["ir.config_parameter"].sudo().get_param(
            "diecut_knowledge.dify_api_key"
        )
        if not base_url or not api_key:
            return self._notify("warning", "请先填写 Dify API 地址和 Dataset API Key。")
        try:
            client = DifyClient(base_url=base_url, api_key=api_key, timeout=15, retries=0)
            ok, payload, error, _duration = client.list_datasets(page=1, limit=5)
        except Exception as exc:
            return self._notify("danger", f"连接失败：{exc}")
        if not ok:
            return self._notify("danger", f"连接失败：{error}")
        total = (payload or {}).get("total") or len((payload or {}).get("data") or [])
        return self._notify("success", f"连接成功。当前可见 Dataset 数量：{total}")

    def _notify(self, kind: str, message: str):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Dify 连接测试",
                "message": message,
                "type": kind,
                "sticky": False,
            },
        }
