# -*- coding: utf-8 -*-

import hashlib
import json
import logging
import re
from datetime import datetime

from odoo import fields

from .dify_client import DifyClient

_logger = logging.getLogger(__name__)


SYSTEM_PROMPT_SINGLE = """
你是模切行业材料知识编译助手。请根据给定的结构化产品参数、相似产品上下文和已有知识摘要，
写出一篇适合进入企业知识库的中文 HTML 文章。

要求：
1. 只依据输入信息写作，不要编造不存在的参数。
2. 结构至少包含：产品概述、关键参数、适用场景、选型建议、风险与限制。
3. 如果缺少关键参数，要明确提醒“请结合原始 TDS 或测试报告复核”。
4. 输出纯 HTML，直接从 <h2> 开始，不要输出 Markdown 代码块。
5. 回答面向销售、工程和客服协作，语言专业但易读。
"""


SYSTEM_PROMPT_COMPARISON = """
你是模切行业材料知识编译助手。请对多个产品做选型对比，输出中文 HTML 文章。

要求：
1. 结构至少包含：对比概览、关键参数对比表、差异分析、适用场景建议、风险提醒。
2. 关键参数请优先用 HTML table 表达。
3. 只依据输入内容，不要补造缺失参数。
4. 输出纯 HTML，直接从 <h2> 开始，不要输出 Markdown 代码块。
"""


SYSTEM_PROMPT_BRAND_OVERVIEW = """
你是模切行业品牌综述编译助手。请根据某个品牌下所有已入库产品的结构化参数，写出一篇适合进入企业知识库的中文 HTML 品牌综述文章。

要求：
1. 只依据提供的产品数据写作，不要编造不存在的型号或参数。
2. 结构至少包含：品牌简介（品牌名称、主营方向）、产品概览（型号列表+一句话简介）、核心参数对比表（用 HTML table）、选型建议、注意事项。
3. 输出纯 HTML，直接从 <h2> 开始，不要输出 Markdown 代码块。
4. 面向销售和工程人员，专业但易读。
"""

SYSTEM_PROMPT_SOURCE_DOCUMENT = """
你是企业知识管理的 LLM 编译器，目标是把原始 PDF/TDS/选型指南编译成可维护的 Wiki 知识网络。
请基于输入资料生成中文 HTML，不要输出 Markdown 代码块，不要输出 <think>。
要求：
1. 只能依据输入资料、结构化产品参数和已有知识摘要，不要编造缺失数据。
2. 输出必须包含：资料综述、关键知识点、适用场景、选型建议、风险与限制、FAQ、交叉引用建议、来源说明。
3. FAQ 至少 3 条；交叉引用建议列出相关品牌、型号、材料类别、应用场景或相关文章标题。
4. 对缺少页码、资料不足或冲突的内容，要明确写“需要人工复核”。
5. 面向销售、工程、客服和知识库维护者，语言专业、简洁、可检索。
"""


class KbCompiler:
    PARAM_CHAT_URL = "diecut_knowledge.dify_chat_app_url"
    PARAM_CHAT_KEY = "diecut_knowledge.dify_chat_api_key"
    PARAM_AUTO_PUBLISH = "diecut_knowledge.compile_auto_publish"
    DEFAULT_CATEGORY_CODE = "material_selection"

    def __init__(self, env):
        self.env = env
        self._client = None
        self._client_built = False

    def compile_from_item(self, item, force=False):
        item.ensure_one()
        client = self._build_client()
        if not client:
            return self._fail_item(item, "未配置 Dify Chat API，无法执行 AI 编译", action="noop")

        context_hash = self._build_source_hash(item)
        existing = item.compiled_article_id or self._find_existing_article(item)

        if existing and not force and item.compile_status == "compiled" and item.compile_hash and item.compile_hash == context_hash:
            return {"ok": True, "action": "noop", "article_id": existing.id, "error": None}

        # 锁住产品行，防止并发编译生成重复文章
        self.env.cr.execute(
            "SELECT id FROM diecut_catalog_item WHERE id = %s FOR UPDATE",
            [item.id],
        )
        # 获取锁后重新查 existing（可能在等锁期间另一事务已创建）
        existing = item.compiled_article_id or self._find_existing_article(item)
        if existing and not item.compiled_article_id:
            item.write({"compiled_article_id": existing.id})

        if existing and not force and item.compile_hash and item.compile_hash == context_hash:
            return {"ok": True, "action": "noop", "article_id": existing.id, "error": None}

        context_text = self._build_compile_context(item)
        if len(context_text.strip()) < 40:
            return self._fail_item(item, "产品可编译内容过少，已跳过", action="skip", status="skipped")

        ok, payload, error, duration = client.chat_messages(
            query=f"请根据以下上下文编译知识文章：\n\n{context_text}",
            user=f"kb-compiler-{self.env.user.id}",
            inputs={"system": SYSTEM_PROMPT_SINGLE},
        )
        if not ok:
            return self._fail_item(item, f"AI 编译失败：{error}", duration_ms=duration)

        answer = self._clean_answer((payload or {}).get("answer", ""))
        if len(answer) < 80:
            return self._fail_item(item, "AI 返回内容过短，未生成文章", duration_ms=duration)

        summary = self._html_to_summary(answer)
        article_vals = self._build_article_vals(item, answer, summary, context_hash)

        if existing:
            existing.write(article_vals)
            article = existing
            action = "update"
        else:
            article = self.env["diecut.kb.article"].create(article_vals)
            action = "create"

        item.write({
            "compiled_article_id": article.id,
            "compile_status": "compiled",
            "last_compiled_at": fields.Datetime.now(),
            "compile_hash": context_hash,
            "compile_error": False,
        })

        from .kb_enricher import KbEnricher
        from .kb_linter import KbLinter

        KbEnricher(self.env).enrich_article(article)
        KbLinter(self.env).lint_article(article)

        # 增量编译：异步更新品牌综述（失败不影响主流程）
        if item.brand_id:
            try:
                self.compile_brand_overview(item.brand_id.id)
            except Exception as exc:
                _logger.warning("品牌综述更新失败 (brand %s): %s", item.brand_id.name, exc)

        self._log_compile(item, "success", f"AI 编译{ '更新' if action == 'update' else '创建' }文章 [{article.name}]", duration, article_id=article.id)
        return {"ok": True, "action": action, "article_id": article.id, "error": None}

    def compile_pending(self, limit=10):
        items = self.env["diecut.catalog.item"].search(
            [
                ("active", "=", True),
                ("catalog_status", "=", "published"),
                ("compile_status", "in", ("pending", "stale", "failed")),
            ],
            limit=limit,
            order="write_date asc, id asc",
        )
        ok_count = fail_count = skip_count = 0
        for item in items:
            result = self.compile_from_item(item)
            if result.get("action") == "skip":
                skip_count += 1
            elif result.get("ok"):
                ok_count += 1
            else:
                fail_count += 1
        return {"total": len(items), "ok": ok_count, "failed": fail_count, "skipped": skip_count}

    def compile_from_source_document(self, source, force=False):
        source.ensure_one()
        client = self._build_client()
        if not client:
            return {"ok": False, "action": "noop", "article_id": False, "error": "未配置 Dify Chat API，无法执行 LLM 编译"}

        source_text = self._get_source_document_text(source)
        if len(source_text.strip()) < 80:
            return {"ok": False, "action": "skip", "article_id": False, "error": "原始资料解析文本过短，请先解析 PDF 或补充正文"}

        context_hash = self._build_source_document_hash(source, source_text)
        existing = self._find_existing_source_article(source)
        if existing and not force and existing.compiled_hash == context_hash:
            return {"ok": True, "action": "noop", "article_id": existing.id, "error": None}

        context_text, linked_items = self._build_source_document_context(source, source_text)
        ok, payload, error, duration = client.chat_messages(
            query=f"请把以下原始资料编译成 Wiki 知识文章：\n\n{context_text}",
            user=f"kb-source-compiler-{self.env.user.id}",
            inputs={"system": SYSTEM_PROMPT_SOURCE_DOCUMENT},
        )
        if not ok:
            return {"ok": False, "action": "compile", "article_id": False, "error": f"LLM 编译失败：{error}"}

        answer = self._clean_answer((payload or {}).get("answer", ""))
        confidence, risk_level, risk_notes = self._score_source_compile(source, source_text, answer, linked_items)
        if len(answer) < 300:
            confidence = min(confidence, 0.45)
            risk_level = "high"
            risk_notes.append("LLM 输出内容过短")

        summary = self._html_to_summary(answer)
        article_vals = self._build_source_article_vals(
            source=source,
            linked_items=linked_items,
            content_html=answer,
            summary=summary,
            context_hash=context_hash,
            confidence=confidence,
            risk_level=risk_level,
            risk_notes=risk_notes,
        )

        if existing:
            existing.write(article_vals)
            article = existing
            action = "update"
        else:
            article = self.env["diecut.kb.article"].create(article_vals)
            action = "create"

        from .kb_enricher import KbEnricher
        from .kb_linter import KbLinter

        KbEnricher(self.env).enrich_article(article)
        KbLinter(self.env).lint_article(article)
        self._log_source_compile(source, "success", f"LLM 编译{ '更新' if action == 'update' else '创建' } Wiki 文章 [{article.name}]", duration, article.id)
        return {"ok": True, "action": action, "article_id": article.id, "error": None, "risk_level": risk_level, "confidence": confidence}

    def compile_comparison(self, items):
        if len(items) < 2:
            return {"ok": False, "article_id": False, "error": "至少需要 2 个产品才能生成对比分析"}
        client = self._build_client()
        if not client:
            return {"ok": False, "article_id": False, "error": "未配置 Dify Chat API"}

        blocks = []
        for item in items:
            blocks.append(f"--- 产品 {item.code or item.name} ---\n{self._build_item_snapshot(item)}")
        ok, payload, error, _duration = client.chat_messages(
            query="请对以下多个产品生成对比选型文章：\n\n%s" % ("\n\n".join(blocks)),
            user=f"kb-compiler-{self.env.user.id}",
            inputs={"system": SYSTEM_PROMPT_COMPARISON},
        )
        if not ok:
            return {"ok": False, "article_id": False, "error": error or "AI 对比编译失败"}

        answer = self._clean_answer((payload or {}).get("answer", ""))
        if len(answer) < 80:
            return {"ok": False, "article_id": False, "error": "AI 对比文章内容过短"}

        category = self._get_compile_category()
        title = "对比分析：%s" % " vs ".join(items.mapped("code") or items.mapped("name"))
        article = self.env["diecut.kb.article"].create({
            "name": title[:200],
            "category_id": category.id,
            "content_html": answer,
            "summary": self._html_to_summary(answer),
            "state": "review",
            "sync_status": "pending",
            "compile_source": "comparison",
            "compiled_at": fields.Datetime.now(),
            "related_item_ids": [(6, 0, items.ids)],
            "related_brand_ids": [(6, 0, items.mapped("brand_id").ids)],
            "related_categ_ids": [(6, 0, items.mapped("categ_id").ids)],
            "keywords": ", ".join(filter(None, items.mapped("code"))),
        })
        from .kb_enricher import KbEnricher
        from .kb_linter import KbLinter

        KbEnricher(self.env).enrich_article(article)
        KbLinter(self.env).lint_article(article)
        return {"ok": True, "article_id": article.id, "error": None}

    def compile_brand_overview(self, brand_id):
        """生成或更新品牌综述文章。"""
        if not brand_id:
            return {"ok": False, "action": "noop", "article_id": False, "error": "brand_id 为空"}
        items = self.env["diecut.catalog.item"].search([
            ("brand_id", "=", brand_id),
            ("active", "=", True),
        ])
        if not items:
            return {"ok": False, "action": "skip", "article_id": False, "error": "该品牌没有活跃产品"}

        brand = self.env["diecut.brand"].browse(brand_id)
        category = self._get_compile_category()

        existing = self.env["diecut.kb.article"].search([
            ("compile_source", "=", "brand_overview"),
            ("compile_source_brand_id", "=", brand_id),
            ("active", "=", True),
        ], limit=1)

        context_parts = [f"# 品牌名称：{brand.name}"]
        context_parts.append(f"该品牌共有 {len(items)} 个活跃产品：")
        for item in items:
            context_parts.append(self._build_item_snapshot(item))

        existing_articles = self.env["diecut.kb.article"].search([
            ("id", "!=", existing.id if existing else 0),
            ("state", "in", ("review", "published")),
            ("related_brand_ids", "in", brand_id),
        ], limit=5, order="write_date desc")
        if existing_articles:
            context_parts.append("\n### 已有相关文章")
            for rel in existing_articles:
                context_parts.append("- %s: %s" % (rel.name, (rel.summary or rel.content_text[:200]).strip()))

        context_text = "\n\n".join(context_parts)

        client = self._build_client()
        if not client:
            return {"ok": False, "action": "noop", "article_id": False, "error": "Dify 未配置"}

        ok, payload, error, duration = client.chat_messages(
            query=f"请根据以下品牌数据生成品牌综述文章：\n\n{context_text}",
            user=f"kb-overview-{self.env.user.id}",
            inputs={"system": SYSTEM_PROMPT_BRAND_OVERVIEW},
        )
        if not ok:
            return {"ok": False, "action": "compile", "article_id": False, "error": error}

        answer = self._clean_answer((payload or {}).get("answer", ""))
        if len(answer) < 150:
            return {"ok": False, "action": "compile", "article_id": False, "error": "AI 返回内容过短"}

        auto_publish = self._auto_publish_enabled()
        title = f"{brand.name} 选型综述"
        vals = {
            "name": title,
            "category_id": category.id,
            "content_html": answer,
            "summary": self._html_to_summary(answer),
            "state": "published" if auto_publish else "review",
            "publish_date": fields.Date.context_today(self.env.user) if auto_publish else False,
            "sync_status": "pending" if auto_publish else "skipped",
            "compile_source": "brand_overview",
            "compile_source_brand_id": brand_id,
            "compiled_at": fields.Datetime.now(),
            "keywords": brand.name,
            "related_brand_ids": [(6, 0, [brand_id])],
            "related_item_ids": [(6, 0, items.ids)],
        }

        if existing:
            existing.write(vals)
            article = existing
            action = "update"
        else:
            article = self.env["diecut.kb.article"].create(vals)
            action = "create"

        from .kb_enricher import KbEnricher
        from .kb_linter import KbLinter

        KbEnricher(self.env).enrich_article(article)
        KbLinter(self.env).lint_article(article)
        return {"ok": True, "action": action, "article_id": article.id, "error": None}

    def _build_compile_context(self, item):
        parts = [
            "### 当前产品",
            self._build_item_snapshot(item),
        ]

        similar_items = self.env["diecut.catalog.item"].search(
            [
                ("id", "!=", item.id),
                ("active", "=", True),
                "|",
                ("brand_id", "=", item.brand_id.id),
                ("categ_id", "=", item.categ_id.id),
            ],
            limit=3,
        )
        if similar_items:
            parts.append("\n### 相似产品")
            for similar in similar_items:
                parts.append(self._build_item_snapshot(similar))

        related_articles = self.env["diecut.kb.article"].search(
            [
                ("id", "!=", item.compiled_article_id.id if item.compiled_article_id else 0),
                ("state", "in", ("review", "published")),
                "|",
                ("related_brand_ids", "in", item.brand_id.ids),
                ("related_categ_ids", "in", item.categ_id.ids),
            ],
            limit=3,
            order="write_date desc",
        )
        if related_articles:
            parts.append("\n### 已有知识摘要")
            for article in related_articles:
                parts.append("- %s: %s" % (article.name, (article.summary or article.content_text[:200]).strip()))

        return "\n\n".join(filter(None, parts))

    def _get_source_document_text(self, source):
        return (
            source.knowledge_parsed_markdown
            or source.knowledge_parsed_text
            or source.raw_text
            or source.result_message
            or ""
        )

    def _build_source_document_context(self, source, source_text):
        linked_items = source.compilable_item_ids or source.compiled_item_ids
        parts = [
            "### 原始资料",
            json.dumps(
                {
                    "title": source.name or "",
                    "source_type": source.source_type or "",
                    "source_url": source.source_url or "",
                    "source_file": source.primary_attachment_name or source.source_filename or "",
                    "brand": source.brand_id.name if source.brand_id else "",
                    "parse_state": source.knowledge_parse_state or "",
                    "parse_method": source.knowledge_parse_method or source.parse_version or "",
                    "page_count": source.knowledge_page_count or 0,
                },
                ensure_ascii=False,
                indent=2,
            ),
            "### 原文/解析内容",
            source_text[:24000],
        ]
        if linked_items:
            parts.append("\n### 已入库结构化产品")
            for item in linked_items[:5]:
                parts.append(self._build_item_snapshot(item))

        related_articles = self.env["diecut.kb.article"].search(
            [
                ("state", "in", ("review", "published")),
                ("compile_source_document_id", "!=", source.id),
                "|",
                ("related_brand_ids", "in", source.brand_id.ids),
                ("related_item_ids", "in", linked_items.ids),
            ],
            limit=5,
            order="write_date desc",
        )
        if related_articles:
            parts.append("\n### 已有 Wiki 摘要")
            for article in related_articles:
                parts.append("- %s: %s" % (article.name, (article.summary or article.content_text[:240]).strip()))
        return "\n\n".join(filter(None, parts)), linked_items

    def _score_source_compile(self, source, source_text, answer, linked_items):
        confidence = 0.35
        notes = []
        if source.knowledge_parse_state == "parsed":
            confidence += 0.25
        else:
            notes.append("原始资料未完成知识解析")
        if source.knowledge_page_count:
            confidence += 0.15
        else:
            notes.append("缺少来源页码")
        if linked_items:
            confidence += 0.15
        else:
            notes.append("未关联结构化产品")
        if len(source_text) >= 1200:
            confidence += 0.10
        else:
            notes.append("解析文本较短")
        if "FAQ" in answer or "常见问题" in answer:
            confidence += 0.05
        else:
            notes.append("未检测到 FAQ 区块")
        confidence = max(0.0, min(confidence, 1.0))
        if confidence >= 0.75 and not notes[:2]:
            risk = "low"
        elif confidence >= 0.55:
            risk = "medium"
        else:
            risk = "high"
        return confidence, risk, notes

    def _build_source_article_vals(self, source, linked_items, content_html, summary, context_hash, confidence, risk_level, risk_notes):
        category = self._get_compile_category()
        auto_publish = self._auto_publish_enabled()
        should_publish = auto_publish and confidence >= 0.75 and risk_level == "low"
        title = source.name or source.primary_attachment_name or source.source_filename or "未命名资料"
        source_refs = self._source_page_refs(source)
        if risk_notes:
            content_html = content_html + self._risk_notes_html(risk_notes)
        vals = {
            "name": f"[Wiki] {title}"[:200],
            "category_id": category.id,
            "content_html": content_html,
            "summary": summary,
            "state": "published" if should_publish else "review",
            "publish_date": fields.Date.context_today(self.env.user) if should_publish else False,
            "sync_status": "pending" if should_publish else "skipped",
            "compile_source": "source_document",
            "compile_source_document_id": source.id,
            "compile_source_item_id": linked_items[:1].id if linked_items else False,
            "compiled_at": fields.Datetime.now(),
            "compiled_hash": context_hash,
            "compile_confidence": confidence,
            "compile_risk_level": risk_level,
            "source_page_refs": source_refs,
            "source_file_name": source.primary_attachment_name or source.source_filename or "",
            "source_url": source.source_url or False,
            "author_name": source.brand_id.name if source.brand_id else "",
            "keywords": ", ".join(filter(None, [source.name, source.brand_id.name if source.brand_id else "", *(linked_items.mapped("code") or [])])),
            "related_brand_ids": [(6, 0, source.brand_id.ids)] if source.brand_id else False,
            "related_categ_ids": [(6, 0, linked_items.mapped("categ_id").ids)] if linked_items else False,
            "related_item_ids": [(6, 0, linked_items.ids)] if linked_items else False,
        }
        return {key: value for key, value in vals.items() if value is not False}

    def _build_item_snapshot(self, item):
        data = {
            "code": item.code or "",
            "name": item.name or "",
            "brand": item.brand_id.name if item.brand_id else "",
            "series": item.series_id.name if item.series_id else "",
            "category": item.categ_id.complete_name if item.categ_id else "",
            "thickness": item.thickness or "",
            "adhesive_thickness": item.adhesive_thickness or "",
            "color": item.color_id.name if item.color_id else "",
            "adhesive_type": item.adhesive_type_id.name if item.adhesive_type_id else "",
            "base_material": item.base_material_id.name if item.base_material_id else "",
            "fire_rating": item.fire_rating or "",
            "rohs": bool(item.is_rohs),
            "reach": bool(item.is_reach),
            "halogen_free": bool(item.is_halogen_free),
            "description": item.product_description or "",
            "features": item.product_features or "",
            "main_applications": item.main_applications or "",
            "special_applications": item.special_applications or "",
            "specs": [],
        }
        for line in item.spec_line_ids.sorted(key=lambda rec: (rec.sequence, rec.id)):
            param = line.param_id.name or line.param_name or ""
            value = line.value_display or ""
            unit = line.unit or ""
            if param and value:
                data["specs"].append("%s: %s %s" % (param, value, unit))
        return json.dumps(data, ensure_ascii=False, indent=2)

    def _build_article_vals(self, item, content_html, summary, context_hash):
        category = self._get_compile_category()
        auto_publish = self._auto_publish_enabled()
        title = "[%s] %s %s" % (
            item.brand_id.name if item.brand_id else "",
            item.code or "",
            item.name or "",
        )
        title = re.sub(r"\s+", " ", title).strip() or item.name or item.code or "未命名知识文章"
        state = "published" if auto_publish else "review"
        vals = {
            "name": title[:200],
            "category_id": category.id,
            "content_html": content_html,
            "summary": summary,
            "state": state,
            "publish_date": fields.Date.context_today(self.env.user) if auto_publish else False,
            "sync_status": "pending",
            "compile_source": "catalog_item",
            "compile_source_item_id": item.id,
            "compiled_at": fields.Datetime.now(),
            "compiled_hash": context_hash,
            "compile_confidence": 0.8,
            "compile_risk_level": "low",
            "keywords": ", ".join(filter(None, [item.code, item.brand_id.name if item.brand_id else "", item.categ_id.name if item.categ_id else ""])),
            "related_brand_ids": [(6, 0, item.brand_id.ids)] if item.brand_id else False,
            "related_categ_ids": [(6, 0, item.categ_id.ids)] if item.categ_id else False,
            "related_item_ids": [(6, 0, [item.id])],
        }
        return {key: value for key, value in vals.items() if value is not False}

    def _auto_publish_enabled(self):
        return str(
            self.env["ir.config_parameter"].sudo().get_param(self.PARAM_AUTO_PUBLISH, default="True")
        ).lower() in ("1", "true", "yes", "on")

    def _find_existing_article(self, item):
        return self.env["diecut.kb.article"].search(
            [
                ("compile_source", "=", "catalog_item"),
                ("compile_source_item_id", "=", item.id),
            ],
            limit=1,
        )

    def _find_existing_source_article(self, source):
        return self.env["diecut.kb.article"].search(
            [
                ("compile_source", "=", "source_document"),
                ("compile_source_document_id", "=", source.id),
            ],
            limit=1,
        )

    def _get_compile_category(self):
        category = self.env["diecut.kb.category"].search([("code", "=", self.DEFAULT_CATEGORY_CODE)], limit=1)
        if not category:
            category = self.env["diecut.kb.category"].search([], limit=1, order="sequence, id")
        if not category:
            raise ValueError("请先创建至少一个知识分类")
        return category

    def _build_client(self):
        if self._client_built:
            return self._client
        self._client_built = True
        icp = self.env["ir.config_parameter"].sudo()
        chat_url = (icp.get_param(self.PARAM_CHAT_URL) or "").strip()
        fallback_url = (icp.get_param("diecut_knowledge.dify_base_url") or "").strip()
        base_url = chat_url or fallback_url
        if chat_url and fallback_url:
            normalized = chat_url.lower()
            if normalized.startswith("http://localhost") or normalized.startswith("https://localhost") or normalized.startswith("http://127.0.0.1") or normalized.startswith("https://127.0.0.1"):
                base_url = fallback_url
        api_key = icp.get_param(self.PARAM_CHAT_KEY)
        if not base_url or not api_key:
            return None
        self._client = DifyClient(base_url=base_url, api_key=api_key, timeout=120, retries=1)
        return self._client

    def _build_source_hash(self, item):
        payload = self._build_item_snapshot(item)
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()

    def _build_source_document_hash(self, source, source_text):
        payload = {
            "source_id": source.id,
            "name": source.name or "",
            "file": source.primary_attachment_name or source.source_filename or "",
            "parse_state": source.knowledge_parse_state or "",
            "parse_method": source.knowledge_parse_method or "",
            "page_count": source.knowledge_page_count or 0,
            "text": source_text,
            "items": source.compiled_item_ids.mapped("code"),
        }
        return hashlib.sha1(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()

    def _source_page_refs(self, source):
        if source.knowledge_page_count:
            return "1-%s" % source.knowledge_page_count
        if source.knowledge_parsed_markdown and "第" in source.knowledge_parsed_markdown and "页" in source.knowledge_parsed_markdown:
            return "parsed-pages"
        return ""

    def _risk_notes_html(self, notes):
        items = "".join("<li>%s</li>" % note for note in notes if note)
        if not items:
            return ""
        return "<h2>需要人工复核</h2><ul>%s</ul>" % items

    def _html_to_summary(self, html):
        text = re.sub(r"<[^>]+>", " ", html or "")
        text = re.sub(r"\s+", " ", text).strip()
        return text[:200]

    def _clean_answer(self, answer):
        text = answer or ""
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.I | re.S)
        text = re.sub(r"</?think>", "", text, flags=re.I)
        text = re.sub(r"^```html?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        return text.strip()

    def _fail_item(self, item, message, action="compile", status="failed", duration_ms=0):
        item.write({
            "compile_status": status,
            "compile_error": message,
        })
        self._log_compile(item, "failed", message, duration_ms)
        return {"ok": False, "action": action, "article_id": False, "error": message}

    def _log_compile(self, item, state, message, duration_ms=0, article_id=False):
        try:
            self.env["diecut.kb.sync.log"].sudo().create({
                "article_id": article_id or False,
                "direction": "push",
                "action": "create",
                "state": "success" if state == "success" else "failed",
                "summary": ("[AI编译] %s: %s" % (item.code or item.name, message))[:500],
                "dify_dataset_id": "",
                "dify_document_id": "",
                "duration_ms": duration_ms,
                "error_message": message if state != "success" else "",
            })
        except Exception as exc:
            _logger.warning("Failed to log compile result: %s", exc)

    def _log_source_compile(self, source, state, message, duration_ms=0, article_id=False):
        try:
            self.env["diecut.kb.sync.log"].sudo().create({
                "article_id": article_id or False,
                "direction": "push",
                "action": "create",
                "state": "success" if state == "success" else "failed",
                "summary": ("[资料编译] %s: %s" % (source.name, message))[:500],
                "dify_dataset_id": "",
                "dify_document_id": "",
                "duration_ms": duration_ms,
                "error_message": message if state != "success" else "",
            })
        except Exception as exc:
            _logger.warning("Failed to log source compile result: %s", exc)
