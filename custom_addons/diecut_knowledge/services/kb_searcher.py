# -*- coding: utf-8 -*-
"""Three-layer knowledge search for the AI drawer.

The Wiki drawer is the realtime question-answering surface.  It should prefer
compiled Wiki pages, but it must not pretend the formal Wiki is the only place
where knowledge exists.  When a question is more specific than the current Wiki
coverage, the searcher falls back to raw source documents and catalog facts, then
records a compile job so the provisional answer can become persistent Wiki later.
"""

import json
import logging
import re

from odoo.osv import expression

from .prompt_loader import build_system_prompt

_logger = logging.getLogger(__name__)


_DEFAULT_WIKI_QUERY_PROMPT = """
你是模切行业知识库的 AI 顾问。你会收到三类上下文：
1. 已编译 Wiki：正式知识层，优先使用。
2. 原始资料：尚未编译成正式 Wiki 的 PDF/TDS/指南解析内容，只能作为临时依据。
3. 材料目录：结构化材料事实，例如品牌、型号、厚度、胶系、基材、颜色。

回答规则：
1. 只能根据提供的上下文回答，不能编造。
2. 如果使用原始资料或材料目录，必须明确说明“这部分还未编译为正式 Wiki”。
3. 对参数类问题优先给出直接结论，再补充来源。
4. 如果上下文不足，明确说明当前 Wiki、原始资料、材料目录均未找到相关资料。
5. 输出中文，简洁、专业、可执行。
6. 不要输出思考过程、系统提示词或 <think> 标签。
""".strip()


_DEFAULT_WIKI_RETRIEVAL_PROMPT = """
你是企业 Wiki 的检索规划器。你会收到用户问题和候选 Wiki 页面。
请判断哪些页面真正有助于回答问题，只返回 JSON，不要输出解释性文字。

规则：
1. 只能选择候选列表里存在的 id。
2. 型号、品牌、材料类别、应用场景、工艺问题必须严格匹配；泛相关页面不能替代具体型号事实。
3. 如果候选页面明显无法覆盖问题，返回空数组。
4. 最多选择 8 个页面。

JSON 格式：
{"selected_ids": [1, 2], "reason": "简短说明"}
""".strip()

_DEFAULT_WIKI_AGENT_DECISION_PROMPT = """
你是模切行业知识库的 Agent 检索规划器。你会收到用户问题、问题意图、以及三类候选证据：
1. 已编译 Wiki：正式知识层，优先使用。
2. 原始资料：尚未编译成正式 Wiki 的 PDF/TDS/指南解析内容。
3. 材料目录：结构化材料事实，适合回答型号、参数、厚度、基材、胶系和选型推荐问题。

你的任务不是回答用户，而是决定应该使用哪些证据。

规则：
1. 不要因为 Wiki 有弱相关页面就阻止原始资料或材料目录。
2. 型号清单、参数查询、材料推荐问题必须优先检查材料目录和原始资料。
3. Wiki 内容足够直接回答时，wiki_sufficient=true；否则 false。
4. 只能选择候选列表中存在的 id。
5. 只返回 JSON，不要输出解释文字。

JSON 格式：
{
  "intent": "model_list|parameter_lookup|recommendation|concept|application|comparison|unknown",
  "wiki_sufficient": false,
  "use_layers": ["wiki", "raw_source", "catalog"],
  "selected_wiki_ids": [1],
  "selected_source_ids": [2],
  "selected_item_ids": [3],
  "answer_strategy": "direct_fact|recommendation|insufficient",
  "compile_gap_required": true,
  "reason": "简短说明"
}
""".strip()


class KbSearcher:
    """Structured query engine shared by the Wiki drawer."""

    _QUESTION_WORDS = {
        "是什么", "是多少", "什么", "多少", "多厚", "厚度", "原理", "用途", "作用",
        "怎么", "如何", "为什么", "请问", "一个", "资料", "相关", "有没有",
        "主要", "哪些", "哪种", "哪款", "适合", "推荐", "列出",
    }
    _DOMAIN_TERMS = (
        "双面胶", "单面胶", "胶带", "胶", "厚度", "基材", "胶系", "颜色", "用途",
        "选型", "材料", "模切", "陶瓷", "吸盘", "多孔陶瓷", "多孔陶瓷吸盘",
        "真空", "治具", "加工", "应用", "耐温", "防水", "防锈", "导热", "绝缘",
        "pet", "pp", "pe", "pc", "pi", "泡棉", "离型膜", "保护膜", "3m", "tesa", "日东",
        "低表面能", "lse", "高表面能", "hse", "丙烯酸", "硅胶", "橡胶",
    )
    _CATALOG_CONTEXT_FIELDS = (
        ("name", "名称"),
        ("code", "型号"),
        ("brand_id", "品牌"),
        ("series_id", "系列"),
        ("categ_id", "分类"),
        ("thickness", "厚度"),
        ("thickness_std", "厚度标准"),
        ("adhesive_thickness", "胶层厚"),
        ("color_id", "颜色"),
        ("adhesive_type_id", "胶系"),
        ("base_material_id", "基材"),
        ("fire_rating", "防火等级"),
        ("is_rohs", "ROHS"),
        ("is_reach", "REACH"),
        ("is_halogen_free", "无卤"),
        ("product_features", "特性"),
        ("product_description", "说明"),
        ("main_applications", "主要应用"),
        ("special_applications", "补充说明"),
        ("selection_search_text", "选型检索文本"),
    )

    def __init__(self, env, model_profile_id=False):
        self.env = env
        self.model_profile_id = model_profile_id or env.context.get("llm_model_profile_id")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze_query(self, query_text):
        """Return a deterministic first-pass intent analysis for retrieval."""
        text = (query_text or "").strip()
        lowered = text.lower()
        terms = self._extract_query_terms(text)
        alnum_terms = [
            term for term in terms
            if re.search(r"[A-Za-z0-9]", term) and len(re.sub(r"[^A-Za-z0-9]", "", term)) >= 2
        ]

        if any(word in text for word in ("推荐", "适合", "选型", "用哪", "哪种", "哪款", "有没有")):
            intent = "recommendation"
        elif any(word in text for word in ("哪些型号", "型号", "清单", "列表", "主要有哪些", "有哪些")):
            intent = "model_list"
        elif any(word in text for word in ("厚度", "多厚", "多少", "参数", "规格", "基材", "胶系", "颜色")):
            intent = "parameter_lookup"
        elif any(word in text for word in ("对比", "区别", "差异", "替代")):
            intent = "comparison"
        elif any(word in text for word in ("用途", "应用", "场景")):
            intent = "application"
        elif any(word in text for word in ("是什么", "原理", "为什么", "作用")):
            intent = "concept"
        else:
            intent = "unknown"

        return {
            "intent": intent,
            "terms": terms,
            "alnum_terms": alnum_terms,
            "asks_catalog_facts": intent in ("model_list", "parameter_lookup", "recommendation", "comparison"),
            "mentions_material": any(term.lower() in lowered for term in ("pp", "pe", "pet", "pc", "pi", "泡棉", "双面胶", "胶带", "低表面能", "lse")),
        }

    def query(self, query_text, user_id=None):
        client = self._build_dify_client()
        if not client:
            return {
                "ok": False,
                "error": "Dify 未配置，无法完成 Wiki 查询。",
                "articles": [],
                "source_layer": "none",
            }

        plan = self._build_retrieval_plan(query_text, client=client)
        if plan["source_layer"] == "none":
            return {
                "ok": True,
                "answer": self._no_context_answer(query_text),
                "articles": [],
                "source_refs": [],
                "source_layer": "none",
            }

        answer, error, duration = self._answer_with_client(client, query_text, plan, user_id=user_id)
        if error:
            return {
                "ok": False,
                "error": error,
                "articles": self._article_refs(plan["articles"]),
                "source_refs": plan["source_refs"],
                "source_layer": plan["source_layer"],
                "compile_job_id": plan.get("compile_job_id"),
            }

        answer = self._mark_provisional_answer(answer, plan)
        if not answer:
            answer = self._fallback_answer_from_context(plan)

        return {
            "ok": True,
            "answer": answer or "未收到 AI 回复，请稍后重试。",
            "articles": self._article_refs(plan["articles"]),
            "source_refs": plan["source_refs"],
            "source_layer": plan["source_layer"],
            "compile_job_id": plan.get("compile_job_id"),
            "duration_ms": duration,
        }

    def query_stream(self, query_text, user_id=None):
        client = self._build_dify_client()
        if not client:
            yield ("done", {
                "full_answer": "Dify 未配置，无法完成 Wiki 查询。",
                "articles": [],
                "source_refs": [],
                "source_layer": "none",
            }, None)
            return

        plan = self._build_retrieval_plan(query_text, client=client)
        if plan["source_layer"] == "none":
            yield ("done", {
                "full_answer": self._no_context_answer(query_text),
                "articles": [],
                "source_refs": [],
                "source_layer": "none",
            }, None)
            return

        full_answer = ""
        article_refs = self._article_refs(plan["articles"])
        source_refs = plan["source_refs"]
        prompt = self._build_answer_prompt(query_text, plan)
        user_name = user_id or "Wiki Searcher"
        prefix = self._provisional_prefix(plan)
        if prefix:
            full_answer += prefix
            yield ("token", {"token": prefix, "full_answer": full_answer}, None)

        for event_type, data, error in client.chat_messages_stream(
            query=prompt,
            user=user_name,
            inputs={"system": build_system_prompt("ai_advisor_qa", _DEFAULT_WIKI_QUERY_PROMPT)},
        ):
            if event_type == "token":
                token = data.get("token", "")
                full_answer += token
                yield ("token", {"token": token, "full_answer": full_answer}, None)
            elif event_type == "done":
                final_answer = self._clean_answer(data.get("full_answer") or full_answer)
                final_answer = self._mark_provisional_answer(final_answer, plan)
                yield ("done", {
                    "full_answer": final_answer or self._fallback_answer_from_context(plan) or "未收到 AI 回复，请稍后重试。",
                    "articles": article_refs,
                    "source_refs": source_refs,
                    "source_layer": plan["source_layer"],
                    "compile_job_id": plan.get("compile_job_id"),
                }, None)
                return
            elif event_type == "error":
                _logger.warning("Wiki stream failed: %s", error)
                yield ("done", {
                    "full_answer": full_answer or self._fallback_answer_from_context(plan) or "查询失败，请稍后重试。",
                    "articles": article_refs,
                    "source_refs": source_refs,
                    "source_layer": plan["source_layer"],
                    "compile_job_id": plan.get("compile_job_id"),
                }, None)
                return

    # ------------------------------------------------------------------
    # Retrieval plan
    # ------------------------------------------------------------------

    def _build_retrieval_plan(self, query_text, client=None):
        analysis = self.analyze_query(query_text)
        wiki_candidates = self._search_articles(query_text, limit=30)
        raw_candidates = self._search_raw_sources(query_text, limit=8)
        catalog_candidates = self._search_catalog_items(query_text, limit=12)

        wiki_articles = self._select_articles_with_llm(query_text, wiki_candidates, client=client, limit=8)
        decision = self._agent_decide_context(
            query_text=query_text,
            analysis=analysis,
            wiki_candidates=wiki_articles or wiki_candidates[:8],
            raw_candidates=raw_candidates,
            catalog_candidates=catalog_candidates,
            client=client,
        )

        articles = self._records_from_decision(
            self.env["diecut.kb.article"],
            decision.get("selected_wiki_ids"),
            wiki_articles or wiki_candidates,
            limit=8,
        )
        raw_sources = self._records_from_decision(
            self.env["diecut.catalog.source.document"],
            decision.get("selected_source_ids"),
            raw_candidates,
            limit=6,
        )
        catalog_items = self._records_from_decision(
            self.env["diecut.catalog.item"],
            decision.get("selected_item_ids"),
            catalog_candidates,
            limit=10,
        )

        source_layer = self._source_layer(articles, raw_sources, catalog_items)
        if source_layer == "none":
            return {
                "source_layer": "none",
                "articles": articles,
                "raw_sources": raw_sources,
                "catalog_items": catalog_items,
                "source_refs": [],
                "compile_job_id": False,
                "analysis": analysis,
                "agent_decision": decision,
            }

        compile_job_id = False
        if raw_sources or catalog_items or decision.get("compile_gap_required"):
            compile_job_id = self._ensure_compile_gap_job(
                source_layer=source_layer,
                query_text=query_text,
                raw_sources=raw_sources,
                catalog_items=catalog_items,
            )
        return {
            "source_layer": source_layer,
            "articles": articles,
            "raw_sources": raw_sources,
            "catalog_items": catalog_items,
            "source_refs": self._source_refs(articles=articles, raw_sources=raw_sources, catalog_items=catalog_items),
            "compile_job_id": compile_job_id,
            "analysis": analysis,
            "agent_decision": decision,
        }

    def _agent_decide_context(self, query_text, analysis, wiki_candidates, raw_candidates, catalog_candidates, client=None):
        if not client:
            return self._fallback_agent_decision(analysis, wiki_candidates, raw_candidates, catalog_candidates)

        payload = {
            "query": query_text or "",
            "analysis": {
                "intent": analysis.get("intent"),
                "terms": analysis.get("terms", [])[:20],
                "asks_catalog_facts": analysis.get("asks_catalog_facts"),
                "mentions_material": analysis.get("mentions_material"),
            },
            "wiki_candidates": self._agent_wiki_payload(wiki_candidates),
            "raw_source_candidates": self._agent_raw_payload(raw_candidates),
            "catalog_candidates": self._agent_catalog_payload(catalog_candidates),
        }
        ok, response, error, _duration = client.chat_messages(
            query=(
                "请根据下列候选证据制定检索决策，只输出 JSON。\n\n%s"
                % json.dumps(payload, ensure_ascii=False)
            ),
            user="wiki-agent-retriever",
            inputs={"system": build_system_prompt("wiki_agent_decision", _DEFAULT_WIKI_AGENT_DECISION_PROMPT)},
        )
        if not ok:
            _logger.warning("LLM Wiki agent decision failed: %s", error)
            return self._fallback_agent_decision(analysis, wiki_candidates, raw_candidates, catalog_candidates)

        decision = self._parse_agent_decision(self._extract_dify_answer(response))
        if not decision:
            return self._fallback_agent_decision(analysis, wiki_candidates, raw_candidates, catalog_candidates)
        return self._sanitize_agent_decision(decision, analysis, wiki_candidates, raw_candidates, catalog_candidates)

    def _fallback_agent_decision(self, analysis, wiki_candidates, raw_candidates, catalog_candidates):
        intent = analysis.get("intent") or "unknown"
        wiki_ids = list(wiki_candidates[:6].ids)
        source_ids = list(raw_candidates[:4].ids)
        item_ids = list(catalog_candidates[:8].ids)

        if analysis.get("asks_catalog_facts"):
            use_layers = []
            if wiki_ids:
                use_layers.append("wiki")
            if source_ids:
                use_layers.append("raw_source")
            if item_ids:
                use_layers.append("catalog")
            return {
                "intent": intent,
                "wiki_sufficient": False,
                "use_layers": use_layers,
                "selected_wiki_ids": wiki_ids[:4] if use_layers else [],
                "selected_source_ids": source_ids,
                "selected_item_ids": item_ids,
                "answer_strategy": "recommendation" if intent == "recommendation" else "direct_fact",
                "compile_gap_required": bool(source_ids or item_ids),
                "reason": "材料事实类问题，不能只依赖 Wiki 弱命中。",
            }

        if wiki_ids:
            return {
                "intent": intent,
                "wiki_sufficient": True,
                "use_layers": ["wiki"],
                "selected_wiki_ids": wiki_ids[:6],
                "selected_source_ids": [],
                "selected_item_ids": [],
                "answer_strategy": "direct_fact",
                "compile_gap_required": False,
                "reason": "Wiki 候选足以作为优先上下文。",
            }

        use_layers = []
        if source_ids:
            use_layers.append("raw_source")
        if item_ids:
            use_layers.append("catalog")
        return {
            "intent": intent,
            "wiki_sufficient": False,
            "use_layers": use_layers,
            "selected_wiki_ids": [],
            "selected_source_ids": source_ids,
            "selected_item_ids": item_ids,
            "answer_strategy": "direct_fact" if use_layers else "insufficient",
            "compile_gap_required": bool(use_layers),
            "reason": "Wiki 未命中，使用可追溯的临时依据。" if use_layers else "三层候选均未命中。",
        }

    def _sanitize_agent_decision(self, decision, analysis, wiki_candidates, raw_candidates, catalog_candidates):
        fallback = self._fallback_agent_decision(analysis, wiki_candidates, raw_candidates, catalog_candidates)
        candidate_wiki_ids = set(wiki_candidates.ids)
        candidate_source_ids = set(raw_candidates.ids)
        candidate_item_ids = set(catalog_candidates.ids)

        def clean_ids(key, allowed, fallback_ids, limit):
            values = decision.get(key)
            if not isinstance(values, list):
                values = fallback_ids
            clean = []
            for value in values:
                try:
                    value = int(value)
                except Exception:
                    continue
                if value in allowed and value not in clean:
                    clean.append(value)
                if len(clean) >= limit:
                    break
            return clean

        wiki_ids = clean_ids("selected_wiki_ids", candidate_wiki_ids, fallback.get("selected_wiki_ids", []), 8)
        source_ids = clean_ids("selected_source_ids", candidate_source_ids, fallback.get("selected_source_ids", []), 6)
        item_ids = clean_ids("selected_item_ids", candidate_item_ids, fallback.get("selected_item_ids", []), 10)

        if analysis.get("asks_catalog_facts") and (catalog_candidates or raw_candidates):
            if catalog_candidates and not item_ids:
                item_ids = list(catalog_candidates[:8].ids)
            if raw_candidates and not source_ids:
                source_ids = list(raw_candidates[:4].ids)

        allowed_intents = {"model_list", "parameter_lookup", "recommendation", "concept", "application", "comparison", "unknown"}
        intent = decision.get("intent") if decision.get("intent") in allowed_intents else fallback["intent"]
        use_layers = []
        if wiki_ids:
            use_layers.append("wiki")
        if source_ids:
            use_layers.append("raw_source")
        if item_ids:
            use_layers.append("catalog")
        return {
            "intent": intent,
            "wiki_sufficient": bool(decision.get("wiki_sufficient")) and not (source_ids or item_ids),
            "use_layers": use_layers,
            "selected_wiki_ids": wiki_ids,
            "selected_source_ids": source_ids,
            "selected_item_ids": item_ids,
            "answer_strategy": decision.get("answer_strategy") or fallback["answer_strategy"],
            "compile_gap_required": bool(decision.get("compile_gap_required")) or bool(source_ids or item_ids),
            "reason": decision.get("reason") or fallback["reason"],
        }

    def _parse_agent_decision(self, answer):
        if not answer:
            return {}
        text = self._clean_answer(answer)
        text = re.sub(r"```(?:json)?", "", text, flags=re.I).replace("```", "").strip()
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start:end + 1]
        try:
            payload = json.loads(text)
        except Exception:
            _logger.info("Unable to parse Wiki agent decision JSON: %s", answer[:500])
            return {}
        return payload if isinstance(payload, dict) else {}

    def _records_from_decision(self, model, selected_ids, fallback_records, limit):
        selected_ids = selected_ids or []
        if selected_ids:
            records = model.browse(selected_ids).exists()
            if records:
                return records[:limit]
        return fallback_records[:limit] if fallback_records else model.browse()

    @staticmethod
    def _source_layer(articles, raw_sources, catalog_items):
        layers = []
        if articles:
            layers.append("wiki")
        if raw_sources:
            layers.append("raw_source")
        if catalog_items:
            layers.append("catalog")
        if not layers:
            return "none"
        if layers == ["wiki"]:
            return "wiki"
        if layers == ["raw_source"]:
            return "raw_source"
        if layers == ["catalog"]:
            return "catalog"
        return "mixed"

    def _wiki_covers_query(self, query_text, articles):
        """Avoid using generic Wiki pages for specific model-number questions."""
        if not articles:
            return False
        specific_terms = [
            term.lower()
            for term in self._extract_query_terms(query_text)
            if re.search(r"\d", term) and len(re.sub(r"[^A-Za-z0-9]", "", term)) >= 3
        ]
        if not specific_terms:
            return True
        combined_parts = []
        for article in articles:
            combined_parts.extend(filter(None, [
                article.name,
                getattr(article, "wiki_slug", ""),
                article.summary,
                article.keywords,
                (article.content_md or article.content_text or "")[:12000],
            ]))
        combined = "\n".join(combined_parts).lower()
        return any(term in combined or re.sub(r"[^a-z0-9]", "", term) in combined for term in specific_terms)

    # ------------------------------------------------------------------
    # Wiki retrieval
    # ------------------------------------------------------------------

    def _search_articles(self, query_text, limit=8):
        query_text = (query_text or "").strip()
        if not query_text:
            return self.env["diecut.kb.article"].browse()

        terms = self._extract_query_terms(query_text)
        Article = self.env["diecut.kb.article"]
        fields_to_search = ("name", "wiki_slug", "summary", "keywords", "content_text", "content_md")
        conditions = []
        for term in terms[:18]:
            for field_name in fields_to_search:
                if self._can_sql_search(Article, field_name):
                    conditions.append((field_name, "ilike", term))
        if not conditions:
            return Article.browse()

        domain = [("state", "in", ("published", "review"))] + self._or_domain(conditions)
        candidates = Article.search(domain, limit=max(limit * 4, 40))
        return self._score_records(candidates, terms, self._score_article, limit)

    def _select_articles_with_llm(self, query_text, candidates, client=None, limit=8):
        if not candidates:
            return candidates
        if not client:
            return candidates[:limit]

        candidate_payload = []
        for article in candidates[:20]:
            content = article.content_md or article.content_text or ""
            candidate_payload.append({
                "id": article.id,
                "title": article.name or "",
                "type": article.wiki_page_type or "wiki",
                "summary": article.summary or "",
                "keywords": article.keywords or "",
                "snippet": content[:800],
                "outbound_links": [
                    link.target_article_id.name
                    for link in article.outbound_link_ids.filtered(lambda link: link.active)[:5]
                ],
                "inbound_links": [
                    link.source_article_id.name
                    for link in article.inbound_link_ids.filtered(lambda link: link.active)[:5]
                ],
            })

        ok, payload, error, _duration = client.chat_messages(
            query=(
                "请从候选 Wiki 页面中选择真正能回答问题的页面，只输出 JSON。\n\n"
                "用户问题：%s\n\n候选页面：\n%s"
            ) % (query_text, json.dumps(candidate_payload, ensure_ascii=False)),
            user="wiki-retriever",
            inputs={"system": build_system_prompt("wiki_retrieval", _DEFAULT_WIKI_RETRIEVAL_PROMPT)},
        )
        if not ok:
            _logger.warning("LLM Wiki retrieval selection failed: %s", error)
            return candidates[:limit]

        selected_ids = self._parse_selected_ids(self._extract_dify_answer(payload))
        if selected_ids is None:
            return candidates[:limit]
        if not selected_ids:
            return self.env["diecut.kb.article"].browse()

        candidate_ids = set(candidates.ids)
        ordered_ids = []
        for selected_id in selected_ids:
            if selected_id in candidate_ids and selected_id not in ordered_ids:
                ordered_ids.append(selected_id)
            if len(ordered_ids) >= limit:
                break
        return self.env["diecut.kb.article"].browse(ordered_ids)

    # ------------------------------------------------------------------
    # Raw source and catalog fallback
    # ------------------------------------------------------------------

    def _agent_wiki_payload(self, articles):
        payload = []
        for article in articles[:12]:
            content = article.content_md or article.content_text or ""
            payload.append({
                "id": article.id,
                "title": article.name or "",
                "type": article.wiki_page_type or "wiki",
                "summary": article.summary or "",
                "keywords": article.keywords or "",
                "graph_degree": getattr(article, "graph_degree", 0) or 0,
                "snippet": self._clip(content, 700),
            })
        return payload

    def _agent_raw_payload(self, sources):
        payload = []
        for source in sources[:10]:
            text = " ".join(filter(None, [
                getattr(source, "knowledge_parsed_text", "") or "",
                getattr(source, "knowledge_parsed_markdown", "") or "",
                getattr(source, "raw_text", "") or "",
                getattr(source, "result_message", "") or "",
                getattr(source, "draft_payload", "") or "",
            ]))
            payload.append({
                "id": source.id,
                "title": source.name or source.display_name,
                "filename": getattr(source, "primary_attachment_name", False) or getattr(source, "source_filename", False) or "",
                "kind": getattr(source, "knowledge_source_kind", False) or getattr(source, "source_type", False) or "",
                "brand": self._record_value(source, "brand_id"),
                "category": self._record_value(source, "categ_id"),
                "snippet": self._clip(text, 900),
            })
        return payload

    def _agent_catalog_payload(self, items):
        payload = []
        for item in items[:16]:
            spec_lines = []
            for spec in getattr(item, "spec_line_ids", self.env["diecut.catalog.item.spec.line"])[:6]:
                spec_text = " ".join(filter(None, [
                    spec.param_name or "",
                    getattr(spec, "value_display", False) or getattr(spec, "value_raw", False) or "",
                    getattr(spec, "unit", False) or getattr(spec, "uom", False) or "",
                    getattr(spec, "condition_summary", False) or getattr(spec, "test_condition", False) or "",
                ])).strip()
                if spec_text:
                    spec_lines.append(spec_text)
            payload.append({
                "id": item.id,
                "code": item.code or "",
                "name": item.name or "",
                "brand": self._record_value(item, "brand_id"),
                "series": self._record_value(item, "series_id"),
                "category": self._record_value(item, "categ_id"),
                "thickness": item.thickness or "",
                "thickness_std": item.thickness_std or "",
                "adhesive": self._record_value(item, "adhesive_type_id"),
                "base_material": self._record_value(item, "base_material_id"),
                "color": self._record_value(item, "color_id"),
                "applications": self._clip(" ".join(filter(None, [
                    item.selection_search_text or "",
                    item.product_features or "",
                    item.product_description or "",
                    item.main_applications or "",
                    item.special_applications or "",
                ])), 800),
                "specs": spec_lines,
            })
        return payload

    def _search_raw_sources(self, query_text, limit=6):
        Source = self.env["diecut.catalog.source.document"]
        terms = self._extract_query_terms(query_text)
        if not terms:
            return Source.browse()

        fields_to_search = (
            "name",
            "source_filename",
            "primary_attachment_name",
            "raw_text",
            "knowledge_parsed_text",
            "knowledge_parsed_markdown",
            "result_message",
            "draft_payload",
        )
        conditions = []
        for term in terms[:16]:
            for field_name in fields_to_search:
                if self._can_sql_search(Source, field_name):
                    conditions.append((field_name, "ilike", term))
            if "brand_id" in Source._fields:
                conditions.append(("brand_id.name", "ilike", term))
            if "categ_id" in Source._fields:
                conditions.append(("categ_id.name", "ilike", term))
        if not conditions:
            return Source.browse()

        domain = self._or_domain(conditions)
        if "active" in Source._fields:
            domain = [("active", "=", True)] + domain
        candidates = Source.search(domain, limit=max(limit * 5, 50))
        return self._score_records(candidates, terms, self._score_raw_source, limit)

    def _search_catalog_items(self, query_text, limit=8):
        Item = self.env["diecut.catalog.item"]
        terms = self._extract_query_terms(query_text)
        if not terms:
            return Item.browse()

        conditions = []
        fields_to_search = (
            "name",
            "code",
            "selection_search_text",
            "thickness",
            "thickness_std",
            "adhesive_thickness",
            "fire_rating",
            "product_features",
            "product_description",
            "main_applications",
            "special_applications",
        )
        for term in terms[:16]:
            for field_name in fields_to_search:
                if self._can_sql_search(Item, field_name):
                    conditions.append((field_name, "ilike", term))
            for relation in ("brand_id", "series_id", "categ_id", "color_id", "adhesive_type_id", "base_material_id"):
                if relation in Item._fields:
                    conditions.append((f"{relation}.name", "ilike", term))
            if "spec_line_ids" in Item._fields:
                conditions.extend([
                    ("spec_line_ids.param_name", "ilike", term),
                    ("spec_line_ids.value_raw", "ilike", term),
                    ("spec_line_ids.value_display", "ilike", term),
                    ("spec_line_ids.test_condition", "ilike", term),
                    ("spec_line_ids.remark", "ilike", term),
                ])
        if not conditions:
            return Item.browse()

        domain = self._or_domain(conditions)
        if "active" in Item._fields:
            domain = [("active", "=", True)] + domain
        candidates = Item.search(domain, limit=max(limit * 5, 60))
        return self._score_records(candidates, terms, self._score_catalog_item, limit)

    def _ensure_compile_gap_job(self, source_layer, query_text, raw_sources, catalog_items):
        Job = self.env["diecut.kb.compile.job"].sudo()
        vals = {
            "priority": 5,
        }
        if "trigger_question" in Job._fields:
            vals["trigger_question"] = query_text or ""
        if "source_layer" in Job._fields:
            vals["source_layer"] = source_layer
        if "source_reason" in Job._fields:
            vals["source_reason"] = self._compile_gap_reason(query_text, raw_sources, catalog_items)

        domain = [("state", "in", ("pending", "processing"))]
        if raw_sources:
            source = raw_sources[0]
            domain += [("job_type", "=", "source_document"), ("source_document_id", "=", source.id)]
            existing = Job.search(domain, limit=1)
            if existing:
                existing.write(vals)
                return existing.id
            vals.update({"job_type": "source_document", "source_document_id": source.id})
            return Job.create(vals).id

        if catalog_items:
            item = catalog_items[0]
            domain += [("job_type", "=", "catalog_item"), ("item_id", "=", item.id)]
            existing = Job.search(domain, limit=1)
            if existing:
                existing.write(vals)
                return existing.id
            vals.update({"job_type": "catalog_item", "item_id": item.id})
            return Job.create(vals).id
        return False

    # ------------------------------------------------------------------
    # Context and answer generation
    # ------------------------------------------------------------------

    def _answer_with_client(self, client, query_text, plan, user_id=None):
        ok, payload, error, duration = client.chat_messages(
            query=self._build_answer_prompt(query_text, plan),
            user=user_id or "Wiki Searcher",
            inputs={"system": build_system_prompt("ai_advisor_qa", _DEFAULT_WIKI_QUERY_PROMPT)},
        )
        if not ok:
            return "", error or "Dify 调用失败", duration
        return self._clean_answer(self._extract_dify_answer(payload)), None, duration

    def _build_answer_prompt(self, query_text, plan):
        decision = plan.get("agent_decision") or {}
        analysis = plan.get("analysis") or {}
        sections = [
            "请根据下面的知识上下文回答用户问题。",
            "用户问题：%s" % (query_text or ""),
            "来源层级：%s" % plan["source_layer"],
            "问题意图：%s" % (decision.get("intent") or analysis.get("intent") or "unknown"),
            "检索决策：%s" % self._clip(decision.get("reason") or "", 300),
            (
                "回答要求：先给结论，再说明依据；如果使用材料目录或原始资料，必须说明尚未编译为正式 Wiki；"
                "如果是材料推荐，必须给出建议实测验证和风险提示；不要编造上下文之外的型号或参数。"
            ),
        ]
        if plan["articles"]:
            sections.append("=== 已编译 Wiki 上下文 ===\n%s" % self._build_wiki_context(plan["articles"]))
        if plan["raw_sources"]:
            sections.append("=== 原始资料上下文（尚未编译为正式 Wiki） ===\n%s" % self._build_raw_source_context(plan["raw_sources"]))
        if plan["catalog_items"]:
            sections.append("=== 材料目录结构化事实（尚未编译为正式 Wiki） ===\n%s" % self._build_catalog_context(plan["catalog_items"]))
        if plan.get("compile_job_id"):
            sections.append("已生成待编译任务：#%s。回答中可以简短说明该临时依据后续会沉淀为 Wiki。" % plan["compile_job_id"])
        return "\n\n".join(sections)

    def _build_wiki_context(self, articles):
        sections = []
        for article in articles:
            parts = ["### [%s] %s" % (article.wiki_page_type or "wiki", article.name)]
            if article.summary:
                parts.append("摘要：%s" % article.summary)
            if article.category_id:
                parts.append("分类：%s" % article.category_id.name)
            if article.keywords:
                parts.append("关键词：%s" % article.keywords)
            content = article.content_md or article.content_text or ""
            parts.append("正文：\n%s" % self._clip(content, 2400))

            link_lines = []
            for link in article.outbound_link_ids.filtered(lambda item: item.active)[:5]:
                link_lines.append("- 出链 -> %s（%s）：%s" % (
                    link.target_article_id.name,
                    link.link_type,
                    link.reason or "",
                ))
            for link in article.inbound_link_ids.filtered(lambda item: item.active)[:3]:
                link_lines.append("- 入链 <- %s（%s）：%s" % (
                    link.source_article_id.name,
                    link.link_type,
                    link.reason or "",
                ))
            if link_lines:
                parts.append("图谱关联：\n%s" % "\n".join(link_lines))

            cite_lines = []
            for cite in article.citation_ids[:3]:
                src_name = cite.source_document_id.name or ""
                page = " 第%s页" % cite.page_ref if cite.page_ref else ""
                cite_lines.append("- %s（来源：%s%s）" % (cite.claim_text[:100], src_name, page))
            if cite_lines:
                parts.append("来源引用：\n%s" % "\n".join(cite_lines))
            sections.append("\n".join(parts))
        return "\n\n---\n\n".join(sections)

    def _build_raw_source_context(self, sources):
        sections = []
        for source in sources:
            text = (
                getattr(source, "knowledge_parsed_markdown", False)
                or getattr(source, "knowledge_parsed_text", False)
                or getattr(source, "raw_text", False)
                or getattr(source, "result_message", False)
                or getattr(source, "draft_payload", False)
                or ""
            )
            parts = ["### 原始资料：%s" % (source.name or source.display_name)]
            for field_name, label in (
                ("source_filename", "文件名"),
                ("primary_attachment_name", "主附件"),
                ("source_type", "来源类型"),
                ("knowledge_source_kind", "资料类型"),
                ("brand_id", "品牌"),
                ("categ_id", "建议分类"),
                ("knowledge_parse_state", "解析状态"),
            ):
                value = self._record_value(source, field_name)
                if value:
                    parts.append("%s：%s" % (label, value))
            parts.append("内容片段：\n%s" % self._clip(text, 2600))
            sections.append("\n".join(parts))
        return "\n\n---\n\n".join(sections)

    def _build_catalog_context(self, items):
        sections = []
        for item in items:
            lines = ["### 材料目录：%s" % (item.display_name or item.name)]
            for field_name, label in self._CATALOG_CONTEXT_FIELDS:
                value = self._record_value(item, field_name)
                if value:
                    lines.append("- %s：%s" % (label, self._clip(value, 500)))
            spec_lines = []
            for spec in getattr(item, "spec_line_ids", self.env["diecut.catalog.item.spec.line"])[:8]:
                spec_value = " ".join(filter(None, [
                    spec.param_name or "",
                    getattr(spec, "value_display", False) or getattr(spec, "value_raw", False) or "",
                    getattr(spec, "unit", False) or getattr(spec, "uom", False) or "",
                    getattr(spec, "condition_summary", False) or getattr(spec, "test_condition", False) or "",
                ])).strip()
                if spec_value:
                    spec_lines.append("- %s" % spec_value)
            if spec_lines:
                lines.append("参数：\n%s" % "\n".join(spec_lines))
            sections.append("\n".join(lines))
        return "\n\n---\n\n".join(sections)

    def _fallback_answer_from_context(self, plan):
        if plan["catalog_items"]:
            item_lines = []
            for item in plan["catalog_items"][:6]:
                bits = []
                for field_name, label in self._CATALOG_CONTEXT_FIELDS[:11]:
                    value = self._record_value(item, field_name)
                    if value:
                        bits.append("%s：%s" % (label, value))
                if bits:
                    item_lines.append("- %s" % "；".join(bits))
            suffix = "该内容尚未编译为正式 Wiki，已生成待编译任务。" if plan.get("compile_job_id") else "该内容尚未编译为正式 Wiki。"
            if item_lines:
                return "根据材料目录结构化数据找到以下可能相关材料：\n%s\n\n%s" % ("\n".join(item_lines), suffix)
        if plan["raw_sources"]:
            source = plan["raw_sources"][0]
            return "Wiki 未命中，但在原始资料《%s》中找到可能相关内容；该资料尚未编译为正式 Wiki，已生成待编译任务。" % (source.name or source.display_name)
        if plan["articles"]:
            return "根据已编译 Wiki 找到相关页面，但未收到 AI 生成内容。请稍后重试。"
        return ""

    def _mark_provisional_answer(self, answer, plan):
        answer = answer or ""
        prefix = self._provisional_prefix(plan)
        if not prefix or not answer:
            return answer
        if "尚未编译为正式 Wiki" in answer or "未编译为正式 Wiki" in answer:
            return answer
        return prefix + answer

    @staticmethod
    def _provisional_prefix(plan):
        layer = plan.get("source_layer")
        if layer == "raw_source":
            return "Wiki 未命中，本回答使用原始资料的临时依据（尚未编译为正式 Wiki）。\n\n"
        if layer == "catalog":
            return "Wiki 未命中，本回答使用材料目录结构化数据的临时依据（尚未编译为正式 Wiki）。\n\n"
        if layer == "mixed":
            return "Wiki 未充分覆盖，本回答同时使用 Wiki、原始资料或材料目录中的可追溯依据；其中非 Wiki 部分尚未编译为正式 Wiki。\n\n"
        return ""

    # ------------------------------------------------------------------
    # Scoring and formatting helpers
    # ------------------------------------------------------------------

    def _extract_query_terms(self, query_text):
        text = (query_text or "").strip()
        terms = []

        def add(term):
            term = (term or "").strip()
            if not term or term in self._QUESTION_WORDS:
                return
            if len(term) == 1 and not term.isalnum():
                return
            lowered = term.lower()
            if lowered not in {item.lower() for item in terms}:
                terms.append(term)

        for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9._/-]*", text):
            add(token)
            add(token.lower())
            if re.search(r"\d", token):
                add(re.sub(r"[^A-Za-z0-9]", "", token))

        lowered_text = text.lower()
        for term in self._DOMAIN_TERMS:
            if term.lower() in lowered_text:
                add(term)

        chunks = re.split(r"[\s,，。？?；;、（）()\[\]【】《》<>!！]+", text)
        for chunk in chunks:
            chunk = re.sub(r"[A-Za-z0-9._/-]+", "", chunk).strip()
            if not chunk:
                continue
            compact = chunk
            for word in self._QUESTION_WORDS:
                compact = compact.replace(word, " ")
            for part in compact.split():
                add(part)
            if len(chunk) <= 12:
                add(chunk)
            max_n = min(7, len(chunk) + 1)
            for size in range(2, max_n):
                for index in range(0, len(chunk) - size + 1):
                    add(chunk[index:index + size])

        domain_terms = {term.lower() for term in self._DOMAIN_TERMS}

        def term_priority(value):
            lowered = value.lower()
            if re.search(r"\d", value):
                return 4
            if re.search(r"[A-Za-z]", value):
                return 3
            if lowered in domain_terms:
                return 2
            return 1

        terms.sort(key=lambda value: (term_priority(value), len(value)), reverse=True)
        return terms[:30]

    def _score_records(self, candidates, terms, scorer, limit):
        scored = []
        for record in candidates:
            score = scorer(record, terms)
            if score > 0:
                scored.append((score, record.id))
        scored.sort(reverse=True)
        return candidates.browse([record_id for _score, record_id in scored[:limit]])

    def _score_article(self, article, terms):
        texts = {
            "title": article.name or "",
            "slug": getattr(article, "wiki_slug", "") or "",
            "summary": article.summary or "",
            "keywords": article.keywords or "",
            "body": (article.content_md or article.content_text or "")[:8000],
        }
        score = self._score_text_bundle(texts, terms, {"title": 14, "slug": 12, "keywords": 9, "summary": 6, "body": 2})
        score += min((getattr(article, "graph_degree", 0) or 0), 12) * 0.15
        return score

    def _score_raw_source(self, source, terms):
        texts = {
            "title": source.name or "",
            "filename": (getattr(source, "source_filename", "") or "") + " " + (getattr(source, "primary_attachment_name", "") or ""),
            "brand": self._record_value(source, "brand_id"),
            "category": self._record_value(source, "categ_id"),
            "body": " ".join(filter(None, [
                getattr(source, "knowledge_parsed_text", "") or "",
                getattr(source, "knowledge_parsed_markdown", "") or "",
                getattr(source, "raw_text", "") or "",
                getattr(source, "result_message", "") or "",
                getattr(source, "draft_payload", "") or "",
            ]))[:12000],
        }
        return self._score_text_bundle(texts, terms, {"title": 14, "filename": 12, "brand": 8, "category": 5, "body": 2})

    def _score_catalog_item(self, item, terms):
        spec_texts = []
        for spec in getattr(item, "spec_line_ids", self.env["diecut.catalog.item.spec.line"])[:20]:
            spec_texts.append(" ".join(filter(None, [
                getattr(spec, "param_name", "") or "",
                getattr(spec, "value_display", False) or getattr(spec, "value_raw", False) or "",
                getattr(spec, "unit", False) or getattr(spec, "uom", False) or "",
                getattr(spec, "test_condition", False) or "",
                getattr(spec, "remark", False) or "",
            ])))
        texts = {
            "code": item.code or "",
            "name": item.name or "",
            "brand": self._record_value(item, "brand_id"),
            "series": self._record_value(item, "series_id"),
            "category": self._record_value(item, "categ_id"),
            "body": " ".join(filter(None, [
                item.thickness or "",
                item.thickness_std or "",
                item.adhesive_thickness or "",
                self._record_value(item, "color_id"),
                self._record_value(item, "adhesive_type_id"),
                self._record_value(item, "base_material_id"),
                item.selection_search_text or "",
                item.product_features or "",
                item.product_description or "",
                item.main_applications or "",
                item.special_applications or "",
                " ".join(spec_texts),
            ]))[:8000],
        }
        return self._score_text_bundle(texts, terms, {"code": 18, "name": 13, "brand": 8, "series": 6, "category": 5, "body": 2})

    @staticmethod
    def _score_text_bundle(texts, terms, weights):
        score = 0.0
        for term in terms:
            term_l = term.lower()
            normalized = re.sub(r"[^a-z0-9]", "", term_l)
            weight_factor = 1.6 if re.search(r"\d", term_l) else 1.0
            for key, text in texts.items():
                haystack = (text or "").lower()
                haystack_normalized = re.sub(r"[^a-z0-9]", "", haystack)
                if term_l in haystack:
                    score += weights.get(key, 1) * weight_factor * min(haystack.count(term_l), 4)
                elif normalized and normalized in haystack_normalized:
                    score += weights.get(key, 1) * weight_factor * 0.8
        return score

    @staticmethod
    def _or_domain(conditions):
        if not conditions:
            return []
        return expression.OR([[condition] for condition in conditions])

    @staticmethod
    def _can_sql_search(model, field_name):
        field = model._fields.get(field_name)
        return bool(field and getattr(field, "store", False))

    @staticmethod
    def _parse_selected_ids(answer):
        if not answer:
            return None
        text = KbSearcher._clean_answer(answer)
        text = re.sub(r"```(?:json)?", "", text, flags=re.I).replace("```", "").strip()
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start:end + 1]
        try:
            payload = json.loads(text)
        except Exception:
            _logger.info("Unable to parse Wiki retrieval JSON: %s", answer[:500])
            return None
        if isinstance(payload, list):
            ids = payload
        elif isinstance(payload, dict):
            ids = payload.get("selected_ids")
        else:
            return None
        if not isinstance(ids, list):
            return None
        clean_ids = []
        for item in ids:
            try:
                clean_ids.append(int(item))
            except Exception:
                continue
        return clean_ids

    def _source_refs(self, articles=None, raw_sources=None, catalog_items=None):
        refs = []
        for article in articles or []:
            refs.append({
                "layer": "wiki",
                "id": article.id,
                "name": article.name,
                "type": article.wiki_page_type or "wiki",
            })
        for source in raw_sources or []:
            refs.append({
                "layer": "raw_source",
                "id": source.id,
                "name": source.name or source.display_name,
                "type": getattr(source, "knowledge_source_kind", False) or getattr(source, "source_type", False) or "source",
            })
        for item in catalog_items or []:
            refs.append({
                "layer": "catalog",
                "id": item.id,
                "name": " ".join(filter(None, [self._record_value(item, "brand_id"), item.code or "", item.name or ""])).strip(),
                "type": "catalog_item",
            })
        return refs

    @staticmethod
    def _article_refs(articles):
        return [
            {"id": article.id, "name": article.name, "wiki_page_type": article.wiki_page_type}
            for article in articles
        ]

    def _compile_gap_reason(self, query_text, raw_sources, catalog_items):
        lines = ["触发问题：%s" % (query_text or "")]
        for source in raw_sources[:3]:
            lines.append("命中原始资料：%s" % (source.name or source.display_name))
        for item in catalog_items[:5]:
            lines.append("命中材料目录：%s" % (item.display_name or item.name))
        lines.append("建议：将上述临时依据编译成正式 Wiki，并建立图谱关联。")
        return "\n".join(lines)

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
        if isinstance(value, bool):
            return "是" if value else ""
        return str(value)

    @staticmethod
    def _extract_dify_answer(payload):
        payload = payload or {}
        answer = payload.get("answer") or payload.get("text") or ""
        if answer:
            return answer
        data = payload.get("data") or {}
        outputs = data.get("outputs") or payload.get("outputs") or {}
        if isinstance(outputs, dict):
            return outputs.get("answer") or outputs.get("text") or ""
        return ""

    def _build_dify_client(self):
        from .llm_client_factory import build_chat_client

        client, error, _profile = build_chat_client(
            self.env,
            model_profile_id=self.model_profile_id,
            purpose="advisor",
        )
        if error:
            _logger.warning("Wiki search LLM client unavailable: %s", error)
        return client

    @staticmethod
    def _clean_answer(answer):
        text = answer or ""
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.I | re.S)
        text = re.sub(r"</?think>", "", text, flags=re.I)
        return text.strip()

    @staticmethod
    def _clip(text, limit):
        text = re.sub(r"<[^>]+>", " ", str(text or ""))
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) <= limit:
            return text
        return text[:limit] + "...（已截断）"

    @staticmethod
    def _no_context_answer(query_text):
        return "当前 Wiki、原始资料、材料目录均未找到与“%s”相关的资料。" % (query_text or "")
