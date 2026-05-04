# -*- coding: utf-8 -*-

import html
import json
import re


SCHEMA_VERSION = "odoo-llm-wiki-v1"

SOURCE_KINDS = {
    "tds",
    "selection_guide",
    "application_note",
    "processing_experience",
    "qa",
    "web",
    "image",
    "raw",
    "unknown",
}

INGEST_ACTIONS = {
    "parse_source",
    "compile_wiki",
    "generate_faq",
    "extract_material_draft",
    "cross_reference",
    "merge_existing",
    "archive",
    "human_review",
}

TARGET_OUTPUTS = {
    "wiki",
    "faq",
    "material_draft",
    "application_note",
    "comparison",
    "graph_links",
}

WIKI_STRATEGIES = {"create", "update_existing", "merge_review", "review_only", "skip"}
INCREMENTAL_WIKI_OPERATIONS = {
    "create_article",
    "update_article",
    "merge_into_existing",
    "mark_conflict",
    "review_only",
}
RISK_LEVELS = {"low", "medium", "high"}

WIKI_PAGE_TYPES = {
    "source_summary",
    "brand",
    "material",
    "material_category",
    "application",
    "process",
    "faq",
    "comparison",
    "concept",
    "query_answer",
}

LINK_TYPES = {
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


INGEST_PLAN_SCHEMA = {
    "schema_version": SCHEMA_VERSION,
    "source_kind": "tds|selection_guide|application_note|processing_experience|qa|web|image|raw|unknown",
    "summary": "一句话说明资料价值",
    "recommended_actions": ["parse_source", "compile_wiki", "cross_reference"],
    "target_outputs": ["wiki", "faq"],
    "requires_human_review": True,
    "risk_level": "low|medium|high",
    "risk_notes": ["来源页码不足"],
    "wiki_strategy": "create|update_existing|merge_review|review_only|skip",
    "candidate_old_pages": [
        {
            "article_id": 0,
            "title": "旧 Wiki 标题",
            "reason": "为什么是候选旧页面",
            "intended_operation": "link|update|merge_review|conflict_review",
        }
    ],
    "related_keywords": ["品牌、型号、材料类别、应用场景关键词"],
}


WIKI_PATCH_SCHEMA = {
    "schema_version": SCHEMA_VERSION,
    "page": {
        "operation": "create|update_existing|merge_review|review_only",
        "target_article_id": None,
        "title": "Wiki 页面标题",
        "wiki_slug": "lowercase-hyphen-slug",
        "wiki_page_type": "source_summary|brand|material|material_category|application|process|faq|comparison|concept|query_answer",
        "summary": "一到两句话摘要",
        "content_md": "# Markdown 正文，包含相关 [[wiki-slug|标题]] 链接",
        "keywords": ["关键词"],
    },
    "citations": [
        {
            "claim_text": "关键事实",
            "source_document_id": None,
            "page_ref": "1-2",
            "excerpt": "来源原文片段",
            "confidence": 0.8,
            "state": "valid|review|conflict",
        }
    ],
    "links": [
        {
            "target_id": 0,
            "link_type": "mentions|same_brand|same_material|same_application|same_process|compares_with|depends_on|contradicts|updates",
            "anchor_text": "链接锚文本",
            "reason": "为什么关联",
            "confidence": 0.7,
        }
    ],
    "remove_link_ids": [],
    "faq_items": [{"question": "问题", "answer": "答案"}],
    "conflicts": [{"description": "冲突说明", "related_article_id": None}],
    "review_required": True,
    "risk_level": "low|medium|high",
    "risk_notes": ["需要人工复核的原因"],
}


INCREMENTAL_WIKI_PATCH_PLAN_SCHEMA = {
    "schema_version": SCHEMA_VERSION,
    "topic": {
        "group_key": "brand|kind|keyword",
        "title": "Topic title",
        "summary": "Why these sources should be compiled together",
    },
    "patches": [
        {
            "operation": "create_article|update_article|merge_into_existing|mark_conflict|review_only",
            "target_article_id": None,
            "title": "Wiki page title",
            "wiki_slug": "lowercase-hyphen-slug",
            "wiki_page_type": "source_summary|brand|material|material_category|application|process|faq|comparison|concept|query_answer",
            "summary": "One or two sentence summary",
            "content_md": "# Markdown content with [[wiki-slug|title]] links",
            "keywords": ["brand", "material", "application"],
            "source_document_ids": [0],
            "citations": WIKI_PATCH_SCHEMA["citations"],
            "links": WIKI_PATCH_SCHEMA["links"],
            "conflicts": WIKI_PATCH_SCHEMA["conflicts"],
            "review_required": True,
            "risk_level": "low|medium|high",
            "risk_notes": ["Reasons that need human review"],
        }
    ],
    "remove_link_ids": [],
    "review_required": True,
    "risk_level": "low|medium|high",
    "risk_notes": ["Group-level notes"],
}


GRAPH_PATCH_SCHEMA = {
    "schema_version": SCHEMA_VERSION,
    "links": WIKI_PATCH_SCHEMA["links"],
    "remove_link_ids": [],
    "review_required": False,
    "notes": ["图谱维护备注"],
}


def extract_json_object(text):
    text = (text or "").strip()
    if not text:
        return {}
    text = re.sub(r"^```json\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)
    match = re.search(r"\{.*\}", text, flags=re.S)
    if match:
        text = match.group(0)
    try:
        payload = json.loads(text)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def clamp_confidence(value, default=0.6):
    try:
        number = float(value)
    except Exception:
        number = default
    return max(0.0, min(1.0, number))


def normalize_ingest_plan(plan, default_kind="raw"):
    plan = plan if isinstance(plan, dict) else {}
    kind = plan.get("source_kind") if plan.get("source_kind") in SOURCE_KINDS else default_kind
    if kind == "unknown":
        kind = "raw"
    actions = [item for item in (plan.get("recommended_actions") or []) if item in INGEST_ACTIONS]
    outputs = [item for item in (plan.get("target_outputs") or []) if item in TARGET_OUTPUTS]
    if not actions:
        actions = ["compile_wiki", "generate_faq", "cross_reference"]
    if not outputs:
        outputs = ["wiki", "faq"]
    risk_level = plan.get("risk_level") if plan.get("risk_level") in RISK_LEVELS else "medium"
    wiki_strategy = plan.get("wiki_strategy") if plan.get("wiki_strategy") in WIKI_STRATEGIES else "create"
    candidates = []
    for row in plan.get("candidate_old_pages") or []:
        if isinstance(row, dict):
            candidates.append(
                {
                    "article_id": row.get("article_id") or row.get("id") or False,
                    "title": str(row.get("title") or ""),
                    "reason": str(row.get("reason") or ""),
                    "intended_operation": str(row.get("intended_operation") or "link"),
                }
            )
    return {
        "schema_version": plan.get("schema_version") or SCHEMA_VERSION,
        "source_kind": kind,
        "summary": str(plan.get("summary") or "建议将该资料编译为可维护 Wiki。"),
        "recommended_actions": list(dict.fromkeys(actions)),
        "target_outputs": list(dict.fromkeys(outputs)),
        "requires_human_review": bool(plan.get("requires_human_review") or risk_level != "low"),
        "risk_level": risk_level,
        "risk_notes": [str(item) for item in (plan.get("risk_notes") or []) if item],
        "wiki_strategy": wiki_strategy,
        "candidate_old_pages": candidates,
        "related_keywords": [str(item) for item in (plan.get("related_keywords") or []) if item],
    }


def normalize_wiki_patch(payload, source=False, fallback_title="", fallback_summary="", fallback_content=""):
    payload = payload if isinstance(payload, dict) else {}
    page = payload.get("page") if isinstance(payload.get("page"), dict) else {}
    title = str(page.get("title") or fallback_title or "未命名 Wiki").strip()
    summary = str(page.get("summary") or fallback_summary or "").strip()
    page_type = page.get("wiki_page_type") if page.get("wiki_page_type") in WIKI_PAGE_TYPES else "source_summary"
    risk_level = payload.get("risk_level") if payload.get("risk_level") in RISK_LEVELS else "medium"
    content_md = str(page.get("content_md") or fallback_content or "").strip()
    if content_md and not content_md.startswith("#"):
        content_md = "# %s\n\n%s" % (title, content_md)
    citations = []
    for row in payload.get("citations") or []:
        if not isinstance(row, dict):
            continue
        claim = str(row.get("claim_text") or "").strip()
        if not claim:
            continue
        state = row.get("state") if row.get("state") in {"valid", "review", "conflict"} else "review"
        citations.append(
            {
                "claim_text": claim,
                "source_document_id": row.get("source_document_id") or (source.id if source else False),
                "page_ref": str(row.get("page_ref") or ""),
                "excerpt": str(row.get("excerpt") or "")[:2000],
                "confidence": clamp_confidence(row.get("confidence"), 0.6),
                "state": state,
            }
        )
    links = normalize_graph_links(payload)
    return {
        "schema_version": payload.get("schema_version") or SCHEMA_VERSION,
        "page": {
            "operation": page.get("operation") if page.get("operation") in {"create", "update_existing", "merge_review", "review_only"} else "create",
            "target_article_id": page.get("target_article_id") or False,
            "title": title,
            "wiki_slug": str(page.get("wiki_slug") or slugify(title)),
            "wiki_page_type": page_type,
            "summary": summary,
            "content_md": content_md,
            "keywords": [str(item) for item in (page.get("keywords") or []) if item],
        },
        "citations": citations,
        "links": links.get("links", []),
        "remove_link_ids": links.get("remove_link_ids", []),
        "faq_items": [row for row in (payload.get("faq_items") or []) if isinstance(row, dict)],
        "conflicts": [row for row in (payload.get("conflicts") or []) if isinstance(row, dict)],
        "review_required": bool(payload.get("review_required") or risk_level != "low"),
        "risk_level": risk_level,
        "risk_notes": [str(item) for item in (payload.get("risk_notes") or []) if item],
    }


def normalize_incremental_wiki_patch_plan(payload, sources=False, fallback_title=""):
    payload = payload if isinstance(payload, dict) else {}
    sources = sources or []
    source_ids = [source.id for source in sources if getattr(source, "id", False)]
    topic = payload.get("topic") if isinstance(payload.get("topic"), dict) else {}
    risk_level = payload.get("risk_level") if payload.get("risk_level") in RISK_LEVELS else "medium"
    patches = []
    for row in payload.get("patches") or payload.get("articles") or []:
        if not isinstance(row, dict):
            continue
        operation = row.get("operation") if row.get("operation") in INCREMENTAL_WIKI_OPERATIONS else "review_only"
        patch_risk = row.get("risk_level") if row.get("risk_level") in RISK_LEVELS else risk_level
        title = str(row.get("title") or fallback_title or "Incremental Wiki Patch").strip()
        content_md = str(row.get("content_md") or "").strip()
        if content_md and not content_md.startswith("#"):
            content_md = "# %s\n\n%s" % (title, content_md)
        row_source_ids = []
        for value in row.get("source_document_ids") or row.get("source_ids") or source_ids:
            try:
                value = int(value)
            except Exception:
                continue
            if not source_ids or value in source_ids:
                row_source_ids.append(value)
        patch = normalize_wiki_patch(
            {
                "page": {
                    "operation": _operation_to_page_operation(operation),
                    "target_article_id": row.get("target_article_id") or False,
                    "title": title,
                    "wiki_slug": row.get("wiki_slug") or slugify(title),
                    "wiki_page_type": row.get("wiki_page_type") or "source_summary",
                    "summary": row.get("summary") or "",
                    "content_md": content_md,
                    "keywords": row.get("keywords") or [],
                },
                "citations": row.get("citations") or [],
                "links": row.get("links") or [],
                "remove_link_ids": row.get("remove_link_ids") or [],
                "conflicts": row.get("conflicts") or [],
                "review_required": row.get("review_required"),
                "risk_level": patch_risk,
                "risk_notes": row.get("risk_notes") or [],
            },
            source=False,
            fallback_title=title,
            fallback_summary=row.get("summary") or "",
            fallback_content=content_md,
        )
        patch["operation"] = operation
        patch["source_document_ids"] = list(dict.fromkeys(row_source_ids or source_ids))
        patches.append(patch)
    return {
        "schema_version": payload.get("schema_version") or SCHEMA_VERSION,
        "topic": {
            "group_key": str(topic.get("group_key") or ""),
            "title": str(topic.get("title") or fallback_title or ""),
            "summary": str(topic.get("summary") or ""),
        },
        "patches": patches,
        "remove_link_ids": [value for value in payload.get("remove_link_ids") or []],
        "review_required": bool(payload.get("review_required") or risk_level != "low"),
        "risk_level": risk_level,
        "risk_notes": [str(item) for item in (payload.get("risk_notes") or []) if item],
    }


def _operation_to_page_operation(operation):
    if operation == "create_article":
        return "create"
    if operation == "update_article":
        return "update_existing"
    if operation == "merge_into_existing":
        return "merge_review"
    return "review_only"


def normalize_graph_links(payload):
    payload = payload if isinstance(payload, dict) else {}
    rows = []
    for row in payload.get("links") or []:
        if not isinstance(row, dict):
            continue
        link_type = row.get("link_type") if row.get("link_type") in LINK_TYPES else "mentions"
        rows.append(
            {
                "target_id": row.get("target_id") or row.get("article_id") or False,
                "link_type": link_type,
                "anchor_text": str(row.get("anchor_text") or ""),
                "reason": str(row.get("reason") or "LLM 判断该页面应接入当前 Wiki 图谱。"),
                "confidence": clamp_confidence(row.get("confidence"), 0.6),
            }
        )
    remove_ids = []
    for value in payload.get("remove_link_ids") or []:
        try:
            remove_ids.append(int(value))
        except Exception:
            continue
    return {
        "schema_version": payload.get("schema_version") or SCHEMA_VERSION,
        "links": rows,
        "remove_link_ids": remove_ids,
        "review_required": bool(payload.get("review_required")),
        "notes": [str(item) for item in (payload.get("notes") or []) if item],
    }


def markdown_to_html(markdown):
    text = (markdown or "").strip()
    if not text:
        return ""
    lines = text.splitlines()
    output = []
    in_list = False
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            if in_list:
                output.append("</ul>")
                in_list = False
            continue
        if line.startswith("### "):
            if in_list:
                output.append("</ul>")
                in_list = False
            output.append("<h3>%s</h3>" % _inline_markup(line[4:]))
        elif line.startswith("## "):
            if in_list:
                output.append("</ul>")
                in_list = False
            output.append("<h2>%s</h2>" % _inline_markup(line[3:]))
        elif line.startswith("# "):
            if in_list:
                output.append("</ul>")
                in_list = False
            output.append("<h2>%s</h2>" % _inline_markup(line[2:]))
        elif line.startswith("- "):
            if not in_list:
                output.append("<ul>")
                in_list = True
            output.append("<li>%s</li>" % _inline_markup(line[2:]))
        else:
            if in_list:
                output.append("</ul>")
                in_list = False
            output.append("<p>%s</p>" % _inline_markup(line))
    if in_list:
        output.append("</ul>")
    return "\n".join(output)


def slugify(value):
    value = (value or "").strip().lower()
    value = re.sub(r"\[[^\]]+\]", "", value)
    value = re.sub(r"[^\w\u4e00-\u9fff]+", "-", value, flags=re.U)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value or "wiki-page"


def _inline_markup(text):
    value = html.escape(text or "")
    value = re.sub(r"\[\[([^|\]]+)\|([^\]]+)\]\]", r"<span data-wiki-link=\"\1\">\2</span>", value)
    value = re.sub(r"\[\[([^\]]+)\]\]", r"<span data-wiki-link=\"\1\">\1</span>", value)
    value = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", value)
    return value
