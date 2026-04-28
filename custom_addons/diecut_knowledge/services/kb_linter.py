# -*- coding: utf-8 -*-

from odoo import fields


class KbLinter:
    def __init__(self, env):
        self.env = env

    def lint_article(self, article):
        article.ensure_one()
        issues = []
        if article.content_length < 150:
            issues.append(("info", "content_short", "文章内容偏短，建议补充应用场景、参数或风险限制。"))
        if article.sync_status == "failed":
            issues.append(("warning", "sync_failed", "文章同步到 Dify 失败，建议先修复同步错误。"))
        if not (article.related_brand_ids or article.related_item_ids or article.related_article_ids):
            issues.append(("info", "missing_reference", "文章缺少关联品牌、型号或相关文章，建议补充交叉引用。"))
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
        }
        return mapping.get(issue_type, "")

