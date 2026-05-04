# -*- coding: utf-8 -*-

import json
import logging

from odoo import fields

from .prompt_loader import build_system_prompt

_logger = logging.getLogger(__name__)

_DEFAULT_LLM_LINT_PROMPT = """
你是企业 Wiki 的知识治理专家。请对给定的 Wiki 页面进行全面审计。

检查范围：
1. 内容质量：是否覆盖了概述、关键事实、应用场景、选型建议、风险与限制这些核心结构。
2. 过时声明：是否引用了已经过时的参数或已停止的型号。
3. 孤立风险：页面是否缺少入链或出链，无法融入知识图谱。
4. 数据缺口：正文中是否缺少可补充的关键参数、应用场景或来源引用。
5. 可扩展方向：根据当前内容，建议该 Wiki 下一步可以补充什么内容或搜索什么新资料。

输出 JSON 格式，不要输出 Markdown 或解释。

JSON 格式：
{
  "issues": [
    {
      "severity": "info|warning|error",
      "issue_type": "llm_content_gap|llm_stale_claim|llm_orphan_suggestion|llm_missing_structure|llm_research_direction",
      "summary": "问题描述",
      "suggestion": "修复建议"
    }
  ],
  "research_directions": ["建议检索的新资料方向"],
  "confidence": 0.0
}
""".strip()


class KbLinter:
    def __init__(self, env):
        self.env = env

    def _build_client(self):
        from .llm_client_factory import build_chat_client

        client, error, _profile = build_chat_client(
            self.env,
            model_profile_id=self.env.context.get("llm_model_profile_id"),
            purpose="wiki_compile",
        )
        if error:
            _logger.warning("Failed to build LLM client for lint: %s", error)
        return client

    def lint_article(self, article):
        article.ensure_one()
        issues = []

        # 规则型检查
        self._rule_checks(article, issues)
        # 主动矛盾检测
        self._detect_contradictions(article, issues)
        # LLM 支持治理检查
        self._llm_lint_article(article, issues)

        self._refresh_logs(article, issues)
        article.write({
            "last_linted_at": fields.Datetime.now(),
            "lint_issue_count": len(issues),
        })
        return {"total": len(issues), "issues": issues}

    def lint_pending(self, limit=20):
        articles = self.env["diecut.kb.article"].search(
            [("state", "=", "published")],
            limit=limit,
            order="last_linted_at asc, write_date desc, id desc",
        )
        counts = 0
        for article in articles:
            self.lint_article(article)
            counts += 1
        return {"total": counts}

    def _rule_checks(self, article, issues):
        if article.content_length < 150:
            issues.append(("info", "content_short", "文章内容偏短，建议补充应用场景、参数或风险限制。"))
        if article.sync_status == "failed":
            issues.append(("warning", "sync_failed", "文章同步到 Dify 失败，建议先修复同步错误。"))
        if not (article.related_brand_ids or article.related_item_ids or article.related_article_ids):
            issues.append(("info", "missing_reference", "文章缺少关联品牌、型号或相关文章，建议补充交叉引用。"))
        if article.graph_degree == 0:
            issues.append(("warning", "orphan_wiki", "Wiki 页面没有入链或出链，无法形成知识图谱，建议补充旧 Wiki 关联。"))
        if article.compile_source != "manual" and not article.citation_ids:
            issues.append(("warning", "missing_citation", "AI 编译页面缺少来源引用，发布前建议补充 raw source 和页码。"))
        if article.inbound_link_count == 0 and article.state == "published":
            issues.append(("info", "missing_inbound_link", "已发布 Wiki 没有其他页面指向它，建议运行图谱关联或加入索引枢纽页。"))
        conflict_count = self.env["diecut.kb.wiki.link"].search_count([
            "|",
            ("source_article_id", "=", article.id),
            ("target_article_id", "=", article.id),
            ("link_type", "=", "contradicts"),
            ("active", "=", True),
        ])
        if conflict_count:
            issues.append(("warning", "open_conflict_link", "Wiki 图谱中存在冲突关系，请人工复核后决定保留、更新或合并。"))
        if article.compile_source == "catalog_item" and article.compile_source_item_id:
            source = article.compile_source_item_id
            if article.compiled_hash and source.compile_hash and article.compiled_hash != source.compile_hash:
                issues.append(("warning", "stale_compile", "源产品参数已变化，当前编译文章可能过期，建议重新编译。"))
            if article.compiled_at and source.write_date and source.write_date > article.compiled_at:
                issues.append(("warning", "stale_compile", "源产品最近有更新，建议重新编译本文。"))
            if source.code and source.code not in (article.content_text or ""):
                issues.append(("info", "weak_source_binding", "文章正文里没有明显提到源产品型号，建议加强源数据映射。"))

        same_title_count = self.env["diecut.kb.article"].search_count([
            ("id", "!=", article.id),
            ("active", "=", True),
            ("name", "=", article.name),
        ])
        if same_title_count:
            issues.append(("info", "duplicate_title", "存在标题相同的其他知识文章，建议确认是否重复沉淀。"))

    def _llm_lint_article(self, article, issues):
        client = self._build_client()
        if not client:
            return
        if article.state not in ("review", "published"):
            return
        text = (article.content_text or article.content_md or "")[:6000]
        if not text.strip():
            return

        context = {
            "article_id": article.id,
            "title": article.name,
            "wiki_page_type": article.wiki_page_type or "",
            "summary": article.summary or "",
            "keywords": article.keywords or "",
            "content_text": text,
            "related_brands": article.related_brand_ids.mapped("name"),
            "related_items": article.related_item_ids.mapped("code"),
            "graph_degree": article.graph_degree,
            "citation_count": article.citation_count,
            "inbound_links": article.inbound_link_count,
            "outbound_links": article.outbound_link_count,
        }

        ok, payload, error, _duration = client.chat_messages(
            query="请审计以下 Wiki 页面：\n\n%s" % json.dumps(context, ensure_ascii=False, indent=2),
            user="kb-linter-%s" % self.env.user.id,
            inputs={"system": build_system_prompt("wiki_lint", _DEFAULT_LLM_LINT_PROMPT)},
        )
        if not ok:
            _logger.warning("LLM lint failed for article %s: %s", article.id, error)
            return

        raw = (payload or {}).get("answer", "")
        try:
            result = json.loads(raw) if raw.strip().startswith("{") else {}
        except (json.JSONDecodeError, ValueError):
            result = {}

        for row in result.get("issues") or []:
            severity = row.get("severity") if row.get("severity") in ("info", "warning", "error") else "info"
            issue_type = row.get("issue_type") or "llm_content_gap"
            summary = (row.get("summary") or "LLM 审计发现问题。")[:200]
            issues.append((severity, issue_type, summary))

        research = result.get("research_directions") or []
        if research:
            summary = "LLM 建议的可扩展方向：%s" % "；".join(research[:5])
            issues.append(("info", "llm_research_direction", summary))

    def _detect_contradictions(self, article, issues):
        if article.state not in ("review", "published"):
            return

        item_ids = set(article.related_item_ids.ids)
        if article.compile_source_item_id:
            item_ids.add(article.compile_source_item_id.id)
        if not item_ids:
            return

        Article = self.env["diecut.kb.article"]
        Link = self.env["diecut.kb.wiki.link"].sudo()

        others = Article.search([
            ("id", "!=", article.id),
            ("active", "=", True),
            ("state", "in", ("review", "published")),
            "|",
            ("compile_source_item_id", "in", list(item_ids)),
            ("related_item_ids", "in", list(item_ids)),
        ])
        if not others:
            return

        for other in others:
            other_item_ids = set(other.related_item_ids.ids)
            if other.compile_source_item_id:
                other_item_ids.add(other.compile_source_item_id.id)
            shared = item_ids & other_item_ids
            if not shared:
                continue

            for item_id in shared:
                item = self.env["diecut.catalog.item"].browse(item_id)
                if not item.exists():
                    continue

                key_params = self._extract_key_item_params(item)
                if not key_params:
                    continue

                text_a = article.content_text or ""
                text_b = other.content_text or ""
                params_a = self._find_param_values(text_a, key_params)
                params_b = self._find_param_values(text_b, key_params)

                for param_name, current_val in key_params.items():
                    val_a = params_a.get(param_name)
                    val_b = params_b.get(param_name)
                    if not val_a or not val_b:
                        continue
                    if val_a == val_b:
                        continue

                    item_label = item.code or item.name or "ID:%s" % item_id
                    summary = (
                        "产品【%s】的参数「%s」在本文章中"
                        "描述为「%s」，但在关联文章《%s》中"
                        "描述为「%s」。当前产品数据值为「%s」。"
                        % (item_label, param_name, val_a, other.name, val_b, current_val)
                    )
                    issues.append(("warning", "contradiction", summary))

                    for src, tgt, reason_prefix in [
                        (article, other, "本文描述"),
                        (other, article, "《%s》描述" % article.name),
                    ]:
                        existing = Link.search([
                            ("source_article_id", "=", src.id),
                            ("target_article_id", "=", tgt.id),
                            ("link_type", "=", "contradicts"),
                        ], limit=1)
                        if not existing:
                            Link.create({
                                "source_article_id": src.id,
                                "target_article_id": tgt.id,
                                "link_type": "contradicts",
                                "anchor_text": tgt.name,
                                "reason": (
                                    "%s中产品【%s】的"
                                    "参数「%s」为「%s」，"
                                    "对方描述为「%s」，数据当前值为「%s」"
                                    % (reason_prefix, item_label, param_name, val_a, val_b, current_val)
                                ),
                                "confidence": 0.85,
                            })

    @staticmethod
    def _extract_key_item_params(item):
        params = {}
        main_fields = [
            ("thickness", item.thickness),
            ("adhesive_thickness", item.adhesive_thickness),
            ("adhesive_type", item.adhesive_type_id.name if item.adhesive_type_id else ""),
            ("base_material", item.base_material_id.name if item.base_material_id else ""),
            ("fire_rating", item.fire_rating),
        ]
        for name, value in main_fields:
            if value:
                params[name] = str(value).strip()

        count = 0
        for line in item.spec_line_ids.sorted(key=lambda r: (r.sequence, r.id)):
            if count >= 10:
                break
            pname = line.param_name or (line.param_id.name if line.param_id else "")
            if not pname:
                continue
            pval = line.value_display or ""
            if not pval:
                continue
            params[pname] = pval.strip()
            count += 1
        return params

    @staticmethod
    def _find_param_values(text, key_params):
        import re
        found = {}
        for param_name in key_params:
            escaped = re.escape(param_name)
            patterns = [
                re.compile(r"%s[:：]\s*(.{0,40}?)(?:[。\n]|$)" % escaped, re.I | re.S),
                re.compile(r"%s\s+(.{0,40}?)(?:[。\n]|$)" % escaped, re.I | re.S),
            ]
            for pattern in patterns:
                match = pattern.search(text)
                if match:
                    raw = match.group(1).strip()
                    raw = re.split(r"[。，,；;]", raw)[0].strip()
                    if raw and len(raw) <= 40:
                        found[param_name] = raw
                        break
        return found

    def _refresh_logs(self, article, issues):
        log_model = self.env["diecut.kb.lint.log"].sudo()
        old_logs = log_model.search([("article_id", "=", article.id), ("state", "=", "open")])
        old_logs.write({"state": "resolved"})
        for severity, issue_type, summary in issues:
            log_model.create({
                "article_id": article.id,
                "source_item_id": article.compile_source_item_id.id,
                "severity": severity,
                "issue_type": issue_type,
                "summary": summary[:200],
                "details": summary,
                "suggestion": self._suggestion_for(issue_type),
            })

    @staticmethod
    def _suggestion_for(issue_type):
        mapping = {
            "content_short": "补充正文结构，至少覆盖概述、参数、场景和风险。",
            "sync_failed": "检查 Dify 配置和同步日志，修复后重新加入同步队列。",
            "missing_reference": "运行交叉引用增强，或手工补充关联品牌、型号、相关文章。",
            "stale_compile": "重新执行 AI 编译，确保编译层与源产品参数一致。",
            "duplicate_title": "检查是否为重复知识文章，必要时归并内容。",
            "weak_source_binding": "在正文中明确写入型号、品牌和关键参数，增强可追溯性。",
            "orphan_wiki": "运行 Wiki 图谱关联，或手工补充与品牌、型号、材料类别、应用场景相关的旧页面。",
            "missing_citation": "从资料收件箱重新编译，或补充来源资料、附件和页码引用。",
            "missing_inbound_link": "检查是否需要从品牌页、分类页或应用页添加反向链接。",
            "open_conflict_link": "打开 Wiki 图谱关联，查看 contradicts 关系并人工判定冲突来源。",
            "contradiction": "对比两篇文章引用的产品参数来源，确认哪一方的数据更准确。如需更新，建议重新编译或手工修正。",
            "llm_content_gap": "根据 LLM 建议补充正文缺失的数据或引用。",
            "llm_stale_claim": "检查 LLM 标记的过时声明，核实是否需要更新或删除。",
            "llm_orphan_suggestion": "根据 LLM 建议与其他页面建立关联。",
            "llm_missing_structure": "按 LLM 建议补充缺失的文章结构。",
            "llm_research_direction": "考虑检索 LLM 建议的新资料，进一步完善知识库。",
        }
        return mapping.get(issue_type, "")
