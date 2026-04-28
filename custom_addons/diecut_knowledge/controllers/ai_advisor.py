# -*- coding: utf-8 -*-
"""AI 顾问 Controller — 代理调用 Dify Chat API，避免 API key 暴露到前端。"""

import logging
import re

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class DiecutAiAdvisor(http.Controller):

    @http.route("/diecut_knowledge/ai/chat", type="json", auth="user")
    def ai_chat(self, query, model, record_id, conversation_id="", inputs=None):
        base_url = (
            request.env["ir.config_parameter"]
            .sudo()
            .get_param("diecut_knowledge.dify_base_url")
        )
        api_key = (
            request.env["ir.config_parameter"]
            .sudo()
            .get_param("diecut_knowledge.dify_chat_api_key")
        )

        if not base_url or not api_key:
            return {
                "ok": False,
                "error": "Dify 未配置，请先在系统设置 → 行业知识库 → Dify 配置 中填写 Base URL 和 Chat API Key。",
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
            new_cid = (payload or {}).get("conversation_id", conversation_id)
            return {
                "ok": True,
                "answer": answer,
                "conversation_id": new_cid,
                "duration_ms": duration,
            }
        return {"ok": False, "error": error or "Dify API 调用失败"}


def _clean_ai_answer(answer: str) -> str:
    """Hide reasoning traces leaked by some chat models."""
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
