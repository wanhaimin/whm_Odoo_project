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
        help="在 Dify -> Knowledge -> API Access 中获取（dataset-xxxx）。",
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
        help="所有 catalog.item（材料目录型号）会同步到此 Dataset，建议在 Dify 中单独建立 KB-Products。",
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
        help="AI 顾问对话应用入口，留空则禁用问答。",
    )
    diecut_kb_dify_chat_api_key = fields.Char(
        string="Dify Chat App API Key",
        config_parameter="diecut_knowledge.dify_chat_api_key",
        help="应用级 API Key（app-xxxx）。",
    )
    diecut_kb_compile_batch_limit = fields.Integer(
        string="AI 编译单次上限",
        config_parameter="diecut_knowledge.compile_batch_limit",
        default=5,
    )
    diecut_kb_compile_auto_publish = fields.Boolean(
        string="AI 编译后自动发布",
        config_parameter="diecut_knowledge.compile_auto_publish",
        default=True,
    )
    diecut_kb_incremental_wiki_batch_limit = fields.Integer(
        string="增量 Wiki 资料上限",
        config_parameter="diecut_knowledge.incremental_wiki_batch_limit",
        default=20,
    )
    diecut_kb_incremental_wiki_group_limit = fields.Integer(
        string="增量 Wiki 主题上限",
        config_parameter="diecut_knowledge.incremental_wiki_group_limit",
        default=5,
    )
    diecut_kb_incremental_wiki_context_article_limit = fields.Integer(
        string="增量 Wiki 候选页上限",
        config_parameter="diecut_knowledge.incremental_wiki_context_article_limit",
        default=12,
    )
    diecut_kb_lint_batch_limit = fields.Integer(
        string="知识治理单次检查上限",
        config_parameter="diecut_knowledge.lint_batch_limit",
        default=20,
    )

    # --- Claude API ---
    diecut_kb_ai_backend = fields.Selection(
        [("dify", "Dify"), ("claude", "Claude")],
        string="AI 后端",
        config_parameter="diecut_knowledge.ai_backend",
        default="dify",
        help="选择 AI 编译和问答使用的后端。切换后立即生效。",
    )
    diecut_kb_claude_api_key = fields.Char(
        string="Claude API Key",
        config_parameter="diecut_knowledge.claude_api_key",
        help="Anthropic API Key（sk-ant-xxxx）。",
    )
    diecut_kb_claude_model = fields.Selection(
        [
            ("claude-opus-4-7", "Claude Opus 4.7"),
            ("claude-sonnet-4-6", "Claude Sonnet 4.6"),
            ("claude-haiku-4-5", "Claude Haiku 4.5"),
        ],
        string="Claude 模型",
        config_parameter="diecut_knowledge.claude_model",
        default="claude-opus-4-7",
    )
    diecut_kb_claude_max_tokens = fields.Integer(
        string="最大输出 Token",
        config_parameter="diecut_knowledge.claude_max_tokens",
        default=4096,
    )
    diecut_kb_claude_base_url = fields.Char(
        string="Claude API 代理地址",
        config_parameter="diecut_knowledge.claude_base_url",
        help="可选，通过代理访问 Claude API 时填写。留空使用官方端点。",
    )

    diecut_kb_vault_root_path = fields.Char(
        string="Knowledge Vault 根目录",
        config_parameter="diecut_knowledge.vault_root_path",
        help="本地 raw/wiki 文件夹镜像根目录。建议使用项目外部目录，或使用已加入 .gitignore 的目录。",
    )
    diecut_kb_vault_raw_batch_limit = fields.Integer(
        string="Raw Inbox 扫描上限",
        config_parameter="diecut_knowledge.vault_raw_batch_limit",
        default=20,
    )
    diecut_kb_vault_scan_scope = fields.Selection(
        [
            ("all_raw", "全部 raw 资料"),
            ("inbox", "仅 raw/inbox"),
        ],
        string="Vault 扫描范围",
        config_parameter="diecut_knowledge.vault_scan_scope",
        default="all_raw",
    )
    diecut_kb_vault_raw_cron_active = fields.Boolean(
        string="Raw Inbox 定时扫描已启用",
        compute="_compute_diecut_kb_vault_raw_cron_active",
    )

    def _compute_diecut_kb_vault_raw_cron_active(self):
        cron = self.env.ref("diecut_knowledge.cron_scan_raw_inbox", raise_if_not_found=False)
        for record in self:
            record.diecut_kb_vault_raw_cron_active = bool(cron and cron.active)

    def action_init_knowledge_vault(self):
        self.ensure_one()
        from ..services.kb_vault_mirror import KbVaultMirror

        try:
            self._sync_vault_settings_to_config()
            root = KbVaultMirror(self.env).ensure_structure()
        except Exception as exc:
            return self._notify("danger", "Vault 初始化失败：%s" % exc)
        return self._notify("success", "Vault 已初始化：%s" % root)

    def action_scan_raw_inbox(self):
        self.ensure_one()

        try:
            self._sync_vault_settings_to_config()
        except Exception as exc:
            return self._notify("danger", "Vault 配置保存失败：%s" % exc)
        return self.env["diecut.catalog.source.document"].action_scan_raw_inbox()

    def action_enable_raw_inbox_cron(self):
        self.ensure_one()
        try:
            self._sync_vault_settings_to_config()
            cron = self.env.ref("diecut_knowledge.cron_scan_raw_inbox")
            cron.write({"active": True})
        except Exception as exc:
            return self._notify("danger", "启用 Raw Inbox 定时扫描失败：%s" % exc)
        return self._notify("success", "Raw Inbox 定时扫描已启用。")

    def action_disable_raw_inbox_cron(self):
        self.ensure_one()
        try:
            cron = self.env.ref("diecut_knowledge.cron_scan_raw_inbox")
            cron.write({"active": False})
        except Exception as exc:
            return self._notify("danger", "停用 Raw Inbox 定时扫描失败：%s" % exc)
        return self._notify("success", "Raw Inbox 定时扫描已停用。")

    def action_export_wiki_vault(self):
        self.ensure_one()
        from ..services.kb_vault_mirror import KbVaultMirror

        try:
            self._sync_vault_settings_to_config()
            result = KbVaultMirror(self.env).export_wiki()
        except Exception as exc:
            return self._notify("danger", "Wiki 导出失败：%s" % exc)
        return self._notify("success", "已导出 %s 篇 Wiki。" % result.get("exported", 0))

    def action_import_wiki_vault(self):
        self.ensure_one()
        from ..services.kb_vault_mirror import KbVaultMirror

        try:
            self._sync_vault_settings_to_config()
            result = KbVaultMirror(self.env).import_wiki_changes()
        except Exception as exc:
            return self._notify("danger", "Wiki 导入失败：%s" % exc)
        return self._notify(
            "success" if not result.get("errors") else "warning",
            "导入 %s，跳过 %s，错误 %s。"
            % (result.get("imported", 0), result.get("skipped", 0), len(result.get("errors") or [])),
        )

    def action_export_knowledge_graph(self):
        self.ensure_one()
        from ..services.kb_graph_exporter import KbGraphExporter

        try:
            self._sync_vault_settings_to_config()
            result = KbGraphExporter(self.env).export()
        except Exception as exc:
            return self._notify("danger", "Knowledge Graph 导出失败：%s" % exc)
        return self._notify(
            "success",
            "Knowledge Graph 已导出：%s 个节点，%s 条边，%s 个警告。路径：%s"
            % (result.get("nodes", 0), result.get("edges", 0), result.get("warnings", 0), result.get("path", "")),
        )

    def action_test_dify_connection(self):
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

    def _sync_vault_settings_to_config(self):
        config = self.env["ir.config_parameter"].sudo()
        if self.diecut_kb_vault_root_path:
            config.set_param("diecut_knowledge.vault_root_path", self.diecut_kb_vault_root_path)
        if self.diecut_kb_vault_raw_batch_limit:
            config.set_param("diecut_knowledge.vault_raw_batch_limit", self.diecut_kb_vault_raw_batch_limit)
        if self.diecut_kb_vault_scan_scope:
            config.set_param("diecut_knowledge.vault_scan_scope", self.diecut_kb_vault_scan_scope)

    def _notify(self, kind: str, message: str):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "知识库设置",
                "message": message,
                "type": kind,
                "sticky": False,
            },
        }
