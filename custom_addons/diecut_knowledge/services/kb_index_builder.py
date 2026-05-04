# -*- coding: utf-8 -*-

from html import escape

from odoo import fields


class KbIndexBuilder:
    """Build the persistent Wiki index article used by humans and LLM agents."""

    INDEX_TITLE = "知识库总目录"

    def __init__(self, env):
        self.env = env

    def rebuild(self):
        Article = self.env["diecut.kb.article"].sudo()
        category = self._index_category()
        if not category:
            return False

        article = Article.search([("compile_source", "=", "wiki_index"), ("active", "=", True)], limit=1)
        html = self._build_index_html()
        md = self._build_index_md()
        vals = {
            "name": self.INDEX_TITLE,
            "category_id": category.id,
            "summary": "按知识分类汇总当前可检索 Wiki 文章，供人工浏览和 LLM 编译检索使用。",
            "content_html": html,
            "content_md": md,
            "state": "published",
            "publish_date": fields.Date.context_today(self.env.user),
            "sync_status": "pending",
            "compile_source": "wiki_index",
            "wiki_page_type": "concept",
            "compiled_at": fields.Datetime.now(),
            "compile_confidence": 1.0,
            "compile_risk_level": "low",
            "keywords": "wiki,index,知识库总目录,目录",
        }
        if article:
            article.with_context(skip_auto_enrich=True).write(vals)
        else:
            article = Article.with_context(skip_auto_enrich=True).create(vals)
        return article

    def _index_category(self):
        return self.env["diecut.kb.category"].sudo().search([], order="sequence, id", limit=1)

    def _articles_by_category(self):
        Article = self.env["diecut.kb.article"].sudo()
        categories = self.env["diecut.kb.category"].sudo().search([], order="sequence, id")
        data = []
        for category in categories:
            articles = Article.search(
                [
                    ("active", "=", True),
                    ("category_id", "=", category.id),
                    ("state", "in", ("review", "published")),
                    ("compile_source", "!=", "wiki_index"),
                ],
                order="wiki_page_type, name, id",
            )
            if articles:
                data.append((category, articles))
        return data

    def _article_label(self, article):
        source = dict(article._fields["compile_source"].selection).get(article.compile_source, article.compile_source or "")
        page_type = dict(article._fields["wiki_page_type"].selection).get(article.wiki_page_type, article.wiki_page_type or "")
        summary = (article.summary or article.content_text or "").strip().replace("\n", " ")[:80]
        metrics = "入链 %s / 出链 %s" % (article.inbound_link_count or 0, article.outbound_link_count or 0)
        return source, page_type, summary, metrics

    def _build_index_html(self):
        parts = [
            "<h2>知识库总目录</h2>",
            "<p>本页由系统定时生成，汇总当前评审中和已发布的 Wiki 文章。LLM 编译和问答可先读取此目录，再进入相关页面。</p>",
        ]
        for category, articles in self._articles_by_category():
            parts.append("<h3>%s</h3><ul>" % escape(category.name or "未分类"))
            for article in articles:
                source, page_type, summary, metrics = self._article_label(article)
                parts.append(
                    "<li><strong>%s</strong> <span>[%s / %s]</span> - %s <em>%s</em></li>"
                    % (
                        escape(article.name or ""),
                        escape(page_type or "-"),
                        escape(source or "-"),
                        escape(summary or "暂无摘要"),
                        escape(metrics),
                    )
                )
            parts.append("</ul>")
        return "\n".join(parts)

    def _build_index_md(self):
        parts = [
            "# 知识库总目录",
            "",
            "本页由系统定时生成，汇总当前评审中和已发布的 Wiki 文章。",
        ]
        for category, articles in self._articles_by_category():
            parts.extend(["", "## %s" % (category.name or "未分类")])
            for article in articles:
                source, page_type, summary, metrics = self._article_label(article)
                parts.append(
                    "- [[%s]] [%s / %s] - %s (%s)"
                    % (article.name or "", page_type or "-", source or "-", summary or "暂无摘要", metrics)
                )
        return "\n".join(parts)
