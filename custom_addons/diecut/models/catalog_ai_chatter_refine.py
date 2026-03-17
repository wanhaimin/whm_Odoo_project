# -*- coding: utf-8 -*-

import json
import logging
import re
import threading
from html import unescape

from odoo import SUPERUSER_ID, api, fields, models
from odoo.exceptions import UserError
from odoo.modules.registry import Registry

_logger = logging.getLogger(__name__)

class DiecutCatalogSourceDocumentChatterRefine(models.Model):
    _inherit = "diecut.catalog.source.document"

    draft_prev_payload = fields.Text(string="上一版草稿", copy=False)
    draft_revision_count = fields.Integer(string="草稿修订次数", default=0, copy=False)
    last_revision_instruction = fields.Text(string="最近修订指令", copy=False)
    ai_refine_in_progress = fields.Boolean(string="AI修订中", default=False, copy=False, readonly=True)

    _REFINE_DEFAULT_ALIASES = "@AI修订,@AI,@Copilot,@TDS助手"
    _QA_DEFAULT_ALIASES = "@AI问答,@AI回答"
    _REFINE_ALLOWED_STATUS = {"generated", "review", "validated"}

    def _is_ai_mode_auto_enabled(self):
        raw_value = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("diecut.ai_mode_auto_enabled", default="true")
        )
        return str(raw_value or "").strip().lower() not in {"0", "false", "no", "off"}

    def _get_refine_aliases(self):
        raw_value = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("diecut.ai_refine_aliases", default=self._REFINE_DEFAULT_ALIASES)
        )
        configured = [chunk.strip() for chunk in str(raw_value or "").split(",") if chunk.strip()]
        defaults = [x.strip() for x in self._REFINE_DEFAULT_ALIASES.split(",") if x.strip()]
        merged = []
        seen = set()
        for alias in configured + defaults:
            key = alias.lower()
            if key in seen:
                continue
            seen.add(key)
            merged.append(alias)
        return merged or defaults

    def _get_qa_aliases(self):
        raw_value = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("diecut.ai_qa_aliases", default=self._QA_DEFAULT_ALIASES)
        )
        configured = [chunk.strip() for chunk in str(raw_value or "").split(",") if chunk.strip()]
        defaults = [x.strip() for x in self._QA_DEFAULT_ALIASES.split(",") if x.strip()]
        merged = []
        seen = set()
        for alias in configured + defaults:
            key = alias.lower()
            if key in seen:
                continue
            seen.add(key)
            merged.append(alias)
        return merged or defaults

    def _get_qa_reply_lang(self):
        raw_value = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("diecut.ai_qa_reply_lang", default="zh")
        )
        value = str(raw_value or "").strip().lower()
        return value if value in {"zh", "en", "auto"} else "zh"

    def _resolve_ai_partner_id(self, key, default_xmlid):
        value = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(key, default=default_xmlid)
        )
        value = str(value or "").strip()
        if not value:
            return False
        if value.isdigit():
            return int(value)
        record = self.env.ref(value, raise_if_not_found=False)
        return record.id if record and record._name == "res.partner" else False

    def _get_ai_mode_partner_ids(self):
        return {
            "qa": self._resolve_ai_partner_id("diecut.ai_mode_qa_partner_xmlid", "diecut.partner_ai_qa"),
            "refine": self._resolve_ai_partner_id("diecut.ai_mode_refine_partner_xmlid", "diecut.partner_ai_refine"),
        }

    @staticmethod
    def _clean_html_message(body):
        text = unescape(str(body or ""))
        text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
        text = re.sub(r"</p\s*>", "\n", text, flags=re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    @staticmethod
    def _alias_pattern(alias):
        escaped = re.escape(str(alias or "").strip())
        if not escaped:
            return None
        return re.compile(rf"(?<!\S){escaped}(?![\w\u4e00-\u9fff])", flags=re.I)

    def _extract_instruction_from_message(self, body, aliases):
        text = self._clean_html_message(body)
        if not text:
            return ""

        matched_aliases = []
        for alias in sorted((aliases or []), key=lambda item: len(str(item or "")), reverse=True):
            pattern = self._alias_pattern(alias)
            if pattern and pattern.search(text):
                matched_aliases.append((alias, pattern))
        if not matched_aliases:
            return ""

        instruction = text
        for _alias, pattern in matched_aliases:
            instruction = pattern.sub(" ", instruction)
        instruction = re.sub(r"^[\s:：,，。.-]+", "", instruction).strip()
        return instruction

    @staticmethod
    def _extract_mentioned_partner_ids(body):
        text = str(body or "")
        matches = re.findall(
            r"data-oe-model=['\"]res\.partner['\"][^>]*data-oe-id=['\"](\d+)['\"]",
            text,
            flags=re.I,
        )
        values = {int(value) for value in matches if str(value).isdigit()}
        link_matches = re.findall(r"/odoo/res\.partner/(\d+)", text, flags=re.I)
        values |= {int(value) for value in link_matches if str(value).isdigit()}
        return values

    @staticmethod
    def _extract_partner_ids_from_kwargs(kwargs):
        values = set()
        partner_ids = kwargs.get("partner_ids") or []
        if isinstance(partner_ids, int):
            return {partner_ids}
        if isinstance(partner_ids, (list, tuple)):
            for entry in partner_ids:
                if isinstance(entry, int):
                    values.add(entry)
                    continue
                if isinstance(entry, (list, tuple)) and len(entry) >= 3:
                    command = entry[0]
                    payload = entry[2]
                    if command in (4, 6):
                        if isinstance(payload, int):
                            values.add(payload)
                        elif isinstance(payload, (list, tuple)):
                            for pid in payload:
                                if isinstance(pid, int):
                                    values.add(pid)
        return values

    def _extract_refine_instruction_from_message(self, body):
        return self._extract_instruction_from_message(body, self._get_refine_aliases())

    def _extract_qa_instruction_from_message(self, body):
        return self._extract_instruction_from_message(body, self._get_qa_aliases())

    def _load_context_snapshot(self):
        self.ensure_one()
        try:
            context_used = json.loads(self.context_used or "{}")
            return context_used if isinstance(context_used, dict) else {}
        except Exception:
            return {}

    def _load_current_draft_payload(self):
        self.ensure_one()
        if hasattr(self, "_load_draft_payload"):
            return self._load_draft_payload()
        try:
            payload = json.loads(self.draft_payload or "{}")
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}

    def _normalize_refined_payload(self, payload):
        self.ensure_one()
        if hasattr(self, "_normalize_generated_payload"):
            return self._normalize_generated_payload(payload)
        if not isinstance(payload, dict):
            payload = {}
        for bucket in ("series", "items", "params", "category_params", "spec_values", "unmatched"):
            if not isinstance(payload.get(bucket), list):
                payload[bucket] = []
        return payload

    def _refine_draft_with_openai(self, instruction, current_payload):
        self.ensure_one()
        if not hasattr(self, "_has_openai_config") or not self._has_openai_config():
            raise UserError("未检测到 AI 配置，暂不能使用 @AI 自动修订。")
        config = self._get_ai_runtime_config()
        if not hasattr(self, "_openai_request") or not hasattr(self, "_strip_json_fence"):
            raise UserError("当前模型未加载 AI 修订能力，请联系管理员。")

        system_prompt = (
            "你是 Odoo 材料库草稿修订助手。"
            "必须基于用户指令对现有草稿做增量修订。"
            "不要整份重写；只改用户明确要求的部分，其余保持不变。"
            "输出必须是严格 JSON，顶层仅允许："
            "series, items, params, category_params, spec_values, unmatched。"
            "不得输出 JSON 之外的解释文本。"
            "如不确定，保留原值或放入 unmatched 并写 reason。"
        )
        user_payload = {
            "title": self.name,
            "brand_name": self.brand_id.name if self.brand_id else False,
            "category_name": self.categ_id.name if self.categ_id else False,
            "instruction": instruction,
            "raw_text": self.raw_text or "",
            "current_draft": current_payload or {},
            "context_used": self._load_context_snapshot(),
        }
        request_kwargs = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
            "max_tokens": 5500,
        }
        content, route = self._request_ai_content(
            request_kwargs["messages"],
            max_tokens=request_kwargs["max_tokens"],
            json_mode=True,
        )
        refined = json.loads(self._strip_json_fence(content))
        normalized = self._normalize_refined_payload(refined)
        route_tag = "qwen-fallback" if route == "qwen_fallback" else "primary"
        return normalized, f"refine-v1:{config.get('model') or 'unknown'}:{route_tag}"

    def _build_qwen_fallback_context(self):
        icp = self.env["ir.config_parameter"].sudo()
        struct_provider = (icp.get_param("diecut.ai_tds_struct_provider", default="") or "").strip().lower()
        default_api_url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
        default_model = "qwen3.5-plus"
        api_key = (
            icp.get_param("diecut.ai_qwen_fallback_api_key", default="")
            or icp.get_param("diecut.ai_tds_openai_api_key", default="")
            or icp.get_param("diecut.ai_tds_struct_api_key", default="")
            or ""
        ).strip()
        if not api_key:
            return {}
        api_url = (
            icp.get_param("diecut.ai_qwen_fallback_api_url", default="")
            or icp.get_param("diecut.ai_tds_struct_api_url", default="")
            or icp.get_param("diecut.ai_tds_openai_api_url", default="")
            or default_api_url
        ).strip() or default_api_url
        model = (
            icp.get_param("diecut.ai_qwen_fallback_model", default="")
            or icp.get_param("diecut.ai_tds_struct_model", default="")
            or icp.get_param("diecut.ai_tds_openai_model", default="")
            or default_model
        ).strip() or default_model
        if "qwen" not in model.lower():
            model = default_model
        return {
            "diecut_ai_provider": "qwen",
            "diecut_ai_api_key": api_key,
            "diecut_ai_api_url": api_url,
            "diecut_ai_model": model,
            "diecut_ai_struct_provider": "qwen",
            "diecut_ai_struct_api_key": api_key,
            "diecut_ai_struct_api_url": api_url,
            "diecut_ai_struct_model": model,
            "diecut_ai_timeout_seconds": 90,
        }

    def _request_ai_content(self, messages, max_tokens=1600, json_mode=False):
        self.ensure_one()

        def _invoke(runner):
            try:
                return runner._openai_request(
                    messages=messages,
                    max_tokens=max_tokens,
                    json_mode=json_mode,
                )
            except TypeError:
                return runner._openai_request(messages, max_tokens=max_tokens)

        last_error = None
        try:
            primary_runner = self.with_context(diecut_ai_timeout_seconds=90)
            primary_content = str(_invoke(primary_runner) or "").strip()
            if primary_content:
                return primary_content, "primary"
            last_error = UserError("主通道返回空内容。")
        except Exception as exc:
            last_error = exc

        current_provider = ""
        if hasattr(self, "_get_ai_runtime_config"):
            try:
                current_provider = str((self._get_ai_runtime_config() or {}).get("provider") or "").strip().lower()
            except Exception:
                current_provider = ""

        qwen_ctx = self._build_qwen_fallback_context()
        if qwen_ctx and current_provider != "qwen":
            try:
                qwen_runner = self.with_context(**qwen_ctx)
                qwen_content = str(_invoke(qwen_runner) or "").strip()
                if qwen_content:
                    return qwen_content, "qwen_fallback"
            except Exception as qwen_exc:
                raise UserError(
                    "主通道调用失败，且 Qwen 3.5 回退也失败："
                    f"{str(last_error)[:180]} / {str(qwen_exc)[:180]}"
                ) from qwen_exc
            raise UserError(f"主通道调用失败，且 Qwen 3.5 回退返回空内容：{str(last_error)[:180]}")

        raise UserError(f"AI 调用失败：{str(last_error)[:240]}")

    @staticmethod
    def _bucket_rows(value):
        return value if isinstance(value, list) else []

    @staticmethod
    def _instruction_allows_deletion(instruction):
        lowered = str(instruction or "").lower()
        delete_tokens = ["删除", "清空", "移除", "delete", "remove", "clear", "drop"]
        return any(token in lowered for token in delete_tokens)

    def _apply_refine_safety_guard(self, old_payload, refined_payload, instruction):
        safe_payload = dict(refined_payload or {})
        allow_delete = self._instruction_allows_deletion(instruction)
        protected_buckets = ("series", "items", "params", "category_params", "spec_values")
        for bucket in protected_buckets:
            old_rows = self._bucket_rows((old_payload or {}).get(bucket))
            new_rows = self._bucket_rows((safe_payload or {}).get(bucket))
            if old_rows and not new_rows and not allow_delete:
                safe_payload[bucket] = old_rows
        return safe_payload

    def _build_refine_diff_summary(self, old_payload, new_payload):
        buckets = ("series", "items", "params", "category_params", "spec_values", "unmatched")
        summary = {}
        for bucket in buckets:
            old_rows = self._bucket_rows((old_payload or {}).get(bucket))
            new_rows = self._bucket_rows((new_payload or {}).get(bucket))
            summary[bucket] = {
                "old": len(old_rows),
                "new": len(new_rows),
                "delta": len(new_rows) - len(old_rows),
            }
        return summary

    def _post_ai_message(self, body):
        self.ensure_one()
        self.sudo().with_context(skip_ai_refine_feedback=True).message_post(
            body=body,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )

    def _build_qa_messages(self, instruction):
        self.ensure_one()
        lang = self._get_qa_reply_lang()
        lang_rule = {
            "zh": "默认使用中文回答，必要时可保留英文术语原词。",
            "en": "默认使用英文回答。",
            "auto": "跟随用户提问语言回答。",
        }[lang]
        system_prompt = (
            "你是 Odoo 材料库助手。"
            "当前处于问答模式，只需要回答问题，不要修改任何草稿字段。"
            f"{lang_rule}"
        )
        user_payload = {
            "question": instruction,
            "document_context": {
                "title": self.name,
                "brand_name": self.brand_id.name if self.brand_id else "",
                "category_name": self.categ_id.name if self.categ_id else "",
                "attachment_name": self.primary_attachment_name or self.source_filename or "",
            },
            "raw_text_excerpt": (self.raw_text or "")[:12000],
            "draft_payload_excerpt": (self.draft_payload or "")[:8000],
        }
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ]

    @staticmethod
    def _collect_raw_text_lines(raw_text, max_lines=80):
        lines = []
        for chunk in str(raw_text or "").splitlines():
            text = chunk.strip()
            if not text:
                continue
            # Skip noisy page markers / separators.
            if text.startswith("====") or text.lower().startswith("page "):
                continue
            lines.append(text)
            if len(lines) >= max_lines:
                break
        return lines

    def _build_local_qa_fallback(self, question):
        question_text = str(question or "").strip().lower()
        lines = self._collect_raw_text_lines(self.raw_text, max_lines=180)
        if not lines:
            return "当前文档暂无可用原文内容。请先执行“提取原文”后再提问。"

        def pick_by_keywords(keywords, limit=5):
            hits = []
            for line in lines:
                lowered = line.lower()
                if any(keyword in lowered for keyword in keywords):
                    hits.append(line)
                if len(hits) >= limit:
                    break
            return hits

        app_keywords = [
            "application", "applications", "recommended use", "end use", "usage",
            "应用", "用途", "使用场景", "适用", "适用于",
        ]
        feature_keywords = [
            "feature", "features", "benefit", "advantages", "performance", "property",
            "特性", "特点", "优势", "性能", "参数",
        ]
        method_keywords = [
            "method", "test", "condition", "procedure",
            "方法", "测试", "条件", "试验",
        ]

        if any(token in question_text for token in ["应用", "用途", "application", "use"]):
            app_hits = pick_by_keywords(app_keywords, limit=6)
            if app_hits:
                return "根据当前原文，可能的主要应用如下：\n- " + "\n- ".join(app_hits[:4])
            return "当前原文里未明确出现“主要应用”标题。我建议检查第一页的描述段落，通常会包含应用场景。"

        if any(token in question_text for token in ["特性", "特点", "优势", "feature", "benefit"]):
            feature_hits = pick_by_keywords(feature_keywords, limit=6)
            if feature_hits:
                return "根据当前原文，可能的产品特性如下：\n- " + "\n- ".join(feature_hits[:4])
            return "当前原文里未找到明确的特性段落标题。可以让我改问法：例如“提取这份TDS的关键参数和卖点”。"

        if any(token in question_text for token in ["方法", "测试", "条件", "method", "test", "condition"]):
            method_hits = pick_by_keywords(method_keywords, limit=6)
            if method_hits:
                return "根据当前原文，相关测试/方法信息如下：\n- " + "\n- ".join(method_hits[:4])
            return "当前原文里未检索到明显的测试方法段落。建议先查看“视觉中间结果”中的 methods 区块。"

        # Generic fallback: concise summary from the first few meaningful lines.
        summary_lines = lines[:3]
        return "AI服务暂不可用，先基于原文给出摘要：\n- " + "\n- ".join(summary_lines)

    def _auto_qa_reply_from_instruction(self, instruction):
        self.ensure_one()
        question = (instruction or "").strip()
        if not question:
            self._post_ai_message("❌ @AI问答 失败：请提供问题内容。")
            return
        self._post_ai_message(f"@AI问答 已收到问题，开始回答：{question[:120]}")
        try:
            if not hasattr(self, "_has_openai_config") or not self._has_openai_config():
                raise UserError("未检测到 AI 配置，暂不能使用 @AI问答。")
            if not hasattr(self, "_openai_request"):
                raise UserError("当前模型未加载 AI 问答能力，请联系管理员。")
            answer_text, route = self._request_ai_content(
                self._build_qa_messages(question),
                max_tokens=1600,
                json_mode=False,
            )
            if not answer_text:
                fallback_text = self._build_local_qa_fallback(question)
                self._post_ai_message(f"⚠️ @AI问答 AI未返回内容，已降级为原文回答：<br/>{fallback_text[:6000]}")
                return
            route_note = "（Qwen 3.5 回退）" if route == "qwen_fallback" else ""
            self._post_ai_message(f"✅ @AI问答 回复{route_note}：<br/>{answer_text[:6000]}")
        except Exception as exc:
            _logger.exception("AI chatter QA failed for doc %s", self.id)
            fallback_text = self._build_local_qa_fallback(question)
            self._post_ai_message(
                "⚠️ @AI问答 AI服务异常，已降级为原文回答："
                f"<br/>异常：{str(exc)[:200]}"
                f"<br/>{fallback_text[:6000]}"
            )

    def _auto_refine_draft_from_instruction(self, instruction):
        self.ensure_one()
        _logger.info(
            "AI chatter refine start doc_id=%s status=%s has_raw=%s has_draft=%s",
            self.id,
            self.import_status,
            bool((self.raw_text or "").strip()),
            bool((self.draft_payload or "").strip()),
        )
        if self.import_status not in self._REFINE_ALLOWED_STATUS:
            self._post_ai_message(
                f"@AI 已收到指令，但当前状态为“{self.import_status}”，仅在 generated/review/validated 状态下自动修订。"
            )
            return
        if self.ai_refine_in_progress:
            self._post_ai_message("@AI 正在处理上一条修订指令，请稍后再试。")
            return
        if not (self.raw_text or "").strip():
            self._post_ai_message("@AI 修订失败：原文为空，请先提取原文。")
            return
        if not (self.draft_payload or "").strip():
            self._post_ai_message("@AI 修订失败：当前无草稿，请先执行“AI生成草稿”。")
            return

        old_payload = self._load_current_draft_payload()
        self.write({"ai_refine_in_progress": True})
        self._post_ai_message(f"@AI 已收到修订指令，开始处理：{instruction[:120]}")
        try:
            refined_payload, refine_version = self._refine_draft_with_openai(instruction, old_payload)
            if hasattr(self, "_run_encoding_precheck"):
                self._run_encoding_precheck(refined_payload)

            refined_payload = self._apply_refine_safety_guard(old_payload, refined_payload, instruction)
            diff_summary = self._build_refine_diff_summary(old_payload, refined_payload)
            revision_no = (self.draft_revision_count or 0) + 1
            parse_version = f"{(self.parse_version or 'draft-v1').strip()}+refine-v1-r{revision_no}"
            result_message = (
                f"AI 对话修订完成（第 {revision_no} 次）。"
                f"instruction={instruction[:160]}; "
                f"diff={json.dumps(diff_summary, ensure_ascii=False)}; "
                f"runtime={refine_version}"
            )
            self.write(
                {
                    "draft_prev_payload": json.dumps(old_payload, ensure_ascii=False, indent=2),
                    "draft_payload": json.dumps(refined_payload, ensure_ascii=False, indent=2),
                    "unmatched_payload": json.dumps(refined_payload.get("unmatched") or [], ensure_ascii=False, indent=2),
                    "draft_revision_count": revision_no,
                    "last_revision_instruction": instruction,
                    "parse_version": parse_version,
                    "result_message": result_message,
                }
            )
            self._post_ai_message(
                "✅ @AI 修订完成。"
                f"<br/>修订次数：{revision_no}"
                f"<br/>指令：{instruction[:200]}"
                f"<br/>变更摘要：{json.dumps(diff_summary, ensure_ascii=False)}"
            )
            _logger.info("AI chatter refine success doc_id=%s revision_no=%s", self.id, revision_no)
        except Exception as exc:
            _logger.exception("AI chatter refine failed for doc %s", self.id)
            self._post_ai_message(f"❌ @AI 修订失败：{str(exc)[:300]}（已保留原草稿）")
        finally:
            self.write({"ai_refine_in_progress": False})
            _logger.info("AI chatter refine end doc_id=%s", self.id)

    def _trigger_refine_from_message_body(self, message_body):
        self.ensure_one()
        if not self._is_ai_mode_auto_enabled():
            return False
        instruction = self._extract_refine_instruction_from_message(message_body)
        if not instruction:
            return False
        self._auto_refine_draft_from_instruction(instruction)
        return True

    @api.model
    def _run_refine_async(self, dbname, doc_id, instruction):
        def _job():
            try:
                with Registry(dbname).cursor() as cr:
                    env = api.Environment(cr, SUPERUSER_ID, {})
                    doc = env["diecut.catalog.source.document"].browse(doc_id).exists()
                    if not doc:
                        return
                    doc._auto_refine_draft_from_instruction(instruction)
                    cr.commit()
            except Exception:
                _logger.exception("AI chatter refine async worker failed doc_id=%s", doc_id)

        thread = threading.Thread(
            target=_job,
            name=f"diecut_ai_refine_{doc_id}",
            daemon=True,
        )
        thread.start()

    @api.model
    def _run_qa_async(self, dbname, doc_id, instruction):
        def _job():
            try:
                with Registry(dbname).cursor() as cr:
                    env = api.Environment(cr, SUPERUSER_ID, {})
                    doc = env["diecut.catalog.source.document"].browse(doc_id).exists()
                    if not doc:
                        return
                    doc._auto_qa_reply_from_instruction(instruction)
                    cr.commit()
            except Exception:
                _logger.exception("AI chatter QA async worker failed doc_id=%s", doc_id)

        thread = threading.Thread(
            target=_job,
            name=f"diecut_ai_qa_{doc_id}",
            daemon=True,
        )
        thread.start()

    def message_post(self, **kwargs):
        message = super().message_post(**kwargs)
        if self.env.context.get("skip_ai_refine_feedback"):
            return message
        if not self:
            return message
        if len(self) != 1:
            return message
        try:
            if kwargs.get("message_type") not in (None, "comment"):
                return message
            if not self._is_ai_mode_auto_enabled():
                return message
            body = kwargs.get("body") or ""
            doc_id = self.id
            dbname = self.env.cr.dbname
            mentioned_partner_ids = self._extract_mentioned_partner_ids(body)
            mentioned_partner_ids |= self._extract_partner_ids_from_kwargs(kwargs)
            partner_ids = self._get_ai_mode_partner_ids()
            mention_refine = bool(partner_ids["refine"] and partner_ids["refine"] in mentioned_partner_ids)
            mention_qa = bool(partner_ids["qa"] and partner_ids["qa"] in mentioned_partner_ids)

            fallback_refine_instruction = self._extract_refine_instruction_from_message(body)
            fallback_qa_instruction = self._extract_qa_instruction_from_message(body)

            if mention_refine and mention_qa:
                self._post_ai_message("❌ 请一次只提及一个 AI 角色：`@AI修订` 或 `@AI问答`。")
                return message
            if mention_refine:
                instruction = fallback_refine_instruction or self._clean_html_message(body)
                if not (instruction or "").strip():
                    self._post_ai_message("❌ @AI修订 失败：请在消息中写明修订指令。")
                    return message
                self.sudo().write({"last_revision_instruction": instruction[:1000]})
                self._run_refine_async(dbname, doc_id, instruction)
                _logger.info("AI chatter refine async queued doc_id=%s instruction=%s", doc_id, instruction[:120])
                return message

            if mention_qa:
                instruction = fallback_qa_instruction or self._clean_html_message(body)
                if not (instruction or "").strip():
                    self._post_ai_message("❌ @AI问答 失败：请在消息中写明问题。")
                    return message
                self._run_qa_async(dbname, doc_id, instruction)
                _logger.info("AI chatter QA async queued doc_id=%s instruction=%s", doc_id, instruction[:120])
                return message

            if fallback_refine_instruction and fallback_qa_instruction:
                self._post_ai_message("❌ 检测到问答/修订双指令，请拆成两条消息发送。")
                return message

            if fallback_refine_instruction:
                instruction = fallback_refine_instruction
                if not (instruction or "").strip():
                    self._post_ai_message("❌ @AI修订 失败：请在消息中写明修订指令。")
                    return message
                self.sudo().write({"last_revision_instruction": instruction[:1000]})
                self._run_refine_async(dbname, doc_id, instruction)
                _logger.info("AI chatter refine async queued doc_id=%s instruction=%s", doc_id, instruction[:120])
                return message

            if fallback_qa_instruction:
                instruction = fallback_qa_instruction
                if not (instruction or "").strip():
                    self._post_ai_message("❌ @AI问答 失败：请在消息中写明问题。")
                    return message
                self._run_qa_async(dbname, doc_id, instruction)
                _logger.info("AI chatter QA async queued doc_id=%s instruction=%s", doc_id, instruction[:120])
        except Exception:
            _logger.exception("AI chatter refine message_post hook failed for doc_id=%s", self.id)
        return message


class MailMessageAiRefineHook(models.Model):
    _inherit = "mail.message"

    @api.model_create_multi
    def create(self, vals_list):
        return super().create(vals_list)
