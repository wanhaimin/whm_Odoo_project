# -*- coding: utf-8 -*-
"""AI advisor controller for configured LLM profiles, Wiki, and Odoo context."""

import html
import json
import logging
import re

from werkzeug.wrappers import Response

from odoo import fields, http
from odoo.http import request

_logger = logging.getLogger(__name__)

ALLOWED_MODELS = {
    "diecut.catalog.item",
    "diecut.kb.article",
    "diecut.kb.qa_ticket",
    "diecut.catalog.source.document",
}


def _build_chat_client(env, model_profile_id=False):
    from ..services.llm_client_factory import build_chat_client

    return build_chat_client(env, model_profile_id=model_profile_id, purpose="advisor")


class DiecutAiAdvisor(http.Controller):
    @http.route("/diecut_knowledge/ai/model_profiles", type="json", auth="user")
    def ai_model_profiles(self):
        from ..services.llm_client_factory import advisor_options

        return {"ok": True, **advisor_options(request.env)}

    @http.route("/diecut_knowledge/ai/chat", type="json", auth="user")
    def ai_chat(self, query, model, record_id, conversation_id="", inputs=None, session_id=None, mode="ai", record_name="", model_profile_id=None):
        client, client_error, profile = _build_chat_client(request.env, model_profile_id)
        if not client:
            return {"ok": False, "error": client_error}

        session = _get_or_open_session(
            session_id=session_id,
            mode=mode or "ai",
            model=model,
            record_id=record_id,
            record_name=record_name,
            model_profile_id=profile.id if profile else False,
        )
        if session:
            conversation_id = conversation_id or session.dify_conversation_id or ""
            session.add_message("user", query, model_profile_id=profile.id if profile else False)

        chat_inputs = dict(inputs or {})
        if session:
            chat_inputs.update(
                {
                    "_ai_session_id": session.id,
                    "_record_name": record_name or session.record_name or "",
                    "_res_model": model or "",
                    "_res_id": int(record_id or 0),
                }
            )
        if model and record_id and model in ALLOWED_MODELS:
            try:
                record = request.env[model].browse(int(record_id))
                if record.exists():
                    chat_inputs.update(_build_record_context(record))
            except Exception as exc:
                _logger.warning("Failed to build AI advisor context: %s", exc)

        ok, payload, error, duration = client.chat_messages(
            query=query,
            user=request.env.user.display_name or "Odoo User",
            conversation_id=conversation_id,
            inputs=chat_inputs,
        )

        if not ok:
            return {"ok": False, "error": error or "AI 调用失败"}

        if (payload or {}).get("queued"):
            message_id = False
            if session:
                message = session.add_message(
                    "assistant",
                    (payload or {}).get("answer") or "OpenClaw 已加入队列，正在处理...",
                    question=query,
                    can_save=False,
                    model_profile_id=profile.id if profile else False,
                    openclaw_run_id=(payload or {}).get("run_db_id") or False,
                    async_state="queued",
                )
                message_id = message.id
            return {
                "ok": True,
                "queued": True,
                "answer": (payload or {}).get("answer") or "OpenClaw 已加入队列，正在处理...",
                "conversation_id": conversation_id,
                "session_id": session.id if session else False,
                "message_id": message_id,
                "openclaw_run_id": (payload or {}).get("run_db_id") or False,
                "duration_ms": duration,
                "model_profile_id": profile.id if profile else False,
                "model_profile_name": profile.name if profile else "",
            }

        answer = _clean_ai_answer((payload or {}).get("answer", ""))
        conversation_id = (payload or {}).get("conversation_id", conversation_id)
        message_id = False
        if session:
            session.dify_conversation_id = conversation_id or session.dify_conversation_id
            message = session.add_message(
                "assistant",
                answer,
                question=query,
                citations=(payload or {}).get("retriever_resources", []),
                can_save=bool(answer),
                model_profile_id=profile.id if profile else False,
            )
            message_id = message.id
        return {
            "ok": True,
            "answer": answer,
            "conversation_id": conversation_id,
            "session_id": session.id if session else False,
            "message_id": message_id,
            "duration_ms": duration,
            "citations": (payload or {}).get("retriever_resources", []),
            "model_profile_id": profile.id if profile else False,
            "model_profile_name": profile.name if profile else "",
        }

    @http.route("/diecut_knowledge/ai/chat_stream", type="http", auth="user", csrf=False)
    def ai_chat_stream(self, **kw):
        client, client_error, profile = _build_chat_client(request.env, kw.get("model_profile_id"))
        if not client:
            return Response(
                "data: %s\n\n" % json.dumps({"error": client_error}, ensure_ascii=False),
                mimetype="text/event-stream",
            )
        if profile and profile.protocol == "openclaw_worker":
            return Response(
                "data: %s\n\n" % json.dumps({"error": "OpenClaw 使用异步队列，不支持流式输出。"}, ensure_ascii=False),
                status=409,
                mimetype="text/event-stream",
            )

        query = kw.get("query", "")
        model = kw.get("model") or ""
        record_id = kw.get("record_id")
        conversation_id = kw.get("conversation_id", "")
        session = _get_or_open_session(
            session_id=kw.get("session_id"),
            mode=kw.get("mode") or "ai",
            model=model,
            record_id=record_id,
            record_name=kw.get("record_name") or "",
            model_profile_id=profile.id if profile else False,
        )
        if session:
            conversation_id = conversation_id or session.dify_conversation_id or ""
            session.add_message("user", query, model_profile_id=profile.id if profile else False)
        try:
            inputs = json.loads(kw.get("inputs", "{}")) if kw.get("inputs") else {}
        except (json.JSONDecodeError, TypeError):
            inputs = {}

        chat_inputs = dict(inputs or {})
        if session:
            chat_inputs.update(
                {
                    "_ai_session_id": session.id,
                    "_record_name": kw.get("record_name") or session.record_name or "",
                    "_res_model": model or "",
                    "_res_id": int(record_id or 0),
                }
            )
        if model and record_id and model in ALLOWED_MODELS:
            try:
                record = request.env[model].browse(int(record_id))
                if record.exists():
                    chat_inputs.update(_build_record_context(record))
            except Exception as exc:
                _logger.warning("Failed to build AI advisor context: %s", exc)

        user_name = request.env.user.display_name or "Odoo User"

        def generate():
            try:
                final_answer = ""
                final_citations = []
                final_conversation_id = conversation_id
                for event_type, data, error in client.chat_messages_stream(
                    query=query,
                    user=user_name,
                    conversation_id=conversation_id,
                    inputs=chat_inputs,
                ):
                    if event_type == "token":
                        final_answer = data.get("full_answer", "") or (final_answer + data.get("token", ""))
                        yield "data: %s\n\n" % json.dumps({"token": data.get("token", ""), "done": False}, ensure_ascii=False)
                    elif event_type == "done":
                        final_answer = data.get("full_answer", "") or final_answer
                        final_citations = data.get("citations", [])
                        final_conversation_id = data.get("conversation_id", "") or final_conversation_id
                        message_id = False
                        if session:
                            session.dify_conversation_id = final_conversation_id or session.dify_conversation_id
                            message = session.add_message(
                                "assistant",
                                _clean_ai_answer(final_answer),
                                question=query,
                                citations=final_citations,
                                can_save=bool(final_answer),
                                model_profile_id=profile.id if profile else False,
                            )
                            message_id = message.id
                        payload = {
                            "done": True,
                            "conversation_id": final_conversation_id,
                            "session_id": session.id if session else False,
                            "message_id": message_id,
                            "full_answer": _clean_ai_answer(final_answer),
                            "citations": final_citations,
                            "model_profile_id": profile.id if profile else False,
                            "model_profile_name": profile.name if profile else "",
                        }
                        yield "data: %s\n\n" % json.dumps(payload, ensure_ascii=False)
                    elif event_type == "error":
                        yield "data: %s\n\n" % json.dumps({"error": error or "AI 调用失败"}, ensure_ascii=False)
                        return
            except Exception as exc:
                _logger.exception("SSE stream error")
                yield "data: %s\n\n" % json.dumps({"error": str(exc)[:200]}, ensure_ascii=False)

        return Response(
            generate(),
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
            direct_passthrough=True,
        )

    @http.route("/diecut_knowledge/ai/save_answer", type="json", auth="user")
    def ai_save_answer(self, question, answer, model=None, record_id=None, record_name="", message_id=None):
        article = _save_answer_as_article(question=question, answer=answer, model=model, record_id=record_id, record_name=record_name)
        if not article:
            return {"ok": False, "error": "无法保存为知识文章"}
        message = _get_user_message(message_id)
        if message:
            message.write({"saved_article_id": article.id, "can_save": False})
        return {"ok": True, "article_id": article.id, "article_name": article.name}

    @http.route("/diecut_knowledge/ai/like_answer", type="json", auth="user")
    def ai_like_answer(self, question, answer, model=None, record_id=None, record_name="", message_id=None):
        message = _get_user_message(message_id)
        if message and message.liked_article_id:
            return {"ok": True, "article_id": message.liked_article_id.id, "already_liked": True}
        article = _save_answer_as_article(question=question, answer=answer, model=model, record_id=record_id, record_name=record_name)
        if not article:
            return {"ok": False, "error": "无法沉淀为知识文章"}
        if message:
            message.write({"liked_article_id": article.id})
        return {"ok": True, "article_id": article.id}

    @http.route("/diecut_knowledge/ai/session/open", type="json", auth="user")
    def ai_session_open(self, mode="ai", model="", record_id=0, record_name="", model_profile_id=None):
        profile_id = int(model_profile_id or 0) or False
        session = request.env["diecut.kb.ai.session"].open_session(
            mode=mode or "ai",
            res_model=model or "",
            res_id=record_id or 0,
            record_name=record_name or "",
            model_profile_id=profile_id,
        )
        from ..services.llm_client_factory import advisor_options

        return {"ok": True, **session.to_client_payload(), "model_options": advisor_options(request.env)}

    @http.route("/diecut_knowledge/ai/session/clear", type="json", auth="user")
    def ai_session_clear(self, session_id):
        session = _get_user_session(session_id)
        if not session:
            return {"ok": False, "error": "未找到当前会话"}
        session.clear_messages()
        return {"ok": True, **session.to_client_payload()}

    @http.route("/diecut_knowledge/ai/openclaw_status", type="json", auth="user")
    def ai_openclaw_status(self, message_id):
        message = _get_user_message(message_id)
        if not message or not message.openclaw_run_id:
            return {"ok": False, "error": "未找到 OpenClaw 任务。"}
        run = message.openclaw_run_id.sudo()
        state_map = {
            "queued": "queued",
            "running": "running",
            "succeeded": "done",
            "failed": "failed",
            "cancelled": "failed",
        }
        async_state = state_map.get(run.state, run.state or "queued")
        vals = {"async_state": async_state}
        if run.state == "succeeded":
            answer = _clean_ai_answer(run.reply_text or run.result_summary or "")
            vals.update({"content": answer, "can_save": bool(answer)})
        elif run.state in ("failed", "cancelled"):
            answer = run.error_message or "OpenClaw 任务失败。"
            vals.update({"content": answer, "can_save": False})
        else:
            answer = message.content or ("OpenClaw 正在处理..." if run.state == "running" else "OpenClaw 已加入队列，正在处理...")
        message.sudo().write(vals)
        return {
            "ok": True,
            "state": run.state,
            "async_state": async_state,
            "answer": answer,
            "can_save": bool(message.can_save or vals.get("can_save")),
            "run_id": run.id,
            "run_uuid": run.run_id,
            "error": run.error_message or "",
        }

    @http.route("/diecut_knowledge/wiki/chat", type="json", auth="user")
    def wiki_chat(self, query, **kw):
        from ..services.kb_searcher import KbSearcher

        session = _get_or_open_session(
            session_id=kw.get("session_id"),
            mode=kw.get("mode") or "wiki",
            model=kw.get("model") or "",
            record_id=kw.get("record_id") or 0,
            record_name=kw.get("record_name") or "",
            model_profile_id=kw.get("model_profile_id") or False,
        )
        if session:
            session.add_message("user", query)
        result = KbSearcher(request.env, model_profile_id=kw.get("model_profile_id") or False).query(
            query_text=query,
            user_id=request.env.user.display_name or "Wiki User",
        )
        message_id = False
        if session and result.get("ok"):
            message = session.add_message(
                "assistant",
                result.get("answer") or result.get("error") or "",
                question=query,
                source_layer=result.get("source_layer"),
                source_refs=result.get("source_refs", []),
                articles=result.get("articles", []),
                compile_job_id=result.get("compile_job_id"),
                can_save=bool(result.get("answer")),
            )
            message_id = message.id
        result["session_id"] = session.id if session else False
        result["message_id"] = message_id
        return result

    @http.route("/diecut_knowledge/wiki/chat_stream", type="http", auth="user", csrf=False)
    def wiki_chat_stream(self, **kw):
        query = kw.get("query", "")
        if not query:
            return Response("data: %s\n\n" % json.dumps({"error": "query is required"}), mimetype="text/event-stream")

        from ..services.kb_searcher import KbSearcher

        session = _get_or_open_session(
            session_id=kw.get("session_id"),
            mode=kw.get("mode") or "wiki",
            model=kw.get("model") or "",
            record_id=kw.get("record_id") or 0,
            record_name=kw.get("record_name") or "",
            model_profile_id=kw.get("model_profile_id") or False,
        )
        if session:
            session.add_message("user", query)
        searcher = KbSearcher(request.env, model_profile_id=kw.get("model_profile_id") or False)
        user_name = request.env.user.display_name or "Wiki User"

        def generate():
            try:
                for event_type, data, error in searcher.query_stream(query_text=query, user_id=user_name):
                    if event_type == "token":
                        yield "data: %s\n\n" % json.dumps({"token": data.get("token", ""), "done": False}, ensure_ascii=False)
                    elif event_type == "done":
                        final_data = data or {}
                        message_id = False
                        if session:
                            message = session.add_message(
                                "assistant",
                                final_data.get("full_answer", ""),
                                question=query,
                                source_layer=final_data.get("source_layer"),
                                source_refs=final_data.get("source_refs", []),
                                articles=final_data.get("articles", []),
                                compile_job_id=final_data.get("compile_job_id"),
                                can_save=bool(final_data.get("full_answer")),
                            )
                            message_id = message.id
                        yield "data: %s\n\n" % json.dumps(
                            {
                                "done": True,
                                "session_id": session.id if session else False,
                                "message_id": message_id,
                                "full_answer": final_data.get("full_answer", ""),
                                "articles": final_data.get("articles", []),
                                "source_layer": final_data.get("source_layer"),
                                "source_refs": final_data.get("source_refs", []),
                                "compile_job_id": final_data.get("compile_job_id"),
                            },
                            ensure_ascii=False,
                        )
                        return
            except Exception as exc:
                _logger.exception("Wiki chat stream error")
                yield "data: %s\n\n" % json.dumps({"error": str(exc)[:200]}, ensure_ascii=False)

        return Response(
            generate(),
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
            direct_passthrough=True,
        )


def _get_user_session(session_id):
    try:
        session_id = int(session_id or 0)
    except (TypeError, ValueError):
        return request.env["diecut.kb.ai.session"].browse()
    if not session_id:
        return request.env["diecut.kb.ai.session"].browse()
    session = request.env["diecut.kb.ai.session"].browse(session_id).exists()
    if not session:
        return session
    if session.create_uid != request.env.user and not request.env.user.has_group("base.group_system"):
        return request.env["diecut.kb.ai.session"].browse()
    return session


def _get_or_open_session(session_id=None, mode="ai", model="", record_id=0, record_name="", model_profile_id=False):
    session = _get_user_session(session_id)
    if session:
        if model_profile_id and session.model_profile_id.id != int(model_profile_id):
            session.model_profile_id = int(model_profile_id)
        return session
    return request.env["diecut.kb.ai.session"].open_session(
        mode=mode or "ai",
        res_model=model or "",
        res_id=record_id or 0,
        record_name=record_name or "",
        model_profile_id=model_profile_id or False,
    )


def _get_user_message(message_id):
    try:
        message_id = int(message_id or 0)
    except (TypeError, ValueError):
        return request.env["diecut.kb.ai.message"].browse()
    if not message_id:
        return request.env["diecut.kb.ai.message"].browse()
    message = request.env["diecut.kb.ai.message"].browse(message_id).exists()
    if not message:
        return message
    session = message.session_id
    if session.create_uid != request.env.user and not request.env.user.has_group("base.group_system"):
        return request.env["diecut.kb.ai.message"].browse()
    return message


def _clean_ai_answer(answer: str) -> str:
    text = answer or ""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"</?think>", "", text, flags=re.IGNORECASE)
    return text.strip()


def _build_record_context(record) -> dict:
    ctx = {"odoo_model": record._name, "odoo_id": record.id}
    if record._name == "diecut.catalog.item":
        ctx.update(
            {
                "产品编码": record.code or "",
                "产品名称": record.name or "",
                "品牌": record.brand_id.name or "",
                "系列": record.series_id.name or "",
                "分类": record.categ_id.name or "",
                "厚度": record.thickness or "",
                "颜色": record.color_id.name or "",
                "胶系": record.adhesive_type_id.name or "",
                "基材": record.base_material_id.name or "",
                "阻燃等级": record.fire_rating or "",
                "产品说明": record.product_description or "",
                "主要应用": record.main_applications or "",
            }
        )
        spec_parts = []
        for line in record.spec_line_ids.sorted(key=lambda line: (line.sequence, line.id)):
            param = line.param_id.name or line.param_name or ""
            value = line.value_display or ""
            unit = line.unit or ""
            if param:
                spec_parts.append(f"{param}: {value} {unit}".strip())
        if spec_parts:
            ctx["技术参数"] = "\n".join(spec_parts)
    elif record._name == "diecut.kb.article":
        ctx.update(
            {
                "标题": record.name or "",
                "分类": record.category_id.name or "",
                "摘要": record.summary or "",
                "正文": record.content_text or record.content_md or "",
                "关键词": record.keywords or "",
            }
        )
    elif record._name == "diecut.kb.qa_ticket":
        ctx.update(
            {
                "问题标题": record.name or "",
                "问题": record.question or "",
                "回答": record.answer or "",
                "客户": record.customer_name or "",
                "来源": record.source or "",
                "关键词": record.keywords or "",
            }
        )
    elif record._name == "diecut.catalog.source.document":
        ctx.update(
            {
                "资料标题": record.name or "",
                "资料类型": getattr(record, "knowledge_source_kind", "") or "",
                "导入状态": record.import_status or "",
                "附件": getattr(record, "primary_attachment_name", "") or "",
                "品牌": record.brand_id.name if getattr(record, "brand_id", False) else "",
                "分类": record.categ_id.name if getattr(record, "categ_id", False) else "",
                "解析文本": (
                    getattr(record, "knowledge_parsed_text", "")
                    or getattr(record, "raw_text", "")
                    or ""
                )[:6000],
            }
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
    if model and record_id and model in ALLOWED_MODELS:
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
    article = env["diecut.kb.article"].create(
        {
            "name": ("AI沉淀：%s" % title_base)[:200],
            "category_id": category.id,
            "summary": question.strip()[:200],
            "content_html": (
                "<h2>问题</h2><p>%s</p><h2>AI 回答</h2><p>%s</p>"
                % (html.escape(question or ""), html.escape(answer or "").replace("\n", "<br/>"))
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
        }
    )
    article._run_enrichment()
    try:
        from ..services.kb_linter import KbLinter

        KbLinter(env).lint_article(article)
    except Exception as exc:
        _logger.warning("AI answer article lint failed for article %s: %s", article.id, exc)
    return article
