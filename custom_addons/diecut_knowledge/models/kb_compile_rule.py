# -*- coding: utf-8 -*-

from odoo import api, fields, models


class DiecutKbCompileRule(models.Model):
    _name = "diecut.kb.compile.rule"
    _description = "知识编译规则"
    _order = "rule_type, priority desc, sequence, id"

    name = fields.Char(string="规则名称", required=True)
    rule_type = fields.Selection(
        [
            ("ingest_plan", "Ingest Plan"),
            ("wiki_compile", "Wiki 编译"),
            ("wiki_graph", "Wiki 图谱"),
            ("catalog_item", "材料条目编译"),
            ("comparison", "对比分析"),
            ("brand_overview", "品牌综述"),
            ("lint", "知识治理"),
            ("advisor", "AI 顾问"),
        ],
        string="规则类型",
        required=True,
        default="wiki_compile",
        index=True,
    )
    active = fields.Boolean(string="启用", default=True, index=True)
    priority = fields.Integer(string="优先级", default=10)
    sequence = fields.Integer(string="顺序", default=10)
    version = fields.Char(string="版本", default="v1")
    content = fields.Text(string="规则内容", required=True)
    schema_json = fields.Text(
        string="Schema JSON",
        help="机器可读的 LLM 输出契约；用于约束 Ingest Plan、Wiki Patch、Graph Patch、问答和 lint 输出。",
    )
    notes = fields.Text(string="备注")

    def action_enable(self):
        self.write({"active": True})

    def action_disable(self):
        self.write({"active": False})

    @api.model
    def _deactivate_legacy_rules(self):
        legacy_rules = self.sudo().search([("priority", "<", 1000)])
        legacy_rules.write({
            "active": False,
            "notes": "历史默认规则，已由 Schema v1 规则替代；保留用于回滚和审计。",
        })
        return True

    @api.model
    def build_system_prompt(self, rule_type, fallback_prompt=""):
        """Append enabled domain rules to the built-in prompt.

        The built-in prompt stays as a safety baseline; editable records are the
        project-specific schema that lets the wiki evolve without code changes.
        """
        rules = self.sudo().search(
            [("active", "=", True), ("rule_type", "=", rule_type)],
            order="priority desc, sequence asc, id asc",
        )
        schema_rules = rules.filtered(lambda rule: rule.priority >= 1000)
        if schema_rules:
            rules = schema_rules
        if not rules:
            return fallback_prompt or ""

        sections = [fallback_prompt.strip()] if fallback_prompt else []
        sections.append("以下是当前 Odoo 知识库启用的可维护编译规则，必须优先遵守：")
        for rule in rules:
            schema = (rule.schema_json or "").strip()
            sections.append(
                "\n".join(
                    list(
                        filter(
                            None,
                            [
                                f"【规则：{rule.name} / {rule.version or 'v1'}】",
                                (rule.content or "").strip(),
                                "【必须遵守的 JSON Schema】\n%s" % schema if schema else "",
                            ],
                        )
                    )
                )
            )
        return "\n\n".join(section for section in sections if section)
