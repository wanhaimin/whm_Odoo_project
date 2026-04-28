# -*- coding: utf-8 -*-
"""AI 顾问 Controller：代理调用 Dify Chat API，避免 API key 暴露到前端。"""

import html
import logging
import re

from odoo import fields, http
from odoo.http import request

_logger = logging.getLogger(__name__)


class DiecutAiAdvisor(http.Controller):
    @http.route("/diecut_knowledge/ai/chat", type="json", auth="user")
    def ai_chat(self, query, model, record_id, conversation_id="", inputs=None):
        base_url = request.env["ir.config_parameter"].sudo().get_param("diecut_knowledge.dify_base_url")
        api_key = request.env["ir.config_parameter"].sudo().get_param("diecut_knowledge.dify_chat_api_key")

        if not base_url or not api_key:
            return {
                "ok": False,
                "error": "Dify 未配置，请先在系统设置中填写 Base URL 和 Chat API Key。",
            }

        chat_inputs = dict(inputs or {})
        if model and record_id:
            try:
                record = request.env[model].browse(record_id)
                if record.exists():
                    chat_inputs.update(_build_record_context(record))
            except Exception as exc:
                _logger.warning("Failed to build AI advisor context: %s", exc)

        from ..services.dify_client import DifyClient

        client = DifyClient(base_url=base_url, api_key=api_key)
        ok, payload, error, duration = client.chat_messages(
            query=query,
            user=request.env.user.display_name or "Odoo User",
            conversation_id=conversation_id,
            inputs=chat_inputs,
        )

        if ok:
            answer = _clean_ai_answer((payload or {}).get("answer", ""))
            return {
                "ok": True,
                "answer": answer,
                "conversation_id": (payload or {}).get("conversation_id", conversation_id),
                "duration_ms": duration,
            }
        return {"ok": False, "error": error or "Dify API 调用失败"}

    @http.route("/diecut_knowledge/ai/save_answer", type="json", auth="user")
    def ai_save_answer(self, question, answer, model=None, record_id=None, record_name=""):
        article = _save_answer_as_article(question=question, answer=answer, model=model, record_id=record_id, record_name=record_name)
        if not article:
            return {"ok": False, "error": "保存失败"}
        return {"ok": True, "article_id": article.id, "article_name": article.name}


def _clean_ai_answer(answer: str) -> str:
    text = answer or ""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"</?think>", "", text, flags=re.IGNORECASE)
    return text.strip()


def _build_record_context(record) -> dict:
    ctx = {"odoo_model": record._name, "odoo_id": record.id}

    if record._name == "diecut.catalog.item":
        ctx["型号"] = record.code or ""
        ctx["名称"] = record.name or ""
        ctx["品牌"] = record.brand_id.name or ""
        ctx["系列"] = record.series_id.name or ""
        ctx["材料分类"] = record.categ_id.name or ""
        ctx["厚度"] = record.thickness or ""
        ctx["颜色"] = record.color_id.name or ""
        ctx["胶系"] = record.adhesive_type_id.name or ""
        ctx["基材"] = record.base_material_id.name or ""
        ctx["防火等级"] = record.fire_rating or ""
        if record.is_rohs:
            ctx["RoHS"] = "是"
        if record.is_reach:
            ctx["REACH"] = "是"
        if record.is_halogen_free:
            ctx["无卤"] = "是"
        spec_parts = []
        for line in record.spec_line_ids.sorted(key=lambda l: (l.sequence, l.id)):
            param = line.param_id.name or line.param_name or ""
            value = line.value_display or ""
            unit = line.unit or ""
            if param:
                spec_parts.append(f"{param}: {value} {unit}".strip())
        if spec_parts:
            ctx["技术参数"] = "\n".join(spec_parts)

    elif record._name == "diecut.kb.article":
        ctx["标题"] = record.name or ""
        ctx["分类"] = record.category_id.name or ""
        ctx["摘要"] = record.summary or ""
        ctx["正文"] = record.content_text or ""
        ctx["关键词"] = record.keywords or ""

    elif record._name == "diecut.kb.qa_ticket":
        ctx["问题摘要"] = record.name or ""
        ctx["知识分类"] = record.category_id.name or ""
        ctx["客户问题"] = record.question or ""
        ctx["答复内容"] = record.answer or ""
        ctx["客户名称"] = record.customer_name or ""
        ctx["来源渠道"] = record.source or ""
        ctx["原始编号"] = record.source_ref or ""
        ctx["关键词"] = record.keywords or ""
        if record.related_brand_ids:
            ctx["关联品牌"] = ", ".join(record.related_brand_ids.mapped("name"))
        if record.related_item_ids:
            ctx["关联型号"] = ", ".join(
                f"[{item.brand_id.name or ''}] {item.code or ''} {item.name or ''}".strip()
                for item in record.related_item_ids
            )

    return ctx


def _save_answer_as_article(question, answer, model=None, record_id=None, record_name=""):
    env = request.env
    category = None
    related_brand_ids = []
    related_categ_ids = []
    related_item_ids = []
    source_item_id = False

    source_record = False
    if model and record_id:
        source_record = env[model].browse(record_id)
    if source_record and source_record.exists():
        if model == "diecut.kb.article":
            category = source_record.category_id
            related_brand_ids = source_record.related_brand_ids.ids
            related_categ_ids = source_record.related_categ_ids.ids
            related_item_ids = source_record.related_item_ids.ids
        elif model == "diecut.catalog.item":
            category = env["diecut.kb.category"].search([("code", "=", "material_selection")], limit=1)
            related_brand_ids = source_record.brand_id.ids
            related_categ_ids = source_record.categ_id.ids
            related_item_ids = [source_record.id]
            source_item_id = source_record.id
        elif model == "diecut.kb.qa_ticket":
            category = source_record.category_id
            related_brand_ids = source_record.related_brand_ids.ids
            related_item_ids = source_record.related_item_ids.ids
            related_categ_ids = source_record.related_item_ids.mapped("categ_id").ids

    if not category:
        category = env["diecut.kb.category"].search([], limit=1, order="sequence, id")
    if not category:
        return False

    title_base = question.strip()[:80] or record_name or "AI 对话沉淀"
    article = env["diecut.kb.article"].create({
        "name": f"AI沉淀：{title_base}"[:200],
        "category_id": category.id,
        "summary": question.strip()[:200],
        "content_html": (
            "<h2>问题</h2><p>%s</p><h2>AI 回答</h2><p>%s</p>" %
            (html.escape(question or ""), html.escape(answer or "").replace("\n", "<br/>"))
        ),
        "state": "review",
        "sync_status": "pending",
        "compile_source": "ai_answer",
        "compile_source_item_id": source_item_id or False,
        "compiled_at": fields.Datetime.now(),
        "related_brand_ids": [(6, 0, related_brand_ids)],
        "related_categ_ids": [(6, 0, related_categ_ids)],
        "related_item_ids": [(6, 0, related_item_ids)],
        "keywords": ", ".join(filter(None, [question[:40], record_name])),
        "author_name": env.user.display_name,
    })
    article._run_enrichment()
    return article
