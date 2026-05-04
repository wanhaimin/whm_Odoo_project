# -*- coding: utf-8 -*-

import hashlib
import json
import logging
import re
from datetime import datetime

from odoo import fields

from .dify_client import DifyClient
from . import kb_schema
from .prompt_loader import build_system_prompt

_logger = logging.getLogger(__name__)


_DEFAULT_PROMPT_SINGLE = """
你是模切行业材料知识编译助手。请根据给定的结构化产品参数、相似产品上下文和已有知识摘要，
写出一篇适合进入企业知识库的中文 HTML 文章。

要求：
1. 只依据输入信息写作，不要编造不存在的参数。
2. 结构至少包含：产品概述、关键参数、适用场景、选型建议、风险与限制。
3. 如果缺少关键参数，要明确提醒“请结合原始 TDS 或测试报告复核”。
4. 输出纯 HTML，直接从 <h2> 开始，不要输出 Markdown 代码块。
5. 回答面向销售、工程和客服协作，语言专业但易读。
"""


_DEFAULT_PROMPT_COMPARISON = """
你是模切行业材料知识编译助手。请对多个产品做选型对比，输出中文 HTML 文章。

要求：
1. 结构至少包含：对比概览、关键参数对比表、差异分析、适用场景建议、风险提醒。
2. 关键参数请优先用 HTML table 表达。
3. 只依据输入内容，不要补造缺失参数。
4. 输出纯 HTML，直接从 <h2> 开始，不要输出 Markdown 代码块。
"""


_DEFAULT_PROMPT_BRAND_OVERVIEW = """
你是模切行业品牌综述编译助手。请根据某个品牌下所有已入库产品的结构化参数，写出一篇适合进入企业知识库的中文 HTML 品牌综述文章。

要求：
1. 只依据提供的产品数据写作，不要编造不存在的型号或参数。
2. 结构至少包含：品牌简介（品牌名称、主营方向）、产品概览（型号列表+一句话简介）、核心参数对比表（用 HTML table）、选型建议、注意事项。
3. 输出纯 HTML，直接从 <h2> 开始，不要输出 Markdown 代码块。
4. 面向销售和工程人员，专业但易读。
"""

_DEFAULT_PROMPT_SOURCE_DOCUMENT = """
你是企业知识管理的 LLM Wiki 编译器。你的任务不是直接写普通文章，而是输出可由 Odoo 校验和应用的 Wiki Patch JSON。

硬规则：
1. 只能依据输入的 raw source、解析文本、结构化产品参数、旧 Wiki 候选页面和来源引用，不要编造事实。
2. Wiki 页面必须包含：概述、关键事实、应用场景、选型建议、风险与限制、FAQ、相关 Wiki、来源引用。
3. 每个关键事实必须在 citations 中给出来源；没有来源的事实必须标记为 state=review。
4. 新页面不能孤立存在。必须基于候选旧 Wiki 输出 links，或在 risk_notes 中说明暂无可靠关联。
5. 如果旧 Wiki 更适合作为目标页面，使用 operation=update_existing 或 merge_review，不要制造重复页面。
6. 如果发现冲突，不要覆盖旧结论；输出 conflicts，并创建 contradicts 链接，review_required=true。
7. 只输出 JSON，不要 Markdown 代码块，不要 HTML，不要 <think>，不要解释。
"""

_DEFAULT_PROMPT_INCREMENTAL_WIKI = """
你是企业 LLM Wiki 的全库感知增量编译器。你的任务不是把每条 source 各写一篇页面，
而是根据一组新增/变更 raw sources、候选旧 Wiki、Wiki index、产品和品牌上下文，输出可由 Odoo 应用的 Incremental Wiki Patch Plan JSON。
硬规则：
1. 只依据输入 source、候选 Wiki、引用和结构化产品信息，不编造事实。
2. 多条 source 属于同一主题时，应合并更新同一篇或少数几篇 Wiki，不要制造重复页面。
3. 已有候选 Wiki 更适合作为目标时，使用 update_article 或 merge_into_existing，并填写 target_article_id。
4. 发现冲突时，使用 mark_conflict 或 review_only，不要静默覆盖旧结论。
5. 每个关键事实必须在 patch.citations 中给出 source_document_id、excerpt、confidence。
6. 输出必须匹配 Incremental Wiki Patch Plan JSON；不要输出 Markdown 代码块、HTML、解释或 <think>。
"""

_DEFAULT_PROMPT_SOURCE_ROUTE_PLAN = """
你是模切行业知识管理的资料分发编辑。你的任务不是执行入库，而是先给出处理方案，让人确认后再执行。
请只输出一个 JSON 对象，不要 Markdown，不要 <think>，不要解释。

JSON 字段：
- source_kind: tds | selection_guide | application_note | processing_experience | qa | raw
- summary: 一句话说明资料价值
- recommended_actions: 字符串数组，可选 parse_source, compile_wiki, generate_faq, extract_material_draft, cross_reference, merge_existing, archive
- target_outputs: 字符串数组，可选 wiki, faq, material_draft, application_note, comparison
- requires_human_review: 布尔值
- risk_level: low | medium | high
- risk_notes: 字符串数组
- wiki_strategy: create | update_existing | merge_review | review_only | skip
- related_keywords: 字符串数组，品牌、型号、材料类别、应用场景关键词

判断原则：
1. TDS/技术数据表：通常需要 compile_wiki + extract_material_draft。
2. 选型指南/应用说明/加工经验：通常需要 compile_wiki + generate_faq + cross_reference。
3. 客户问答：通常需要 generate_faq + compile_wiki。
4. 资料不足、扫描质量差、来源不明、参数冲突时 requires_human_review=true。
5. 不要建议直接发布或直接入库；这里只做处理方案。
"""


_DEFAULT_PROMPT_WIKI_GRAPH_AGENT = """
你是企业 Wiki 图谱维护 Agent。你的任务是根据当前 Wiki 页面、原始资料、旧图谱边和候选旧 Wiki 页面，
判断应该保留/删除/新增哪些关联。请只输出 JSON，不要 Markdown，不要 <think>，不要解释正文。

核心规则：
1. 当前资料标题、品牌、正文优先级高于历史旧链接；如果历史链接来自旧标题误判，应删除。
2. 不要因为某个词偶然相同就建立强关联；必须说明业务原因。
3. 对同品牌、同型号、同材料体系、同应用场景、同工艺问题、对比、依赖、冲突、更新关系分别判断。
4. 如果存在标题污染、重复主题、冲突或不确定，设置 review_required=true，并在 notes 里说明。
5. links 只能引用候选页面 id，不要虚构 id。

JSON 结构：
{
  "links": [
    {
      "target_id": 123,
      "link_type": "mentions|same_brand|same_material|same_application|same_process|compares_with|depends_on|contradicts|updates",
      "anchor_text": "关联锚文本",
      "reason": "为什么应该关联",
      "confidence": 0.0
    }
  ],
  "remove_link_ids": [1, 2],
  "review_required": false,
  "notes": ["需要人工关注的事项"]
}
"""


class KbCompiler:
    PARAM_CHAT_URL = "diecut_knowledge.dify_chat_app_url"
    PARAM_CHAT_KEY = "diecut_knowledge.dify_chat_api_key"
    PARAM_AI_BACKEND = "diecut_knowledge.ai_backend"
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
            return self._fail_item(item, "未配置 AI 后端，无法执行 AI 编译", action="noop")

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
            inputs={"system": self._system_prompt("catalog_item_wiki", _DEFAULT_PROMPT_SINGLE)},
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
        self._connect_article_to_wiki_graph(article, False, self.env["diecut.catalog.item"].browse([item.id]), self._build_item_snapshot(item))
        KbLinter(self.env).lint_article(article)

        # 增量编译：异步更新品牌综述（失败不影响主流程）
        if item.brand_id:
            try:
                self.compile_brand_overview(item.brand_id.id)
            except Exception as exc:
                _logger.warning("品牌综述更新失败 (brand %s): %s", item.brand_id.name, exc)

        self._log_compile(item, "success", f"AI 编译{ '更新' if action == 'update' else '创建' }文章 [{article.name}]", duration, article_id=article.id)
        self._log_wiki_event("compile", f"产品 Wiki 编译：{article.name}", article=article, summary="产品结构化数据编译为 Wiki 页面，并接入图谱。")
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
            return {"ok": False, "action": "noop", "article_id": False, "error": "未配置 AI 后端，无法执行 LLM 编译"}

        source_text = self._get_source_document_text(source)
        if len(source_text.strip()) < 80:
            return {"ok": False, "action": "skip", "article_id": False, "error": "原始资料解析文本过短，请先解析 PDF 或补充正文"}

        context_hash = self._build_source_document_hash(source, source_text)
        existing = self._find_existing_source_article(source)
        if existing and not force and existing.compiled_hash == context_hash:
            return {"ok": True, "action": "noop", "article_id": existing.id, "error": None}

        context_text, linked_items = self._build_source_document_context(source, source_text)
        ok, payload, error, duration = client.chat_messages(
            query=f"请把以下原始资料编译成 Wiki Patch JSON：\n\n{context_text}",
            user=f"kb-source-compiler-{self.env.user.id}",
            inputs={"system": self._system_prompt("wiki_patch", _DEFAULT_PROMPT_SOURCE_DOCUMENT)},
        )
        if not ok:
            return {"ok": False, "action": "compile", "article_id": False, "error": f"LLM 编译失败：{error}"}

        raw_answer = self._clean_answer((payload or {}).get("answer", ""))
        wiki_patch = self._parse_wiki_patch_json(source, raw_answer, linked_items)
        answer_md = wiki_patch["page"]["content_md"]
        answer = kb_schema.markdown_to_html(answer_md)
        confidence, risk_level, risk_notes = self._score_source_compile(source, source_text, answer, linked_items)
        risk_notes.extend(wiki_patch.get("risk_notes") or [])
        if wiki_patch.get("review_required"):
            risk_level = "high" if wiki_patch.get("risk_level") == "high" else max(risk_level, "medium", key={"low": 1, "medium": 2, "high": 3}.get)
        if wiki_patch.get("risk_level") in {"low", "medium", "high"}:
            risk_level = max(risk_level, wiki_patch["risk_level"], key={"low": 1, "medium": 2, "high": 3}.get)
        if len(answer) < 300:
            confidence = min(confidence, 0.45)
            risk_level = "high"
            risk_notes.append("LLM 输出内容过短")

        summary = wiki_patch["page"]["summary"] or self._html_to_summary(answer)
        article_vals = self._build_source_article_vals(
            source=source,
            linked_items=linked_items,
            content_html=answer,
            content_md=answer_md,
            summary=summary,
            context_hash=context_hash,
            confidence=confidence,
            risk_level=risk_level,
            risk_notes=risk_notes,
            wiki_patch=wiki_patch,
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
        self._apply_wiki_patch_citations(article, source, wiki_patch)
        self._connect_article_to_wiki_graph(article, source, linked_items, source_text, seed_plan=wiki_patch)
        KbLinter(self.env).lint_article(article)
        self._log_source_compile(source, "success", f"LLM 编译{ '更新' if action == 'update' else '创建' } Wiki 文章 [{article.name}]", duration, article.id)
        self._log_wiki_event(
            "compile",
            f"Wiki 编译：{article.name}",
            article=article,
            source=source,
            summary=f"资料编译{ '更新' if action == 'update' else '创建' }页面，并接入 Wiki 图谱。",
        )
        return {
            "ok": True,
            "action": action,
            "article_id": article.id,
            "error": None,
            "risk_level": risk_level,
            "confidence": confidence,
            "llm_payload_json": json.dumps(wiki_patch, ensure_ascii=False, indent=2),
            "validation_message": "Wiki Patch JSON 已归一化并应用。",
        }

    def find_incremental_wiki_targets(self, sources, limit=12):
        candidates = self.env["diecut.kb.article"].browse()
        for source in sources:
            source_text = self._get_source_document_text(source)
            candidates |= self._find_wiki_candidates(
                source=source,
                source_text=source_text,
                linked_items=source.compiled_item_ids,
                limit=limit,
            )
            if len(candidates) >= limit:
                break
        if len(candidates) < limit:
            candidates |= self.env["diecut.kb.article"].sudo().search(
                [("active", "=", True), ("state", "in", ("review", "published"))],
                limit=limit - len(candidates),
                order="graph_degree desc, write_date desc",
            )
        return candidates[:limit]

    def compile_incremental_wiki_job(self, job):
        job.ensure_one()
        sources = job.incremental_source_document_ids.exists()
        if not sources:
            return {"ok": False, "action": "skip", "article_ids": [], "error": "增量编译任务没有关联资料"}
        client = self._build_client()
        if not client:
            sources.write({"wiki_compile_state": "failed", "wiki_compile_error": "未配置 AI 后端，无法执行增量编译"})
            return {"ok": False, "action": "noop", "article_ids": [], "error": "未配置 AI 后端，无法执行增量编译"}

        context_text, target_articles = self._build_incremental_wiki_context(sources, job=job)
        ok, payload, error, duration = client.chat_messages(
            query="请根据以下全库上下文生成 Incremental Wiki Patch Plan JSON：\n\n%s" % context_text,
            user=f"kb-incremental-wiki-{self.env.user.id}",
            inputs={"system": self._system_prompt("incremental_wiki_patch", _DEFAULT_PROMPT_INCREMENTAL_WIKI)},
        )
        if not ok:
            sources.write({"wiki_compile_state": "failed", "wiki_compile_error": "LLM 增量编译失败：%s" % error})
            return {
                "ok": False,
                "action": "compile",
                "article_ids": [],
                "error": "LLM 增量编译失败：%s" % error,
                "validation_message": "LLM request failed before JSON validation.",
                "risk_level": "high",
            }

        if (payload or {}).get("queued"):
            sources.write({"wiki_compile_state": "queued", "wiki_compile_error": False})
            queued_payload = {
                "queued": True,
                "run_id": (payload or {}).get("run_id") or "",
                "run_db_id": (payload or {}).get("run_db_id") or False,
                "duration_ms": duration,
            }
            return {
                "ok": False,
                "action": "queued",
                "article_ids": [],
                "openclaw_run_id": queued_payload["run_db_id"],
                "openclaw_run_uuid": queued_payload["run_id"],
                "error": False,
                "llm_payload_json": json.dumps(queued_payload, ensure_ascii=False, indent=2),
                "validation_message": "OpenClaw 已提交，等待 worker 完成。",
            }

        return self.apply_incremental_wiki_answer(job, (payload or {}).get("answer", ""))

    def apply_incremental_wiki_answer(self, job, raw_answer):
        job.ensure_one()
        sources = job.incremental_source_document_ids.exists()
        if not sources:
            return {"ok": False, "action": "skip", "article_ids": [], "error": "增量编译任务没有关联资料"}
        raw_answer = self._clean_answer(raw_answer or "")
        _context_text, target_articles = self._build_incremental_wiki_context(sources, job=job)
        plan = kb_schema.normalize_incremental_wiki_patch_plan(
            kb_schema.extract_json_object(raw_answer),
            sources=sources,
            fallback_title=job.compile_group_key or "Incremental Wiki",
        )
        if not plan.get("patches"):
            sources.write({"wiki_compile_state": "failed", "wiki_compile_error": "LLM 未返回有效的增量 Wiki patch"})
            diagnostic_payload = {
                "parse_error": "No patches parsed from LLM response.",
                "raw_answer_excerpt": raw_answer[:4000],
                "normalized_plan": plan,
            }
            return {
                "ok": False,
                "action": "compile",
                "article_ids": [],
                "error": "LLM 未返回有效的增量 Wiki patch",
                "risk_level": "high",
                "llm_payload_json": json.dumps(diagnostic_payload, ensure_ascii=False, indent=2),
                "validation_message": "Incremental Wiki Patch Plan JSON 缺少有效 patches；已保存 LLM 原始回复片段。",
            }

        article_ids = []
        risk_order = {"low": 1, "medium": 2, "high": 3}
        group_risk = plan.get("risk_level") or "medium"
        for patch in plan["patches"]:
            result = self._apply_incremental_wiki_patch(patch, sources, target_articles, job)
            if result.get("article"):
                article_ids.append(result["article"].id)
            group_risk = max(group_risk, result.get("risk_level") or group_risk, key=risk_order.get)

        snapshot = self._job_source_hash_snapshot(job, sources)
        now = fields.Datetime.now()
        for source in sources:
            source_hash = snapshot.get(str(source.id)) or source._incremental_source_hash()
            source.write(
                {
                    "wiki_compile_state": "compiled",
                    "wiki_compile_hash": source_hash,
                    "wiki_compiled_at": now,
                    "wiki_compile_error": False,
                }
            )
        self._log_wiki_event(
            "compile",
            "Incremental Wiki compile: %s" % (job.compile_group_key or job.display_name),
            source=sources[:1],
            summary="全库感知增量编译完成，生成/更新 %s 篇 Wiki。" % len(set(article_ids)),
            payload=plan,
        )
        return {
            "ok": True,
            "action": "incremental_compile",
            "article_id": article_ids[0] if article_ids else False,
            "article_ids": list(dict.fromkeys(article_ids)),
            "error": None,
            "risk_level": group_risk,
            "llm_payload_json": json.dumps(plan, ensure_ascii=False, indent=2),
            "validation_message": "Incremental Wiki Patch Plan JSON 已归一化并应用。",
        }

    def _build_incremental_wiki_context(self, sources, job=False):
        context_limit = int(
            self.env["ir.config_parameter"].sudo().get_param(
                "diecut_knowledge.incremental_wiki_context_article_limit", default="12"
            )
            or 12
        )
        target_articles = (job.target_article_ids if job else self.env["diecut.kb.article"].browse()) or self.find_incremental_wiki_targets(sources, limit=context_limit)
        linked_items = sources.mapped("compiled_item_ids")
        source_blocks = []
        for source in sources:
            source_text = self._get_source_document_text(source)
            source_blocks.append(
                {
                    "id": source.id,
                    "title": source.name or source.primary_attachment_name or source.source_filename or "",
                    "vault_raw_path": source.vault_raw_path or "",
                    "vault_file_hash": source.vault_file_hash or "",
                    "incremental_hash": source._incremental_source_hash(),
                    "source_kind": source.knowledge_source_kind or "",
                    "parse_state": source.knowledge_parse_state or "",
                    "brand": source.brand_id.name if source.brand_id else "",
                    "category": source.categ_id.complete_name if source.categ_id else "",
                    "linked_items": source.compiled_item_ids.mapped("code"),
                    "text_excerpt": source_text[:9000],
                }
            )
        payload = {
            "schema": kb_schema.INCREMENTAL_WIKI_PATCH_PLAN_SCHEMA,
            "group_key": job.compile_group_key if job else "",
            "sources": source_blocks,
            "linked_items": [
                {
                    "id": item.id,
                    "code": item.code or "",
                    "name": item.name or "",
                    "brand": item.brand_id.name if item.brand_id else "",
                    "category": item.categ_id.complete_name if item.categ_id else "",
                    "snapshot": self._build_item_snapshot(item),
                }
                for item in linked_items[:15]
            ],
            "candidate_wiki_targets": [
                {
                    "id": article.id,
                    "title": article.name,
                    "wiki_page_type": article.wiki_page_type or "",
                    "summary": article.summary or "",
                    "keywords": article.keywords or "",
                    "state": article.state,
                    "compiled_hash": article.compiled_hash or "",
                    "brands": article.related_brand_ids.mapped("name"),
                    "items": article.related_item_ids.mapped("code"),
                    "categories": article.related_categ_ids.mapped("complete_name"),
                    "content_excerpt": (article.content_text or article.content_md or "")[:1800],
                }
                for article in target_articles
            ],
            "wiki_index": [
                {
                    "id": article.id,
                    "title": article.name,
                    "type": article.wiki_page_type or "",
                    "degree": article.graph_degree,
                    "summary": article.summary or "",
                }
                for article in self.env["diecut.kb.article"].sudo().search(
                    [("active", "=", True), ("state", "in", ("review", "published"))],
                    limit=80,
                    order="graph_degree desc, write_date desc",
                )
            ],
        }
        return json.dumps(payload, ensure_ascii=False, indent=2), target_articles

    def _apply_incremental_wiki_patch(self, patch, sources, target_articles, job=False):
        source_ids = patch.get("source_document_ids") or sources.ids
        patch_sources = sources.filtered(lambda source: source.id in source_ids) or sources
        primary_source = patch_sources[:1]
        linked_items = patch_sources.mapped("compiled_item_ids")
        page = patch.get("page") or {}
        target = self._resolve_incremental_target_article(patch, target_articles)
        risk_level = patch.get("risk_level") or "medium"
        confidence = 0.8 if risk_level == "low" and not patch.get("review_required") else 0.55
        risk_notes = list(patch.get("risk_notes") or [])
        if patch.get("operation") in {"merge_into_existing", "mark_conflict", "review_only"}:
            risk_level = "high" if patch.get("operation") == "mark_conflict" else max(risk_level, "medium", key={"low": 1, "medium": 2, "high": 3}.get)
            risk_notes.append("增量 patch 需要人工复核：%s" % patch.get("operation"))
        content_md = page.get("content_md") or ""
        content_html = kb_schema.markdown_to_html(content_md)
        if risk_notes:
            content_html += self._risk_notes_html(risk_notes)
            content_md += "\n\n## 需要人工复核\n" + "\n".join("- %s" % note for note in risk_notes)
        summary = page.get("summary") or self._html_to_summary(content_html)
        context_hash = self._build_incremental_article_hash(patch_sources, patch, target)
        vals = self._build_incremental_article_vals(
            source=primary_source,
            sources=patch_sources,
            linked_items=linked_items,
            page=page,
            content_html=content_html,
            content_md=content_md,
            summary=summary,
            context_hash=context_hash,
            confidence=confidence,
            risk_level=risk_level,
            risk_notes=risk_notes,
        )
        if target and patch.get("operation") != "create_article":
            target.write(vals)
            article = target
            action = "update"
        else:
            article = self.env["diecut.kb.article"].create(vals)
            action = "create"
        from .kb_enricher import KbEnricher
        from .kb_linter import KbLinter

        KbEnricher(self.env).enrich_article(article)
        self._apply_wiki_patch_citations(article, primary_source, patch)
        combined_text = "\n\n".join(self._get_source_document_text(source)[:4000] for source in patch_sources)
        self._connect_article_to_wiki_graph(article, primary_source, linked_items, combined_text, seed_plan=patch)
        KbLinter(self.env).lint_article(article)
        self._log_wiki_event(
            "compile",
            "Incremental Wiki %s: %s" % (action, article.name),
            article=article,
            source=primary_source,
            summary="由 %s 条 source 参与的全库感知增量 patch。" % len(patch_sources),
            payload=patch,
        )
        return {"article": article, "risk_level": risk_level}

    def _resolve_incremental_target_article(self, patch, target_articles):
        page = patch.get("page") or {}
        article_model = self.env["diecut.kb.article"].sudo()
        target_id = page.get("target_article_id")
        if target_id:
            try:
                target_id = int(target_id)
            except Exception:
                target_id = 0
            article = article_model.browse(target_id).exists()
            if article:
                return article
        slug = page.get("wiki_slug")
        if slug:
            article = article_model.search([("wiki_slug", "=", slug), ("active", "=", True)], limit=1)
            if article:
                return article
        title = page.get("title")
        if title:
            article = (target_articles or article_model).filtered(lambda rec: rec.name == title)[:1]
            if article:
                return article
        return article_model.browse()

    def _build_incremental_article_vals(self, source, sources, linked_items, page, content_html, content_md, summary, context_hash, confidence, risk_level, risk_notes):
        category = self._get_compile_category()
        auto_publish = self._auto_publish_enabled()
        should_publish = auto_publish and confidence >= 0.75 and risk_level == "low"
        title = page.get("title") or (source.name if source else "") or "Incremental Wiki"
        brands = (sources.mapped("brand_id") | linked_items.mapped("brand_id")).ids
        categories = (sources.mapped("categ_id") | linked_items.mapped("categ_id")).ids
        keywords = list(
            dict.fromkeys(
                list(page.get("keywords") or [])
                + sources.mapped("name")
                + sources.mapped("brand_id.name")
                + linked_items.mapped("code")
                + linked_items.mapped("name")
            )
        )
        vals = {
            "name": title[:200],
            "category_id": category.id,
            "content_html": content_html,
            "content_md": content_md or self._html_to_markdownish(content_html),
            "summary": summary,
            "state": "published" if should_publish else "review",
            "publish_date": fields.Date.context_today(self.env.user) if should_publish else False,
            "sync_status": "pending" if should_publish else "skipped",
            "compile_source": "source_document",
            "wiki_page_type": page.get("wiki_page_type") or (self._wiki_page_type_for_source(source) if source else "source_summary"),
            "wiki_slug": page.get("wiki_slug") or kb_schema.slugify(title),
            "compile_source_document_id": source.id if source else False,
            "compile_source_item_id": linked_items[:1].id if linked_items else False,
            "compiled_at": fields.Datetime.now(),
            "compiled_hash": context_hash,
            "compile_confidence": confidence,
            "compile_risk_level": risk_level,
            "source_page_refs": ", ".join(filter(None, [self._source_page_refs(item) for item in sources])),
            "source_file_name": ", ".join(filter(None, sources.mapped("primary_attachment_name") or sources.mapped("source_filename")))[:255],
            "source_url": source.source_url if source else False,
            "author_name": source.brand_id.name if source and source.brand_id else "",
            "keywords": ", ".join(filter(None, keywords))[:1000],
            "related_brand_ids": [(6, 0, brands)] if brands else False,
            "related_categ_ids": [(6, 0, categories)] if categories else False,
            "related_item_ids": [(6, 0, linked_items.ids)] if linked_items else False,
        }
        return {key: value for key, value in vals.items() if value is not False}

    def _build_incremental_article_hash(self, sources, patch, target=False):
        payload = {
            "sources": {str(source.id): source._incremental_source_hash() for source in sources},
            "patch": patch,
            "target": {
                "id": target.id if target else False,
                "write_date": fields.Datetime.to_string(target.write_date) if target and target.write_date else "",
                "compiled_hash": target.compiled_hash if target else "",
            },
        }
        return hashlib.sha1(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()

    def _job_source_hash_snapshot(self, job, sources):
        try:
            snapshot = json.loads(job.source_hash_snapshot or "{}")
        except Exception:
            snapshot = {}
        for source in sources:
            snapshot.setdefault(str(source.id), source._incremental_source_hash())
        return snapshot

    def generate_source_route_plan(self, source):
        source.ensure_one()
        source_text = self._get_source_document_text(source)
        client = self._build_client()
        if not client:
            plan = self._build_rule_based_route_plan(source, source_text, note="未配置 AI 后端，已生成规则型处理方案。")
        else:
            context = self._build_route_plan_context(source, source_text)
            ok, payload, error, duration = client.chat_messages(
                query=f"请为以下原始资料生成处理方案：\n\n{context}",
                user=f"kb-route-plan-{self.env.user.id}",
                inputs={"system": self._system_prompt("ingest_plan", _DEFAULT_PROMPT_SOURCE_ROUTE_PLAN)},
            )
            if not ok:
                plan = self._build_rule_based_route_plan(source, source_text, note=f"LLM 方案生成失败：{error}；已生成规则型处理方案。")
            else:
                answer = self._clean_answer((payload or {}).get("answer", ""))
                plan = kb_schema.extract_json_object(answer) or self._build_rule_based_route_plan(
                    source,
                    source_text,
                    note="LLM 返回格式不是有效 JSON，已生成规则型处理方案。",
                )
                plan.setdefault("llm_duration_ms", duration or 0)
        plan = self._normalize_route_plan(source, plan)
        source.write({
            "route_plan_state": "ready",
            "route_plan_summary": self._route_plan_summary(plan),
            "route_plan_json": json.dumps(plan, ensure_ascii=False, indent=2),
            "route_plan_error": False,
            "route_plan_generated_at": fields.Datetime.now(),
            "route_plan_confirmed_at": False,
        })
        return {"ok": True, "action": "plan", "error": None}

    def execute_source_route_plan(self, source):
        source.ensure_one()
        plan = source._load_route_plan() if hasattr(source, "_load_route_plan") else {}
        if not plan:
            return {"ok": False, "action": "execute", "error": "请先生成 AI 处理方案"}
        actions = set(plan.get("recommended_actions") or [])
        if "archive" in actions and len(actions) == 1:
            source.write({
                "route_plan_state": "done",
                "route_plan_confirmed_at": fields.Datetime.now(),
            })
            return {"ok": True, "action": "archive", "error": None}

        source.write({
            "route_plan_state": "running",
            "route_plan_confirmed_at": fields.Datetime.now(),
        })
        errors = []

        if "parse_source" in actions and source.knowledge_parse_state != "parsed" and source.primary_attachment_id:
            try:
                source.action_parse_for_knowledge()
            except Exception as exc:
                errors.append(f"解析失败：{exc}")

        if "extract_material_draft" in actions:
            try:
                source.action_extract_material_draft()
            except Exception as exc:
                errors.append(f"TDS 参数抽取失败：{exc}")

        article_result = {"ok": True}
        if actions & {"compile_wiki", "generate_faq", "cross_reference", "merge_existing"}:
            try:
                article_result = self.compile_from_source_document(source, force=True)
                if not article_result.get("ok"):
                    errors.append(article_result.get("error") or "Wiki 编译失败")
            except Exception as exc:
                errors.append(f"Wiki 编译失败：{exc}")

        source.write({
            "route_plan_state": "review" if errors or plan.get("requires_human_review") else "done",
            "route_plan_error": "\n".join(errors) if errors else False,
        })
        return {
            "ok": not errors,
            "action": "execute",
            "article_id": article_result.get("article_id") if isinstance(article_result, dict) else False,
            "error": "\n".join(errors) if errors else None,
        }

    def compile_comparison(self, items):
        if len(items) < 2:
            return {"ok": False, "article_id": False, "error": "至少需要 2 个产品才能生成对比分析"}
        client = self._build_client()
        if not client:
            return {"ok": False, "article_id": False, "error": "未配置 AI 后端"}

        blocks = []
        for item in items:
            blocks.append(f"--- 产品 {item.code or item.name} ---\n{self._build_item_snapshot(item)}")
        ok, payload, error, _duration = client.chat_messages(
            query="请对以下多个产品生成对比选型文章：\n\n%s" % ("\n\n".join(blocks)),
            user=f"kb-compiler-{self.env.user.id}",
            inputs={"system": self._system_prompt("comparison_wiki", _DEFAULT_PROMPT_COMPARISON)},
        )
        if not ok:
            return {"ok": False, "article_id": False, "error": error or "AI 对比编译失败"}

        answer = self._clean_answer((payload or {}).get("answer", ""))
        if len(answer) < 80:
            return {"ok": False, "article_id": False, "error": "AI 对比文章内容过短"}

        category = self._get_compile_category()
        title = "对比分析：%s" % " vs ".join(items.mapped("code") or items.mapped("name"))
        auto_publish = self._auto_publish_enabled()
        article_state = "published" if auto_publish else "review"
        article = self.env["diecut.kb.article"].create({
            "name": title[:200],
            "category_id": category.id,
            "content_html": answer,
            "content_md": self._html_to_markdownish(answer),
            "summary": self._html_to_summary(answer),
            "state": article_state,
            "publish_date": fields.Date.context_today(self.env.user) if article_state == "published" else False,
            "sync_status": "pending" if article_state == "published" else "skipped",
            "compile_source": "comparison",
            "wiki_page_type": "comparison",
            "compiled_at": fields.Datetime.now(),
            "compiled_hash": hashlib.sha1(
                "\n".join(self._build_item_snapshot(item) for item in items).encode("utf-8")
            ).hexdigest(),
            "compile_confidence": 0.8,
            "compile_risk_level": "low",
            "related_item_ids": [(6, 0, items.ids)],
            "related_brand_ids": [(6, 0, items.mapped("brand_id").ids)],
            "related_categ_ids": [(6, 0, items.mapped("categ_id").ids)],
            "keywords": ", ".join(filter(None, items.mapped("code"))),
        })
        from .kb_enricher import KbEnricher
        from .kb_linter import KbLinter

        KbEnricher(self.env).enrich_article(article)
        self._connect_article_to_wiki_graph(article, False, items, "\n".join(self._build_item_snapshot(item) for item in items))
        KbLinter(self.env).lint_article(article)
        self._log_wiki_event("compile", f"对比 Wiki 编译：{article.name}", article=article, summary="产品对比分析编译为 Wiki 页面，并接入图谱。")
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
            return {"ok": False, "action": "noop", "article_id": False, "error": "AI 后端未配置"}

        ok, payload, error, duration = client.chat_messages(
            query=f"请根据以下品牌数据生成品牌综述文章：\n\n{context_text}",
            user=f"kb-overview-{self.env.user.id}",
            inputs={"system": self._system_prompt("brand_overview", _DEFAULT_PROMPT_BRAND_OVERVIEW)},
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
            "content_md": self._html_to_markdownish(answer),
            "summary": self._html_to_summary(answer),
            "state": "published" if auto_publish else "review",
            "publish_date": fields.Date.context_today(self.env.user) if auto_publish else False,
            "sync_status": "pending" if auto_publish else "skipped",
            "compile_source": "brand_overview",
            "wiki_page_type": "brand",
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
        self._connect_article_to_wiki_graph(article, False, items, context_text)
        KbLinter(self.env).lint_article(article)
        self._log_wiki_event("compile", f"品牌 Wiki 编译：{article.name}", article=article, summary="品牌综述编译为 Wiki 页面，并接入图谱。")
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
            "### LLM Wiki Schema",
            json.dumps(kb_schema.WIKI_PATCH_SCHEMA, ensure_ascii=False, indent=2),
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
        wiki_candidates = self._find_wiki_candidates(source, source_text, linked_items=linked_items, limit=10)
        if wiki_candidates:
            parts.append("\n### 旧 Wiki 候选页面（编译时必须判断关联、更新、合并或冲突）")
            for article in wiki_candidates:
                parts.append(
                    json.dumps(
                        {
                            "id": article.id,
                            "title": article.name,
                            "type": article.wiki_page_type or "",
                            "summary": article.summary or article.content_text[:240],
                            "brands": article.related_brand_ids.mapped("name"),
                            "items": article.related_item_ids.mapped("code"),
                            "categories": article.related_categ_ids.mapped("complete_name"),
                        },
                        ensure_ascii=False,
                    )
                )
        index_articles = self.env["diecut.kb.article"].sudo().search(
            [("active", "=", True), ("state", "in", ("review", "published"))],
            limit=80,
            order="graph_degree desc, write_date desc",
        )
        if index_articles:
            parts.append("\n### Wiki Index 摘要（先读索引，再判断候选页面）")
            for article in index_articles:
                parts.append(
                    "- #%s %s [%s] degree=%s: %s"
                    % (
                        article.id,
                        article.name,
                        article.wiki_page_type or "wiki",
                        article.graph_degree,
                        (article.summary or article.content_text[:120] or "").strip(),
                    )
                )
        return "\n\n".join(filter(None, parts)), linked_items

    def _build_route_plan_context(self, source, source_text):
        linked_items = source.compiled_item_ids
        payload = {
            "schema": kb_schema.INGEST_PLAN_SCHEMA,
            "title": source.name or "",
            "source_type": source.source_type or "",
            "source_url": source.source_url or "",
            "source_file": source.primary_attachment_name or source.source_filename or "",
            "brand": source.brand_id.name if source.brand_id else "",
            "category": source.categ_id.complete_name if source.categ_id else "",
            "knowledge_source_kind": source.knowledge_source_kind or "",
            "parse_state": source.knowledge_parse_state or "",
            "page_count": source.knowledge_page_count or 0,
            "import_status": source.import_status or "",
            "linked_items": linked_items.mapped("code"),
            "text_excerpt": (source_text or source.raw_text or source.result_message or "")[:12000],
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def _parse_route_plan_json(self, answer):
        return kb_schema.extract_json_object(answer)

    def _parse_wiki_patch_json(self, source, answer, linked_items=False):
        payload = kb_schema.extract_json_object(answer)
        fallback_title = source.name or source.primary_attachment_name or source.source_filename or "未命名资料"
        fallback_summary = "根据原始资料生成的 Wiki 草稿，需按来源引用复核。"
        fallback_content = ""
        if not payload:
            fallback_content = self._html_to_markdownish(answer)
            if not fallback_content:
                fallback_content = "# %s\n\n%s" % (fallback_title, answer or "")
            payload = {
                "page": {
                    "title": fallback_title,
                    "wiki_slug": kb_schema.slugify(fallback_title),
                    "wiki_page_type": self._wiki_page_type_for_source(source),
                    "summary": self._html_to_summary(answer) or fallback_summary,
                    "content_md": fallback_content,
                    "keywords": list(filter(None, [source.brand_id.name if source.brand_id else "", source.name or ""])),
                },
                "citations": [
                    {
                        "claim_text": fallback_summary,
                        "source_document_id": source.id,
                        "page_ref": self._source_page_refs(source),
                        "excerpt": (self._get_source_document_text(source) or "")[:800],
                        "confidence": 0.45,
                        "state": "review",
                    }
                ],
                "review_required": True,
                "risk_level": "high",
                "risk_notes": ["LLM 未返回合法 Wiki Patch JSON，已按原始回答生成待审核草稿。"],
            }
        patch = kb_schema.normalize_wiki_patch(
            payload,
            source=source,
            fallback_title=fallback_title,
            fallback_summary=fallback_summary,
            fallback_content=fallback_content,
        )
        if not patch["page"]["wiki_page_type"]:
            patch["page"]["wiki_page_type"] = self._wiki_page_type_for_source(source)
        if linked_items and not patch["page"]["keywords"]:
            patch["page"]["keywords"] = linked_items.mapped("code")
        return patch

    def _build_rule_based_route_plan(self, source, source_text, note=""):
        kind = source.knowledge_source_kind or "raw"
        haystack = " ".join(
            filter(
                None,
                [
                    source.name or "",
                    source.primary_attachment_name or "",
                    source.source_filename or "",
                    (source_text or source.raw_text or "")[:3000],
                ],
            )
        ).lower()
        if re.search(r"\btds\b|technical data sheet|datasheet|技术数据|数据表", haystack):
            kind = "tds"
        elif any(token in haystack for token in ("选型", "selection guide", "selection handbook")):
            kind = "selection_guide"
        elif any(token in haystack for token in ("应用", "application", "方案", "case study")):
            kind = "application_note"
        elif any(token in haystack for token in ("加工", "工艺", "经验", "process", "troubleshooting")):
            kind = "processing_experience"
        elif any(token in haystack for token in ("faq", "问答", "q&a", "问题")):
            kind = "qa"

        actions = ["compile_wiki", "generate_faq", "cross_reference"]
        outputs = ["wiki", "faq"]
        if source.primary_attachment_id and source.knowledge_parse_state != "parsed":
            actions.insert(0, "parse_source")
        if kind == "tds":
            actions.append("extract_material_draft")
            outputs.append("material_draft")
        notes = []
        if note:
            notes.append(note)
        if not source_text and not source.raw_text:
            notes.append("缺少已解析正文，建议先解析原始资料。")
        if not source.knowledge_page_count:
            notes.append("缺少来源页码。")
        return {
            "source_kind": kind,
            "summary": "将该资料编译为可检索 Wiki；如为 TDS，同时生成材料结构化草稿。",
            "recommended_actions": list(dict.fromkeys(actions)),
            "target_outputs": list(dict.fromkeys(outputs)),
            "requires_human_review": bool(notes),
            "risk_level": "medium" if notes else "low",
            "risk_notes": notes,
            "wiki_strategy": "create",
            "related_keywords": list(filter(None, [source.brand_id.name if source.brand_id else "", source.name or ""])),
        }

    def _normalize_route_plan(self, source, plan):
        normalized = kb_schema.normalize_ingest_plan(plan, default_kind=source.knowledge_source_kind or "raw")
        if normalized.get("source_kind") == "tds" and "extract_material_draft" not in normalized["recommended_actions"]:
            normalized["recommended_actions"].append("extract_material_draft")
        if normalized.get("source_kind") == "tds" and "material_draft" not in normalized["target_outputs"]:
            normalized["target_outputs"].append("material_draft")
        if source.primary_attachment_id and source.knowledge_parse_state != "parsed" and "parse_source" not in normalized["recommended_actions"]:
            normalized["recommended_actions"].insert(0, "parse_source")
        return normalized

    def _route_plan_summary(self, plan):
        action_labels = {
            "parse_source": "解析原始资料",
            "compile_wiki": "生成 Wiki",
            "generate_faq": "生成 FAQ",
            "extract_material_draft": "抽取材料参数",
            "cross_reference": "建立交叉引用",
            "merge_existing": "检查合并已有文章",
            "archive": "归档",
        }
        actions = "、".join(action_labels.get(action, action) for action in plan.get("recommended_actions", []))
        review = "需要人工审核" if plan.get("requires_human_review") else "可确认执行"
        return "%s\n建议动作：%s\n风险：%s，%s" % (
            plan.get("summary") or "",
            actions or "无",
            plan.get("risk_level") or "medium",
            review,
        )

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
        critical_notes = {"原始资料未完成知识解析", "缺少来源页码", "LLM 输出内容过短"}
        if confidence >= 0.75 and not (critical_notes & set(notes)):
            risk = "low"
        elif confidence >= 0.55:
            risk = "medium"
        else:
            risk = "high"
        return confidence, risk, notes

    def _build_source_article_vals(
        self,
        source,
        linked_items,
        content_html,
        content_md,
        summary,
        context_hash,
        confidence,
        risk_level,
        risk_notes,
        wiki_patch=False,
    ):
        category = self._get_compile_category()
        auto_publish = self._auto_publish_enabled()
        should_publish = auto_publish and confidence >= 0.75 and risk_level == "low"
        page = (wiki_patch or {}).get("page") or {}
        title = page.get("title") or source.name or source.primary_attachment_name or source.source_filename or "未命名资料"
        source_refs = self._source_page_refs(source)
        if risk_notes:
            content_html = content_html + self._risk_notes_html(risk_notes)
            content_md = (content_md or "") + "\n\n## 需要人工复核\n" + "\n".join("- %s" % note for note in risk_notes if note)
        vals = {
            "name": f"[Wiki] {title}"[:200],
            "category_id": category.id,
            "content_html": content_html,
            "content_md": content_md or self._html_to_markdownish(content_html),
            "summary": summary,
            "state": "published" if should_publish else "review",
            "publish_date": fields.Date.context_today(self.env.user) if should_publish else False,
            "sync_status": "pending" if should_publish else "skipped",
            "compile_source": "source_document",
            "wiki_page_type": page.get("wiki_page_type") or self._wiki_page_type_for_source(source),
            "wiki_slug": page.get("wiki_slug") or kb_schema.slugify(title),
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
            "keywords": ", ".join(
                filter(
                    None,
                    [
                        *(page.get("keywords") or []),
                        source.name,
                        source.brand_id.name if source.brand_id else "",
                        *(linked_items.mapped("code") or []),
                    ],
                )
            ),
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
            "content_md": self._html_to_markdownish(content_html),
            "summary": summary,
            "state": state,
            "publish_date": fields.Date.context_today(self.env.user) if auto_publish else False,
            "sync_status": "pending" if state == "published" else "skipped",
            "compile_source": "catalog_item",
            "wiki_page_type": "material",
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
        from .llm_client_factory import build_chat_client

        client, error, profile = build_chat_client(
            self.env,
            model_profile_id=self.env.context.get("llm_model_profile_id"),
            purpose="wiki_compile",
        )
        if error:
            _logger.warning("Failed to build LLM client: %s", error)
        self._client = client
        return self._client

    def _build_dify_client(self, icp):
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

    def _build_claude_client(self, icp):
        api_key = (icp.get_param("diecut_knowledge.claude_api_key") or "").strip()
        model = (icp.get_param("diecut_knowledge.claude_model") or "").strip()
        base_url = (icp.get_param("diecut_knowledge.claude_base_url") or "").strip()
        max_tokens_str = (icp.get_param("diecut_knowledge.claude_max_tokens") or "").strip()
        if not api_key:
            return None
        from .claude_client import ClaudeClient

        kwargs = {"api_key": api_key}
        if model:
            kwargs["model"] = model
        if base_url:
            kwargs["base_url"] = base_url
        if max_tokens_str and max_tokens_str.isdigit():
            kwargs["max_tokens"] = int(max_tokens_str)
        kwargs["timeout"] = 120
        self._client = ClaudeClient(**kwargs)
        return self._client

    def _system_prompt(self, rule_type, fallback_prompt):
        try:
            return build_system_prompt(rule_type, default=fallback_prompt)
        except Exception as exc:
            _logger.warning("Failed to build %s system prompt from files: %s", rule_type, exc)
        try:
            return self.env["diecut.kb.compile.rule"].build_system_prompt(rule_type, fallback_prompt)
        except Exception as exc:
            _logger.warning("Failed to build %s fallback prompt from rules: %s", rule_type, exc)
        return fallback_prompt

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
            "items": [
                {
                    "code": item.code or "",
                    "write_date": fields.Datetime.to_string(item.write_date) if item.write_date else "",
                    "compile_hash": item.compile_hash or "",
                    "snapshot": self._build_item_snapshot(item),
                }
                for item in source.compiled_item_ids
            ],
        }
        return hashlib.sha1(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()

    def _source_page_refs(self, source):
        if not source:
            return ""
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

    def _html_to_markdownish(self, html):
        text = html or ""
        text = re.sub(r"<h2[^>]*>(.*?)</h2>", r"\n## \1\n", text, flags=re.I | re.S)
        text = re.sub(r"<h3[^>]*>(.*?)</h3>", r"\n### \1\n", text, flags=re.I | re.S)
        text = re.sub(r"<li[^>]*>(.*?)</li>", r"- \1\n", text, flags=re.I | re.S)
        text = re.sub(r"</p\s*>", "\n\n", text, flags=re.I)
        text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"&nbsp;", " ", text, flags=re.I)
        text = re.sub(r"&amp;", "&", text, flags=re.I)
        text = re.sub(r"&lt;", "<", text, flags=re.I)
        text = re.sub(r"&gt;", ">", text, flags=re.I)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        return text.strip()

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

    def _wiki_page_type_for_source(self, source):
        kind = source.knowledge_source_kind if source else ""
        mapping = {
            "tds": "material",
            "selection_guide": "application",
            "application_note": "application",
            "processing_experience": "process",
            "qa": "faq",
        }
        return mapping.get(kind, "source_summary")

    def _find_wiki_candidates(self, source=False, source_text="", linked_items=False, limit=10, exclude_article=False):
        article_model = self.env["diecut.kb.article"].sudo()
        domain = [("active", "=", True), ("state", "in", ("review", "published"))]
        if exclude_article:
            domain.append(("id", "!=", exclude_article.id))

        candidates = article_model.browse()
        if linked_items:
            brand_ids = linked_items.mapped("brand_id").ids
            categ_ids = linked_items.mapped("categ_id").ids
            item_ids = linked_items.ids
            if item_ids:
                candidates |= article_model.search(domain + [("related_item_ids", "in", item_ids)], limit=limit)
            if brand_ids:
                candidates |= article_model.search(domain + [("related_brand_ids", "in", brand_ids)], limit=limit)
            if categ_ids:
                candidates |= article_model.search(domain + [("related_categ_ids", "in", categ_ids)], limit=limit)

        if source and source.brand_id:
            candidates |= article_model.search(domain + [("related_brand_ids", "in", source.brand_id.ids)], limit=limit)

        keywords = self._extract_graph_keywords(source, source_text, linked_items)
        for keyword in keywords[:8]:
            candidates |= article_model.search(
                domain
                + [
                    "|",
                    "|",
                    "|",
                    ("name", "ilike", keyword),
                    ("summary", "ilike", keyword),
                    ("keywords", "ilike", keyword),
                    ("content_text", "ilike", keyword),
                ],
                limit=3,
            )
            if len(candidates) >= limit:
                break
        return (candidates - exclude_article)[:limit] if exclude_article else candidates[:limit]

    def _extract_graph_keywords(self, source=False, source_text="", linked_items=False):
        values = []
        if source:
            values.extend([source.name or "", source.brand_id.name if source.brand_id else ""])
        if linked_items:
            values.extend(linked_items.mapped("code"))
            values.extend(linked_items.mapped("name"))
            values.extend(linked_items.mapped("brand_id.name"))
            values.extend(linked_items.mapped("categ_id.name"))
        text = source_text or ""
        for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9\-_/]{1,}|[\u4e00-\u9fff]{2,8}", text[:6000]):
            if token not in values:
                values.append(token)
            if len(values) >= 24:
                break
        cleaned = []
        for value in values:
            value = (value or "").strip()
            if len(value) >= 2 and value not in cleaned:
                cleaned.append(value)
        return cleaned

    def _connect_article_to_wiki_graph(self, article, source=False, linked_items=False, source_text="", reset_existing=True, seed_plan=False):
        candidates = self._find_wiki_candidates(
            source=source,
            source_text=source_text,
            linked_items=linked_items,
            limit=12,
            exclude_article=article,
        )
        old_links = self._get_article_graph_links(article, source)
        agent_plan = kb_schema.normalize_graph_links(seed_plan) if seed_plan else self._run_wiki_graph_agent(article, candidates, old_links, source, linked_items, source_text)
        if reset_existing:
            self._archive_article_graph_links(article, source, reason="重新编译或修正资料后，由 Wiki Graph Agent 重新判断关联。")
        self._remove_graph_links_from_plan(agent_plan, article, source)
        if not candidates:
            article.write({"last_graph_checked_at": fields.Datetime.now()})
            self._create_source_citation(article, source, source_text)
            self._log_wiki_event(
                "link",
                f"Wiki 图谱检查：{article.name}",
                article=article,
                source=source,
                summary="未找到可自动关联的旧 Wiki，后续 lint 会标记为孤立候选。",
            )
            return {"links": 0}

        link_model = self.env["diecut.kb.wiki.link"].sudo()
        created = 0
        decisions = self._normalize_graph_agent_links(agent_plan, candidates)
        if not decisions and not agent_plan:
            decisions = []
            for target in candidates:
                link_type, confidence, reason = self._infer_wiki_link(article, target, source, linked_items)
                decisions.append(
                    {
                        "target": target,
                        "link_type": link_type,
                        "anchor_text": target.name,
                        "reason": reason,
                        "confidence": confidence,
                    }
                )
        # Asymmetric link types use a weaker reverse type
        _REVERSE_LINK_TYPE = {"depends_on": "mentions", "updates": "mentions"}

        for decision in decisions:
            target = decision["target"]
            link_type = decision["link_type"]
            reverse_type = _REVERSE_LINK_TYPE.get(link_type, link_type)
            confidence = decision["confidence"]
            reason = decision["reason"]
            anchor_text = decision.get("anchor_text") or target.name
            forward = link_model.create(
                {
                    "source_article_id": article.id,
                    "target_article_id": target.id,
                    "link_type": link_type,
                    "anchor_text": anchor_text,
                    "reason": reason,
                    "confidence": confidence,
                    "source_document_id": source.id if source else False,
                }
            )
            link_model.create(
                {
                    "source_article_id": target.id,
                    "target_article_id": article.id,
                    "link_type": reverse_type,
                    "anchor_text": article.name,
                    "reason": "反向链接：" + reason,
                    "confidence": confidence,
                    "source_document_id": source.id if source else False,
                }
            )
            if forward:
                created += 1
                self._log_wiki_event(
                    "link",
                    f"新增 Wiki 关联：{article.name} -> {target.name}",
                    article=article,
                    source=source,
                    link=forward[:1],
                    summary=reason,
                )

        if agent_plan.get("review_required"):
            article.write({"state": "review"})
        if agent_plan.get("notes"):
            self._log_wiki_event(
                "lint",
                f"Wiki Graph Agent 复核：{article.name}",
                article=article,
                source=source,
                summary="；".join(agent_plan.get("notes")[:5]),
                payload=agent_plan,
            )
        article.write(
            {
                "related_article_ids": [(6, 0, [decision["target"].id for decision in decisions])],
                "last_graph_checked_at": fields.Datetime.now(),
            }
        )
        self._create_source_citation(article, source, source_text)
        return {"links": created}

    def _get_article_graph_links(self, article, source=False):
        domain = [
            "|",
            ("source_article_id", "=", article.id),
            ("target_article_id", "=", article.id),
            ("active", "=", True),
        ]
        if source:
            domain.append(("source_document_id", "=", source.id))
        return self.env["diecut.kb.wiki.link"].sudo().search(domain)

    def _archive_article_graph_links(self, article, source=False, reason=""):
        links = self._get_article_graph_links(article, source)
        if not links:
            return 0
        suffix = reason or "Wiki 图谱重新生成，旧关联已归档。"
        for link in links:
            link.write(
                {
                    "active": False,
                    "reason": ((link.reason or "").strip() + "\n\n[归档] " + suffix).strip(),
                }
            )
        self._log_wiki_event(
            "link",
            f"归档旧 Wiki 关联：{article.name}",
            article=article,
            source=source,
            summary=f"归档 {len(links)} 条旧关联，等待 Graph Agent 按最新资料重建。",
        )
        return len(links)

    def _remove_graph_links_from_plan(self, plan, article, source=False):
        remove_ids = (plan or {}).get("remove_link_ids") or []
        if not remove_ids:
            return 0
        links = self.env["diecut.kb.wiki.link"].sudo().browse(remove_ids).exists()
        if not links:
            return 0
        allowed = links.filtered(
            lambda link: link.source_article_id == article or link.target_article_id == article
        )
        if source:
            allowed = allowed.filtered(lambda link: not link.source_document_id or link.source_document_id == source)
        for link in allowed:
            link.write(
                {
                    "active": False,
                    "reason": ((link.reason or "").strip() + "\n\n[移除] LLM Schema 判断该关系不再成立。").strip(),
                }
            )
        if allowed:
            self._log_wiki_event(
                "link",
                f"移除污染 Wiki 关联：{article.name}",
                article=article,
                source=source,
                summary=f"按 Graph Patch 移除 {len(allowed)} 条旧关联。",
                payload={"remove_link_ids": allowed.ids},
            )
        return len(allowed)

    def _run_wiki_graph_agent(self, article, candidates, old_links, source=False, linked_items=False, source_text=""):
        if not candidates:
            return {}
        client = self._build_client()
        if not client:
            return {}
        payload = {
            "current_article": {
                "id": article.id,
                "title": article.name,
                "wiki_page_type": article.wiki_page_type or "",
                "summary": article.summary or "",
                "keywords": article.keywords or "",
                "brands": article.related_brand_ids.mapped("name"),
                "items": article.related_item_ids.mapped("code"),
                "categories": article.related_categ_ids.mapped("complete_name"),
                "content_excerpt": (article.content_text or article.content_md or "")[:3000],
            },
            "source": {
                "id": source.id if source else False,
                "title": source.name if source else "",
                "brand": source.brand_id.name if source and source.brand_id else "",
                "category": source.categ_id.complete_name if source and source.categ_id else "",
                "filename": source.primary_attachment_name if source else "",
                "text_excerpt": (source_text or "")[:5000],
            },
            "linked_items": [
                {
                    "id": item.id,
                    "code": item.code or "",
                    "name": item.name or "",
                    "brand": item.brand_id.name if item.brand_id else "",
                    "category": item.categ_id.complete_name if item.categ_id else "",
                }
                for item in (linked_items or self.env["diecut.catalog.item"].browse())[:12]
            ],
            "old_links": [
                {
                    "id": link.id,
                    "source_id": link.source_article_id.id,
                    "source_title": link.source_article_id.name,
                    "target_id": link.target_article_id.id,
                    "target_title": link.target_article_id.name,
                    "link_type": link.link_type,
                    "reason": link.reason or "",
                    "confidence": link.confidence,
                }
                for link in old_links
            ],
            "candidate_pages": [
                {
                    "id": candidate.id,
                    "title": candidate.name,
                    "wiki_page_type": candidate.wiki_page_type or "",
                    "summary": candidate.summary or "",
                    "keywords": candidate.keywords or "",
                    "brands": candidate.related_brand_ids.mapped("name"),
                    "items": candidate.related_item_ids.mapped("code"),
                    "categories": candidate.related_categ_ids.mapped("complete_name"),
                    "content_excerpt": (candidate.content_text or candidate.content_md or "")[:1000],
                }
                for candidate in candidates
            ],
        }
        ok, response, error, duration = client.chat_messages(
            query="请根据以下 JSON 维护 Wiki 图谱关联：\n\n%s" % json.dumps(payload, ensure_ascii=False, indent=2),
            user=f"kb-graph-agent-{self.env.user.id}",
            inputs={"system": self._system_prompt("wiki_graph_patch", _DEFAULT_PROMPT_WIKI_GRAPH_AGENT)},
        )
        if not ok:
            self._log_wiki_event(
                "lint",
                f"Wiki Graph Agent 调用失败：{article.name}",
                article=article,
                source=source,
                summary=f"Graph Agent 调用失败，已退回规则型建图：{error}",
                payload={"error": error, "duration_ms": duration},
            )
            return {}
        answer = self._clean_answer((response or {}).get("answer", ""))
        plan = kb_schema.normalize_graph_links(kb_schema.extract_json_object(answer))
        if not plan:
            self._log_wiki_event(
                "lint",
                f"Wiki Graph Agent 输出无效：{article.name}",
                article=article,
                source=source,
                summary="Graph Agent 未返回有效 JSON，已退回规则型建图。",
                details=answer[:2000],
            )
            return {}
        return plan

    def _normalize_graph_agent_links(self, plan, candidates):
        if not plan:
            return []
        allowed_types = {
            "mentions",
            "same_brand",
            "same_material",
            "same_application",
            "same_process",
            "compares_with",
            "depends_on",
            "contradicts",
            "updates",
        }
        candidate_by_id = {candidate.id: candidate for candidate in candidates}
        decisions = []
        for row in plan.get("links") or []:
            target = candidate_by_id.get(row.get("target_id"))
            if not target:
                continue
            link_type = row.get("link_type") if row.get("link_type") in allowed_types else "mentions"
            try:
                confidence = float(row.get("confidence", 0.6))
            except Exception:
                confidence = 0.6
            confidence = max(0.0, min(1.0, confidence))
            reason = (row.get("reason") or "Graph Agent 判断该页面应接入当前 Wiki 图谱。").strip()
            decisions.append(
                {
                    "target": target,
                    "link_type": link_type,
                    "anchor_text": (row.get("anchor_text") or target.name or "").strip(),
                    "reason": reason,
                    "confidence": confidence,
                }
            )
        return decisions

    def _infer_wiki_link(self, article, target, source=False, linked_items=False):
        if linked_items and set(article.related_item_ids.ids) & set(target.related_item_ids.ids):
            return "compares_with", 0.85, "页面关联到相同材料型号，适合互相对照。"
        if set(article.related_brand_ids.ids) & set(target.related_brand_ids.ids):
            return "same_brand", 0.8, "页面关联到相同品牌，属于同一品牌知识网络。"
        if set(article.related_categ_ids.ids) & set(target.related_categ_ids.ids):
            return "same_material", 0.75, "页面关联到相同材料类别，适合形成材料体系关联。"
        if article.wiki_page_type == target.wiki_page_type == "application":
            return "same_application", 0.65, "页面同属应用场景知识，可作为应用选型关联。"
        if article.wiki_page_type == target.wiki_page_type == "process":
            return "same_process", 0.65, "页面同属工艺经验知识，可作为问题排查关联。"
        if source and target.compile_source_document_id and source.id != target.compile_source_document_id.id:
            return "mentions", 0.55, "新资料与旧 Wiki 在标题、关键词或正文摘要上相似，先建立弱关联供人工复核。"
        return "mentions", 0.5, "通过关键词相似度发现的候选旧 Wiki，先建立弱关联。"

    def _create_source_citation(self, article, source=False, source_text=""):
        if not source:
            return
        existing = self.env["diecut.kb.citation"].sudo().search(
            [
                ("article_id", "=", article.id),
                ("source_document_id", "=", source.id),
            ],
            limit=1,
        )
        if existing:
            return
        excerpt = (source_text or "").strip()[:800]
        claim = article.summary or self._html_to_summary(article.content_html or "") or article.name
        if not claim:
            return
        self.env["diecut.kb.citation"].sudo().create(
            {
                "article_id": article.id,
                "source_document_id": source.id,
                "source_attachment_id": source.primary_attachment_id.id if source.primary_attachment_id else False,
                "claim_text": claim,
                "page_ref": self._source_page_refs(source),
                "excerpt": excerpt,
                "confidence": article.compile_confidence or 0.6,
                "state": "valid" if self._source_page_refs(source) else "review",
            }
        )

    def _apply_wiki_patch_citations(self, article, source, wiki_patch):
        rows = (wiki_patch or {}).get("citations") or []
        if not rows:
            return 0
        citation_model = self.env["diecut.kb.citation"].sudo()
        created = 0
        for row in rows:
            claim = (row.get("claim_text") or "").strip()
            if not claim:
                continue
            source_id = row.get("source_document_id") or (source.id if source else False)
            page_ref = row.get("page_ref") or ""
            existing = citation_model.search(
                [
                    ("article_id", "=", article.id),
                    ("source_document_id", "=", source_id),
                    ("claim_text", "=", claim[:1024]),
                ],
                limit=1,
            )
            vals = {
                "article_id": article.id,
                "source_document_id": source_id,
                "source_attachment_id": source.primary_attachment_id.id if source and source.primary_attachment_id else False,
                "claim_text": claim[:1024],
                "page_ref": page_ref,
                "excerpt": (row.get("excerpt") or "")[:2000],
                "confidence": row.get("confidence") or 0.6,
                "state": row.get("state") or "review",
            }
            if existing:
                existing.write(vals)
            else:
                citation_model.create(vals)
                created += 1
        if created:
            self._log_wiki_event(
                "compile",
                f"写入 Wiki 来源引用：{article.name}",
                article=article,
                source=source,
                summary=f"根据 Wiki Patch 写入 {created} 条来源引用。",
            )
        return created

    def _log_wiki_event(self, event_type, name, article=False, source=False, link=False, summary="", details="", payload=None):
        try:
            self.env["diecut.kb.wiki.log"].sudo().create(
                {
                    "event_type": event_type,
                    "name": name[:200],
                    "article_id": article.id if article else False,
                    "source_document_id": source.id if source else False,
                    "link_id": link.id if link else False,
                    "summary": summary,
                    "details": details,
                    "payload_json": json.dumps(payload or {}, ensure_ascii=False, indent=2) if payload else False,
                }
            )
        except Exception as exc:
            _logger.warning("Failed to write wiki log: %s", exc)
