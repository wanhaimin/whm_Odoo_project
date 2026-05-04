# -*- coding: utf-8 -*-
"""OpenClaw worker adapter for the AI advisor.

This adapter intentionally does not run the OpenClaw CLI in the Odoo process.
It creates a chatter.ai.run record and lets the existing chatter_ai_assistant
external worker claim and complete it.
"""

import html
import json
import time
import uuid

from odoo import fields


class OpenClawWorkerClient:
    def __init__(self, *, env):
        self.env = env

    def test_connection(self):
        t0 = time.monotonic()
        try:
            config = self.env["chatter.ai.run"].sudo()._config()
            cli_command = (config.get("cli_command") or "").strip()
            agent_id = (config.get("general_agent_id") or "").strip()
            if not cli_command:
                return False, {}, "OpenClaw CLI Command 未配置。", self._duration(t0)
            if not agent_id:
                return False, {}, "OpenClaw General Agent ID 未配置。", self._duration(t0)
            return True, {"answer": "OpenClaw worker 配置可用。"}, None, self._duration(t0)
        except Exception as exc:  # pylint: disable=broad-except
            return False, {}, str(exc), self._duration(t0)

    def chat_messages(
        self,
        query,
        *,
        user="",
        conversation_id="",
        inputs=None,
        response_mode="blocking",
        files=None,
    ):
        t0 = time.monotonic()
        try:
            run = self._create_run(query=query, user=user, conversation_id=conversation_id, inputs=inputs or {})
            run._trigger_processing()
            return (
                True,
                {
                    "answer": "OpenClaw 已加入队列，正在处理...",
                    "queued": True,
                    "run_id": run.run_id,
                    "run_db_id": run.id,
                    "conversation_id": conversation_id,
                },
                None,
                self._duration(t0),
            )
        except Exception as exc:  # pylint: disable=broad-except
            return False, {}, str(exc), self._duration(t0)

    def chat_messages_stream(self, *args, **kwargs):
        yield ("error", {}, "OpenClaw 使用异步 worker 队列，不支持流式输出。")

    def _create_run(self, *, query, user="", conversation_id="", inputs=None):
        inputs = dict(inputs or {})
        session = self._session(inputs.get("_ai_session_id"))
        context_rows = self._context_rows(session)
        prompt_text = self._build_prompt_text(query=query, inputs=inputs, context_rows=context_rows)
        trigger_message = self._create_trigger_message(session=session, prompt_text=query)
        run_model = self.env["chatter.ai.run"].sudo()
        values = {
            "name": self._run_name(inputs=inputs, session=session),
            "run_id": str(uuid.uuid4()),
            "conversation_type": "private_chat",
            "task_type": "chat",
            "model": "diecut.kb.ai.session",
            "res_id": session.id if session else 0,
            "record_display_name": inputs.get("_record_name") or (session.record_name if session else "") or "OpenClaw 任务",
            "trigger_message_id": trigger_message.id,
            "requesting_partner_id": self.env.user.partner_id.id,
            "requesting_user_id": self.env.user.id,
            "prompt_html": "<p>%s</p>" % html.escape(query or ""),
            "prompt_text": prompt_text,
            "context_payload": json.dumps(context_rows, ensure_ascii=False),
            "source_attachment_ids": [(6, 0, [])],
        }
        return run_model.create(values)

    def _build_prompt_text(self, *, query, inputs, context_rows):
        system_prompt = (inputs.get("system") or "").strip()
        if system_prompt:
            lines = [
                system_prompt,
                "",
                "用户任务:",
                query or "",
            ]
        else:
            lines = [
                "你是 Odoo 里的 AI 顾问。请用简洁、专业的中文回答用户问题。",
                "这次调用来自 diecut_knowledge AI 顾问抽屉，请直接给出业务回答。",
                "",
                "用户问题:",
                query or "",
            ]
        record_context = {
            key: value
            for key, value in inputs.items()
            if value and not str(key).startswith("_") and key != "system"
        }
        if record_context:
            lines.extend(["", "当前业务记录上下文:", json.dumps(record_context, ensure_ascii=False, indent=2)])
        if context_rows:
            lines.extend(["", "近期对话:", json.dumps(context_rows, ensure_ascii=False, indent=2)])
        return "\n".join(lines)

    @staticmethod
    def _run_name(*, inputs, session):
        if inputs.get("system"):
            return "LLM Task / OpenClaw / %s" % (inputs.get("_record_name") or "global")
        return "AI Advisor / OpenClaw / %s" % (session.id if session else "global")

    def _create_trigger_message(self, *, session, prompt_text):
        subtype = self.env.ref("mail.mt_note", raise_if_not_found=False)
        vals = {
            "model": "diecut.kb.ai.session",
            "res_id": session.id if session else 0,
            "body": "<p>%s</p>" % html.escape(prompt_text or ""),
            "author_id": self.env.user.partner_id.id,
            "message_type": "comment",
        }
        if subtype:
            vals["subtype_id"] = subtype.id
        return self.env["mail.message"].sudo().create(vals)

    def _session(self, session_id):
        try:
            session_id = int(session_id or 0)
        except (TypeError, ValueError):
            return self.env["diecut.kb.ai.session"]
        if not session_id:
            return self.env["diecut.kb.ai.session"]
        return self.env["diecut.kb.ai.session"].sudo().browse(session_id).exists()

    def _context_rows(self, session):
        if not session:
            return []
        messages = session.message_ids.sorted(key=lambda message: (message.create_date, message.id))[-12:]
        rows = []
        for message in messages:
            rows.append(
                {
                    "role": message.role,
                    "content": message.content or "",
                    "date": fields.Datetime.to_string(message.create_date),
                }
            )
        return rows

    @staticmethod
    def _duration(t0):
        return int((time.monotonic() - t0) * 1000)
