# -*- coding: utf-8 -*-

import html
import logging
import re

from odoo import fields

_logger = logging.getLogger(__name__)

AUTO_SECTION_MARKER_START = "<!-- AUTO-RELATED-START -->"
AUTO_SECTION_MARKER_END = "<!-- AUTO-RELATED-END -->"


class KbEnricher:
    def __init__(self, env):
        self.env = env

    def enrich_article(self, article):
        article.ensure_one()
        text = (article.content_text or "").strip()
        if not text:
            return {"ok": True, "related_articles": 0}

        related_brands = set(article.related_brand_ids.ids)
        related_categories = set(article.related_categ_ids.ids)
        related_items = set(article.related_item_ids.ids)

        source_item = article.compile_source_item_id
        if source_item:
            related_items.add(source_item.id)
            related_brands.update(source_item.brand_id.ids)
            related_categories.update(source_item.categ_id.ids)

        candidate_items = self._candidate_items(source_item, related_brands, related_categories)
        lowered = text.lower()
        for item in candidate_items:
            code = (item.code or "").strip()
            name = (item.name or "").strip()
            if code and code.lower() in lowered:
                related_items.add(item.id)
                related_brands.update(item.brand_id.ids)
                related_categories.update(item.categ_id.ids)
            elif name and name.lower() in lowered:
                related_items.add(item.id)
                related_brands.update(item.brand_id.ids)
                related_categories.update(item.categ_id.ids)

        brand_records = self._match_brands(text, related_brands)
        related_brands.update(brand_records.ids)

        related_articles = self._find_related_articles(article, list(related_items), list(related_brands), list(related_categories))
        auto_html = self._build_related_section(related_articles, related_items)

        values = {
            "xref_enriched_at": fields.Datetime.now(),
            "related_item_ids": [(6, 0, list(related_items))] if related_items else [(5, 0, 0)],
            "related_brand_ids": [(6, 0, list(related_brands))] if related_brands else [(5, 0, 0)],
            "related_categ_ids": [(6, 0, list(related_categories))] if related_categories else [(5, 0, 0)],
            "related_article_ids": [(6, 0, related_articles.ids)] if related_articles else [(5, 0, 0)],
            "content_html": self._merge_auto_section(article.content_html or "", auto_html),
        }
        article.with_context(skip_auto_enrich=True).write(values)
        return {"ok": True, "related_articles": len(related_articles)}

    def _candidate_items(self, source_item, brand_ids, category_ids):
        domain = [("active", "=", True)]
        if source_item:
            domain += ["|", ("brand_id", "=", source_item.brand_id.id), ("categ_id", "=", source_item.categ_id.id)]
        elif brand_ids or category_ids:
            domain += ["|", ("brand_id", "in", list(brand_ids) or [0]), ("categ_id", "in", list(category_ids) or [0])]
        return self.env["diecut.catalog.item"].search(domain, limit=30)

    def _match_brands(self, text, existing_brand_ids):
        lowered = text.lower()
        matched_ids = set(existing_brand_ids)
        # 用 search_read 只取 id + name，避免加载完整 ORM 记录
        all_brands = self.env["diecut.brand"].search_read([], ["id", "name"])
        for brand in all_brands:
            name = (brand["name"] or "").lower()
            if name and name in lowered:
                matched_ids.add(brand["id"])
        return self.env["diecut.brand"].browse(list(matched_ids))

    def _find_related_articles(self, article, item_ids, brand_ids, categ_ids):
        domain = [("id", "!=", article.id), ("state", "in", ("review", "published"))]
        ors = []
        if item_ids:
            ors.append(("related_item_ids", "in", item_ids))
        if brand_ids:
            ors.append(("related_brand_ids", "in", brand_ids))
        if categ_ids:
            ors.append(("related_categ_ids", "in", categ_ids))
        if not ors:
            return self.env["diecut.kb.article"]
        domain += self._or_domain(ors)
        return self.env["diecut.kb.article"].search(domain, limit=8, order="write_date desc")

    def _build_related_section(self, related_articles, related_item_ids):
        parts = [AUTO_SECTION_MARKER_START, "<h2>相关资料</h2>"]
        if related_item_ids:
            items = self.env["diecut.catalog.item"].browse(list(related_item_ids))
            labels = []
            for item in items[:8]:
                label = ("[%s] %s %s" % (item.brand_id.name or "", item.code or "", item.name or "")).strip()
                labels.append("<li>%s</li>" % html.escape(label))
            if labels:
                parts.append("<h3>关联型号</h3><ul>%s</ul>" % "".join(labels))
        if related_articles:
            article_links = []
            for rel in related_articles:
                article_links.append("<li>%s</li>" % html.escape(rel.name or "未命名文章"))
            parts.append("<h3>相关文章</h3><ul>%s</ul>" % "".join(article_links))
        parts.append(AUTO_SECTION_MARKER_END)
        return "".join(parts)

    def _merge_auto_section(self, content_html, auto_html):
        cleaned = re.sub(
            "%s.*?%s" % (re.escape(AUTO_SECTION_MARKER_START), re.escape(AUTO_SECTION_MARKER_END)),
            "",
            content_html or "",
            flags=re.S,
        ).strip()
        return ("%s\n%s" % (cleaned, auto_html)).strip()

    @staticmethod
    def _or_domain(clauses):
        if not clauses:
            return []
        if len(clauses) == 1:
            return [clauses[0]]
        domain = ["|", clauses[0], clauses[1]]
        for clause in clauses[2:]:
            domain = ["|", clause] + domain
        return domain
