# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request


class DiecutKnowledgeWikiGraphController(http.Controller):
    @http.route("/diecut_knowledge/wiki_graph/data", type="json", auth="user")
    def wiki_graph_data(self, limit=200, **kwargs):
        limit = min(int(limit or 200), 300)
        article_model = request.env["diecut.kb.article"].sudo()
        link_model = request.env["diecut.kb.wiki.link"].sudo()
        citation_model = request.env["diecut.kb.citation"].sudo()

        articles = article_model.search(
            [("active", "=", True), ("state", "in", ("review", "published"))],
            limit=limit,
            order="graph_degree desc, write_date desc, id desc",
        )
        article_ids = set(articles.ids)
        links = link_model.search(
            [
                ("active", "=", True),
                ("source_article_id", "in", list(article_ids)),
                ("target_article_id", "in", list(article_ids)),
            ],
            limit=limit * 4,
            order="confidence desc, id desc",
        )
        connected_ids = set(links.mapped("source_article_id").ids) | set(links.mapped("target_article_id").ids)
        visible_articles = articles.filtered(lambda article: article.id in connected_ids or article.graph_degree == 0)
        citations = citation_model.search(
            [
                ("article_id", "in", visible_articles.ids),
                ("source_document_id", "!=", False),
            ],
            limit=limit * 3,
            order="confidence desc, id desc",
        )
        source_documents = citations.mapped("source_document_id")

        article_nodes = [
            {
                "id": article.id,
                "label": article.name,
                "model": article._name,
                "resId": article.id,
                "type": article.wiki_page_type or "source_summary",
                "nodeType": "article",
                "state": article.state,
                "degree": article.graph_degree,
                "inbound": article.inbound_link_count,
                "outbound": article.outbound_link_count,
                "summary": article.summary or ((article.content_text or "")[:220]),
                "wiki_slug": article.wiki_slug or "",
                "compiled_at": article.compiled_at.isoformat() if article.compiled_at else "",
                "citation_count": article.citation_count,
                "risk_level": article.compile_risk_level or "",
                "confidence": article.compile_confidence or 0.0,
                "orphan_score": article.orphan_score,
                "brand_ids": article.related_brand_ids.ids,
                "brand_label": article.related_brand_ids[:1].name or "",
                "category_id": article.category_id.id,
                "category_label": article.category_id.name or "",
                "item_count": len(article.related_item_ids),
            }
            for article in visible_articles
        ]
        brand_records = visible_articles.mapped("related_brand_ids")
        category_records = visible_articles.mapped("category_id")
        source_nodes = [
            {
                "id": "source:%s" % source.id,
                "label": source.name or source.display_name,
                "model": source._name,
                "resId": source.id,
                "type": "source",
                "nodeType": "source",
                "state": getattr(source, "knowledge_parse_state", "") or "",
                "degree": 1,
                "inbound": 0,
                "outbound": 0,
                "summary": (
                    getattr(source, "route_plan_summary", False)
                    or getattr(source, "result_message", False)
                    or getattr(source, "raw_text", False)
                    or ""
                )[:220],
                "wiki_slug": "",
                "compiled_at": getattr(source, "knowledge_parsed_at", False).isoformat()
                if getattr(source, "knowledge_parsed_at", False)
                else "",
                "citation_count": 0,
                "risk_level": "",
                "confidence": 0.0,
            }
            for source in source_documents
        ]
        wiki_links = [
            {
                "id": link.id,
                "source": link.source_article_id.id,
                "target": link.target_article_id.id,
                "type": link.link_type,
                "confidence": link.confidence,
                "reason": link.reason or "",
            }
            for link in links
        ]
        citation_links = [
            {
                "id": "cite:%s" % citation.id,
                "source": citation.article_id.id,
                "target": "source:%s" % citation.source_document_id.id,
                "type": "cites",
                "confidence": citation.confidence or 0.6,
                "reason": citation.claim_text or "",
            }
            for citation in citations
        ]
        all_nodes = article_nodes + source_nodes
        all_links = wiki_links + citation_links

        return {
            "nodes": all_nodes,
            "links": all_links,
            "node_types": sorted(set(node["type"] for node in all_nodes if node.get("type"))),
            "link_types": sorted(set(link["type"] for link in all_links if link.get("type"))),
            "brands": sorted(
                ({"id": brand.id, "name": brand.name} for brand in brand_records),
                key=lambda b: b["name"] or "",
            ),
            "categories": sorted(
                ({"id": cat.id, "name": cat.name} for cat in category_records),
                key=lambda c: c["name"] or "",
            ),
        }
