# -*- coding: utf-8 -*-
"""Export Odoo-maintained diecut knowledge as a portable graph JSON."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .kb_vault_mirror import KbVaultMirror


GRAPH_DIR = ".diecut_knowledge_graph"
GRAPH_FILE = "knowledge-graph.json"
GRAPH_VERSION = "diecut-knowledge-graph-v1"


class KbGraphExporter:
    def __init__(self, env):
        self.env = env
        self.warnings = []

    def export(self, output_path=None):
        graph = self.build_graph()
        graph = self._validate_graph(graph)
        path = Path(output_path) if output_path else self._default_output_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(graph, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return {
            "ok": True,
            "path": str(path),
            "nodes": len(graph.get("nodes") or []),
            "edges": len(graph.get("edges") or []),
            "warnings": len(graph.get("warnings") or []),
        }

    def build_graph(self):
        articles = self.env["diecut.kb.article"].sudo().search(
            [("active", "=", True), ("state", "in", ("review", "published"))],
            order="category_id, wiki_page_type, name, id",
        )
        nodes = []
        edges = []

        article_ids = set(articles.ids)
        topic_by_category = {}
        for category in articles.mapped("category_id"):
            topic_id = "topic:%s" % (category.code or category.id)
            topic_by_category[category.id] = topic_id
            nodes.append(self._topic_node(category, topic_id))

        for article in articles:
            article_node_id = self._article_id(article)
            nodes.append(self._article_node(article))
            if article.category_id:
                edges.append(
                    self._edge(
                        article_node_id,
                        topic_by_category[article.category_id.id],
                        "categorized_under",
                        0.65,
                        "文章所属知识分类。",
                    )
                )

        link_model = self.env["diecut.kb.wiki.link"].sudo()
        links = link_model.search(
            [
                ("active", "=", True),
                ("source_article_id", "in", list(article_ids)),
                ("target_article_id", "in", list(article_ids)),
            ],
            order="confidence desc, id",
        )
        for link in links:
            edges.append(
                self._edge(
                    self._article_id(link.source_article_id),
                    self._article_id(link.target_article_id),
                    link.link_type or "mentions",
                    link.confidence or 0.6,
                    link.reason or "",
                    {"link_id": link.id, "anchor_text": link.anchor_text or ""},
                )
            )

        source_docs = self._collect_source_documents(articles)
        for source in source_docs:
            nodes.append(self._source_node(source))

        catalog_items = self._collect_catalog_items(articles)
        for item in catalog_items:
            nodes.append(self._catalog_item_node(item))

        for article in articles:
            for citation in article.citation_ids:
                if citation.source_document_id:
                    edges.append(
                        self._edge(
                            self._article_id(article),
                            self._source_id(citation.source_document_id),
                            "cites",
                            citation.confidence or 0.6,
                            citation.claim_text or "",
                            {
                                "citation_id": citation.id,
                                "page_ref": citation.page_ref or "",
                                "state": citation.state or "",
                            },
                        )
                    )
            for item in (article.related_item_ids | article.compile_source_item_id).exists():
                edges.append(
                    self._edge(
                        self._article_id(article),
                        self._catalog_item_id(item),
                        "mentions",
                        0.7,
                        "文章关联材料目录型号。",
                    )
                )

        graph = {
            "version": GRAPH_VERSION,
            "kind": "knowledge",
            "project": {
                "name": "diecut_knowledge",
                "description": "Odoo diecut industry knowledge graph export.",
                "analyzedAt": datetime.now(timezone.utc).isoformat(),
            },
            "nodes": nodes,
            "edges": edges,
            "layers": self._build_layers(nodes),
            "tour": self._build_tour(nodes),
            "metadata": {
                "source": "odoo",
                "article_count": len(articles),
                "review_and_published_only": True,
                "entity_claim_layer": "lightweight_metadata",
            },
            "warnings": self.warnings,
        }
        return graph

    def _default_output_path(self):
        root = KbVaultMirror(self.env).ensure_structure()
        return root / GRAPH_DIR / GRAPH_FILE

    def _article_node(self, article):
        text = article.content_text or article.content_md or ""
        return {
            "id": self._article_id(article),
            "type": "article",
            "name": article.name or "",
            "summary": article.summary or self._clip(text, 180) or "Wiki article.",
            "tags": list(
                dict.fromkeys(
                    filter(
                        None,
                        [
                            article.state,
                            article.wiki_page_type,
                            article.category_id.code if article.category_id else "",
                        ],
                    )
                )
            ),
            "complexity": self._complexity(article),
            "metadata": {
                "odoo_model": article._name,
                "odoo_id": article.id,
                "state": article.state,
                "wiki_slug": article.wiki_slug or "",
                "wiki_page_type": article.wiki_page_type or "",
                "category": article.category_id.display_name if article.category_id else "",
                "compiled_at": article.compiled_at.isoformat() if article.compiled_at else "",
                "compile_confidence": article.compile_confidence or 0.0,
                "compile_risk_level": article.compile_risk_level or "",
                "citation_count": article.citation_count,
                "inbound": article.inbound_link_count,
                "outbound": article.outbound_link_count,
                "entity_candidates": self._extract_entity_candidates(article),
                "claim_candidates": self._extract_claim_candidates(article),
            },
        }

    def _topic_node(self, category, topic_id):
        return {
            "id": topic_id,
            "type": "topic",
            "name": category.name or category.code or "未分类",
            "summary": category.description or "知识分类：%s" % (category.name or category.code or ""),
            "tags": ["category"],
            "complexity": "simple",
            "metadata": {
                "odoo_model": category._name,
                "odoo_id": category.id,
                "code": category.code or "",
                "sequence": category.sequence,
            },
        }

    def _source_node(self, source):
        return {
            "id": self._source_id(source),
            "type": "source",
            "name": source.name or source.display_name,
            "summary": self._clip(
                getattr(source, "route_plan_summary", False)
                or getattr(source, "result_message", False)
                or getattr(source, "raw_text", False)
                or "",
                220,
            )
            or "Source document.",
            "tags": list(
                dict.fromkeys(
                    filter(
                        None,
                        [
                            getattr(source, "source_type", ""),
                            getattr(source, "knowledge_source_kind", ""),
                            getattr(source, "knowledge_parse_state", ""),
                        ],
                    )
                )
            ),
            "complexity": "moderate" if getattr(source, "knowledge_page_count", 0) > 5 else "simple",
            "metadata": {
                "odoo_model": source._name,
                "odoo_id": source.id,
                "filename": getattr(source, "source_filename", "") or getattr(source, "primary_attachment_name", "") or "",
                "vault_raw_path": getattr(source, "vault_raw_path", "") or "",
                "vault_file_hash": getattr(source, "vault_file_hash", "") or "",
                "parse_state": getattr(source, "knowledge_parse_state", "") or "",
            },
        }

    def _catalog_item_node(self, item):
        return {
            "id": self._catalog_item_id(item),
            "type": "catalog_item",
            "name": " ".join(filter(None, [self._record_value(item, "brand_id"), item.code or "", item.name or ""])).strip(),
            "summary": self._clip(item.product_description or item.product_features or item.main_applications or "", 220)
            or "材料目录型号。",
            "tags": list(
                dict.fromkeys(
                    filter(
                        None,
                        [
                            self._record_value(item, "brand_id"),
                            self._record_value(item, "categ_id"),
                            getattr(item, "catalog_status", ""),
                        ],
                    )
                )
            ),
            "complexity": "moderate" if len(getattr(item, "spec_line_ids", [])) > 8 else "simple",
            "metadata": {
                "odoo_model": item._name,
                "odoo_id": item.id,
                "code": item.code or "",
                "brand": self._record_value(item, "brand_id"),
                "category": self._record_value(item, "categ_id"),
                "thickness": getattr(item, "thickness", "") or "",
                "adhesive_type": self._record_value(item, "adhesive_type_id"),
                "base_material": self._record_value(item, "base_material_id"),
            },
        }

    def _collect_source_documents(self, articles):
        sources = articles.mapped("compile_source_document_id") | articles.mapped("citation_ids.source_document_id")
        return sources.exists()

    def _collect_catalog_items(self, articles):
        items = articles.mapped("related_item_ids") | articles.mapped("compile_source_item_id")
        return items.exists()

    def _extract_entity_candidates(self, article):
        values = []
        for brand in article.related_brand_ids:
            values.append({"type": "brand", "name": brand.name})
        for item in article.related_item_ids | article.compile_source_item_id:
            if item.code:
                values.append({"type": "model", "name": item.code})
            if item.categ_id:
                values.append({"type": "material_category", "name": item.categ_id.display_name})
            for field_name, entity_type in (
                ("adhesive_type_id", "adhesive"),
                ("base_material_id", "substrate"),
            ):
                value = self._record_value(item, field_name)
                if value:
                    values.append({"type": entity_type, "name": value})
        text = (article.content_text or "")[:3000]
        for term in ("应用", "工艺", "风险", "限制", "选型"):
            if term in text:
                values.append({"type": "concept", "name": term})
        return self._dedupe_dicts(values)

    def _extract_claim_candidates(self, article):
        claims = []
        for citation in article.citation_ids[:12]:
            if citation.claim_text:
                claims.append(
                    {
                        "type": "cited_fact",
                        "text": citation.claim_text[:240],
                        "citation_id": citation.id,
                        "state": citation.state or "review",
                    }
                )
        text = article.content_text or ""
        for pattern, claim_type in (
            (r"[^。\n]*(?:建议|适合|推荐)[^。\n]{4,80}", "selection_guidance"),
            (r"[^。\n]*(?:风险|限制|注意)[^。\n]{4,80}", "risk_limit"),
            (r"[^。\n]*(?:厚度|基材|胶系|耐温)[^。\n]{4,80}", "parameter_fact"),
        ):
            for match in re.finditer(pattern, text[:5000]):
                claims.append({"type": claim_type, "text": match.group(0)[:240], "state": "review"})
                if len(claims) >= 16:
                    return self._dedupe_dicts(claims)
        return self._dedupe_dicts(claims)

    def _validate_graph(self, graph):
        node_ids = {node["id"] for node in graph.get("nodes") or []}
        valid_edges = []
        linked_article_ids = set()
        for edge in graph.get("edges") or []:
            if edge["source"] not in node_ids or edge["target"] not in node_ids:
                self.warnings.append(
                    {
                        "type": "dangling_edge",
                        "message": "Graph edge references a missing node and was dropped.",
                        "edge": edge,
                    }
                )
                continue
            valid_edges.append(edge)
            if edge["source"].startswith("article:"):
                linked_article_ids.add(edge["source"])
            if edge["target"].startswith("article:"):
                linked_article_ids.add(edge["target"])
        graph["edges"] = valid_edges
        for node in graph.get("nodes") or []:
            if node["type"] == "article" and node["id"] not in linked_article_ids:
                self.warnings.append(
                    {
                        "type": "orphan_article",
                        "message": "Article has no graph edge in the exported graph.",
                        "node_id": node["id"],
                    }
                )
        graph["warnings"] = self.warnings
        return graph

    def _build_layers(self, nodes):
        grouped = {}
        for node in nodes:
            grouped.setdefault(node["type"], []).append(node["id"])
        return [
            {
                "id": "layer:%s" % node_type,
                "name": node_type.replace("_", " ").title(),
                "description": "All %s nodes." % node_type,
                "nodeIds": sorted(node_ids),
            }
            for node_type, node_ids in sorted(grouped.items())
        ]

    def _build_tour(self, nodes):
        topic_nodes = [node for node in nodes if node["type"] == "topic"]
        return [
            {
                "order": index,
                "title": node["name"],
                "description": node["summary"],
                "nodeIds": [node["id"]],
            }
            for index, node in enumerate(topic_nodes, start=1)
        ]

    @staticmethod
    def _edge(source, target, edge_type, weight, description="", metadata=None):
        return {
            "source": source,
            "target": target,
            "type": edge_type,
            "direction": "forward",
            "weight": max(0.0, min(1.0, float(weight or 0.0))),
            "description": description or "",
            "metadata": metadata or {},
        }

    @staticmethod
    def _article_id(article):
        return "article:%s" % article.id

    @staticmethod
    def _source_id(source):
        return "source:%s" % source.id

    @staticmethod
    def _catalog_item_id(item):
        return "catalog_item:%s" % item.id

    @staticmethod
    def _complexity(article):
        degree = article.graph_degree or 0
        length = article.content_length or 0
        if degree > 12 or length > 3000:
            return "complex"
        if degree > 4 or length > 900:
            return "moderate"
        return "simple"

    @staticmethod
    def _clip(value, limit):
        text = re.sub(r"<[^>]+>", " ", str(value or ""))
        text = re.sub(r"\s+", " ", text).strip()
        return text if len(text) <= limit else text[: limit - 3] + "..."

    @staticmethod
    def _dedupe_dicts(rows):
        result = []
        seen = set()
        for row in rows:
            key = tuple(sorted(row.items()))
            if key in seen:
                continue
            seen.add(key)
            result.append(row)
        return result

    @staticmethod
    def _record_value(record, field_name):
        if field_name not in record._fields:
            return ""
        value = getattr(record, field_name)
        if not value:
            return ""
        if hasattr(value, "_name"):
            if len(value) > 1:
                return ", ".join(value.mapped("display_name"))
            return value.display_name or value.name or ""
        return str(value)
