# -*- coding: utf-8 -*-

import base64
import html
import json
import os
import re

from odoo import api, fields, models
from odoo.exceptions import UserError


class DiecutCatalogSourceDocumentDualRuntime(models.Model):
    _inherit = "diecut.catalog.source.document"

    vision_payload = fields.Text(string="视觉中间结果")
    vision_summary = fields.Text(string="视觉摘要", compute="_compute_vision_summary")

    _ROLE_DEFAULTS = {
        "vision": {
            "disabled": {"api_url": "", "model": ""},
            "openai": {
                "api_url": "https://api.openai.com/v1/chat/completions",
                "model": "gpt-4.1-mini",
            },
            "deepseek": {
                "api_url": "https://api.deepseek.com/chat/completions",
                "model": "deepseek-chat",
            },
            "qwen": {
                "api_url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
                "model": "qwen-vl-max-latest",
            },
        },
        "struct": {
            "disabled": {"api_url": "", "model": ""},
            "openai": {
                "api_url": "https://api.openai.com/v1/chat/completions",
                "model": "gpt-4.1-mini",
            },
            "deepseek": {
                "api_url": "https://api.deepseek.com/chat/completions",
                "model": "deepseek-chat",
            },
            "qwen": {
                "api_url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
                "model": "qwen3.5-plus",
            },
        },
    }

    @api.depends("vision_payload")
    def _compute_vision_summary(self):
        for record in self:
            try:
                payload = json.loads(record.vision_payload or "{}")
            except Exception:
                payload = {}
            blocks = len(payload.get("sections") or [])
            tables = len(payload.get("tables") or [])
            charts = len(payload.get("charts") or [])
            methods = len(payload.get("methods") or [])
            items = len(payload.get("candidate_items") or [])
            record.vision_summary = (
                f"段落块 {blocks}，表格块 {tables}，图表块 {charts}，方法块 {methods}，候选型号 {items}"
                if payload
                else ""
            )

    @api.model
    def _render_skill_context_text(self, copilot_context):
        bundle = (copilot_context or {}).get("skill_bundle") or {}
        parts = []
        if copilot_context.get("skills_loaded"):
            parts.append("Skills: " + ", ".join(copilot_context["skills_loaded"]))
        if bundle.get("task_instructions"):
            parts.append("Task:\n- " + "\n- ".join(bundle["task_instructions"][:5]))
        if bundle.get("brand_or_domain_conventions"):
            parts.append("Conventions:\n- " + "\n- ".join(bundle["brand_or_domain_conventions"][:5]))
        if bundle.get("table_patterns"):
            parts.append("Table patterns:\n- " + "\n- ".join(bundle["table_patterns"][:4]))
        if bundle.get("method_patterns"):
            parts.append("Method patterns:\n- " + "\n- ".join(bundle["method_patterns"][:6]))
        if bundle.get("negative_rules"):
            parts.append("Negative rules:\n- " + "\n- ".join(bundle["negative_rules"][:4]))
        return "\n\n".join(parts)

    @api.model
    def _get_role_defaults(self, role, provider):
        return dict(self._ROLE_DEFAULTS.get(role, {}).get(provider or "disabled", {"api_url": "", "model": ""}))

    @api.model
    def _get_ai_provider_label(self, provider):
        return {
            "disabled": "本地增强规则",
            "openai": "OpenAI",
            "deepseek": "DeepSeek",
            "qwen": "通义千问(Qwen)",
        }.get(provider or "disabled", provider or "AI")

    @api.model
    def _get_ai_role_config(self, role):
        icp = self.env["ir.config_parameter"].sudo()
        old_provider = icp.get_param("diecut.ai_tds_provider", default="disabled")
        old_api_key = icp.get_param("diecut.ai_tds_openai_api_key", default="") or os.getenv("OPENAI_API_KEY")
        old_api_url = icp.get_param("diecut.ai_tds_openai_api_url", default="") or os.getenv("OPENAI_API_URL")
        old_model = icp.get_param("diecut.ai_tds_openai_model", default="") or os.getenv("OPENAI_MODEL")

        provider = (
            self.env.context.get(f"diecut_ai_{role}_provider")
            or icp.get_param(f"diecut.ai_tds_{role}_provider")
            or old_provider
            or ("qwen" if old_api_key else "disabled")
        )
        defaults = self._get_role_defaults(role, provider)
        return {
            "provider": provider or "disabled",
            "api_key": (
                self.env.context.get(f"diecut_ai_{role}_api_key")
                or icp.get_param(f"diecut.ai_tds_{role}_api_key")
                or old_api_key
                or ""
            ),
            "api_url": (
                self.env.context.get(f"diecut_ai_{role}_api_url")
                or icp.get_param(f"diecut.ai_tds_{role}_api_url")
                or old_api_url
                or defaults["api_url"]
            ),
            "model": (
                self.env.context.get(f"diecut_ai_{role}_model")
                or icp.get_param(f"diecut.ai_tds_{role}_model")
                or (old_model if role == "struct" else "")
                or defaults["model"]
            ),
        }

    @api.model
    def _get_ai_runtime_config(self):
        return self._get_ai_role_config("struct")

    def _has_openai_config(self):
        return bool(self._get_ai_role_config("struct").get("api_key"))

    def _has_ai_role_config(self, role):
        config = self._get_ai_role_config(role)
        return config["provider"] != "disabled" and bool(config["api_key"])

    def _openai_request(self, messages, max_tokens=4000, json_mode=False):
        return self._ai_request("struct", messages, max_tokens=max_tokens, json_mode=json_mode)

    def _ai_request(self, role, messages, max_tokens=4000, json_mode=False):
        try:
            import requests
        except ImportError as exc:
            raise UserError("当前环境未安装 requests，无法调用 AI 接口。") from exc

        config = self._get_ai_role_config(role)
        if config["provider"] == "disabled" or not config["api_key"]:
            raise UserError(f"{'视觉模型' if role == 'vision' else '结构化模型'}未配置可用的 AI 接口。")

        payload = {
            "model": config["model"],
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        response = requests.post(
            config["api_url"],
            timeout=self.env.context.get("diecut_ai_timeout_seconds") or 240,
            headers={
                "Authorization": f"Bearer {config['api_key']}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    def _build_vision_messages(self, source_bytes, filename, text_excerpt):
        copilot_context = self._build_copilot_context()
        mime = "image/png"
        if (filename or "").lower().endswith(".pdf"):
            mime = "image/jpeg"
        elif "." in (filename or ""):
            import mimetypes

            mime = mimetypes.guess_type(filename or "")[0] or "image/png"
        data_url = f"data:{mime};base64,{base64.b64encode(source_bytes).decode()}"
        prompt = (
            "你是 TDS 视觉解析器。请阅读图片或 PDF 预览，输出严格 JSON。"
            "顶层 keys 必须为：sections, tables, charts, methods, candidate_items。"
            "sections 用于产品描述/特性/应用等段落；tables 用于物性和型号矩阵；charts 用于图表标题、图例、坐标轴和结论；"
            "methods 用于测试方法区块；candidate_items 用于识别到的型号/厚度候选。不要输出 JSON 以外的任何内容。"
        )
        return [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"原文摘录：{text_excerpt[:3000]}"},
                    {
                        "type": "text",
                        "text": "Copilot 上下文：\n%s" % self._render_skill_context_text(copilot_context),
                    },
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            },
        ]

    def _generate_vision_payload(self, source_bytes=False, filename=False):
        self.ensure_one()
        if not self._has_ai_role_config("vision"):
            return {}
        payload_bytes = source_bytes
        payload_name = filename
        if not payload_bytes:
            attachment = self._get_effective_primary_attachment()
            if attachment:
                payload_bytes = self._read_attachment_bytes(attachment)
                payload_name = attachment.name
        if not payload_bytes and self.source_file:
            payload_bytes = self._decode_binary_field(self.source_file)
            payload_name = self.source_filename or self.name
        if not payload_bytes:
            return {}

        if (payload_name or "").lower().endswith(".pdf"):
            preview, preview_name = self._extract_pdf_preview_image(payload_bytes, payload_name)
            payload_bytes = base64.b64decode(preview or b"") if preview else payload_bytes
            payload_name = preview_name or payload_name
        content = self._ai_request(
            "vision",
            self._build_vision_messages(payload_bytes, payload_name, self.raw_text or ""),
            max_tokens=2500,
            json_mode=True,
        )
        try:
            return self._parse_json_loose(self._strip_json_fence(content))
        except Exception:
            return {"raw": content}

    def _extract_source_payload(self):
        payload = super()._extract_source_payload()
        copilot_context = self._build_copilot_context()
        vision_payload = {}
        try:
            if payload.get("source_type") in {"pdf", "ocr"}:
                vision_payload = self._generate_vision_payload()
        except Exception as exc:
            result = payload.get("result_message") or ""
            payload["result_message"] = (result + f"\n视觉解析失败：{exc}").strip()
        if vision_payload:
            payload["vision_payload"] = json.dumps(vision_payload, ensure_ascii=False, indent=2)
            payload["result_message"] = ((payload.get("result_message") or "").rstrip() + "\n视觉解析完成。").strip()
            payload["parse_version"] = "extract-v2"
        payload["skill_profile"] = copilot_context.get("skill_profile")
        payload["brand_skill_name"] = copilot_context.get("brand_skill")
        payload["context_used"] = json.dumps(copilot_context, ensure_ascii=False, indent=2)
        return payload

    @api.model
    def _render_source_mark(self, source):
        return {
            "vision": "视觉解析",
            "struct": "结构化模型",
            "heuristic": "本地规则",
        }.get(source or "", source or "")

    def _build_ai_enrichment_context(self, base_payload):
        context = super()._build_ai_enrichment_context(base_payload)
        try:
            vision_payload = json.loads(self.vision_payload or "{}")
        except Exception:
            vision_payload = {}
        context["vision_payload"] = vision_payload
        return context

    @api.model
    def _preview_columns_for_bucket(self, bucket):
        mapping = {
            "series": [
                ("brand_name", "品牌"),
                ("series_name", "系列"),
                ("name", "系列标题"),
                ("product_description", "产品描述"),
                ("source", "来源"),
            ],
            "items": [
                ("brand_name", "品牌"),
                ("code", "型号"),
                ("thickness", "厚度"),
                ("color_name", "颜色"),
                ("base_material_name", "基材"),
                ("source", "来源"),
            ],
            "params": [
                ("param_key", "参数键"),
                ("name", "参数名称"),
                ("spec_category_name", "参数分类"),
                ("preferred_unit", "单位"),
                ("route_label", "写入位置"),
                ("source", "来源"),
            ],
            "category_params": [
                ("categ_name", "材料分类"),
                ("param_key", "参数键"),
                ("name", "参数名称"),
                ("required", "必填"),
                ("allow_import", "允许导入"),
                ("source", "来源"),
            ],
            "spec_values": [
                ("item_code", "型号"),
                ("param_name", "参数"),
                ("display_value", "值"),
                ("unit", "单位"),
                ("test_condition", "测试条件"),
                ("source", "来源"),
            ],
            "unmatched": [
                ("excerpt", "未识别内容"),
                ("reason", "原因"),
                ("candidate_param_key", "候选参数键"),
            ],
        }
        return mapping.get(bucket) or super()._preview_columns_for_bucket(bucket)

    @api.model
    def _preview_value(self, bucket, row, column):
        if column == "source":
            return self._render_source_mark((row or {}).get("source")) if isinstance(row, dict) else ""
        if isinstance(row, dict) and bucket == "params" and column in {"preferred_unit", "unit"}:
            value = row.get(column)
            return "" if value in (False, None, "", "false", "False", "none", "None", "null", "Null") else value
        return super()._preview_value(bucket, row, column)

    def _generate_draft_with_openai(self):
        self.ensure_one()
        text = self._clean_text(self.raw_text)
        if not text:
            raise UserError("请先提取原文，再生成 AI 草稿。")

        base_payload, heuristic_version = self._generate_draft_heuristic()
        copilot_context = self._build_copilot_context(base_payload)
        if not self.vision_payload and self._has_ai_role_config("vision"):
            try:
                vision_payload = self._generate_vision_payload()
                if vision_payload:
                    self.write({"vision_payload": json.dumps(vision_payload, ensure_ascii=False, indent=2)})
            except Exception:
                pass
        text_excerpt = self._build_ai_text_excerpt(text)
        struct_config = self._get_ai_role_config("struct")
        vision_config = self._get_ai_role_config("vision")
        prompt = (
            "你是 Odoo 材料系统的 TDS 结构化引擎。系统已经使用本地规则生成了基础草稿，并给出了视觉中间结果。"
            "你只负责精修，不要重做整份数值表。"
            "请严格输出一个 JSON 对象，顶层 keys 只能是：series_updates, item_updates, param_updates, category_param_updates, unmatched。"
            "series_updates 只补产品描述、产品特性、主要应用等。"
            "item_updates 只按 code 输出需要修正的主字段。"
            "param_updates 只按 param_key 输出参数中文名、分类、单位、method_html 等修正。"
            "category_param_updates 只补漏掉的分类参数。"
            "unmatched 只放仍无法确定映射的内容。"
            "不要输出 spec_values，不要重复输出完整草稿，不要输出 Markdown。"
        )
        content = self._ai_request(
            "struct",
            messages=[
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "title": self.name,
                            "brand_name": self.brand_id.name if self.brand_id else False,
                            "category_name": self.categ_id.name if self.categ_id else False,
                            "source_text_excerpt": text_excerpt,
                            "copilot_context": {
                                "skill_profile": copilot_context.get("skill_profile"),
                                "brand_skill": copilot_context.get("brand_skill"),
                                "skills_loaded": copilot_context.get("skills_loaded"),
                                "source_context": copilot_context.get("source_context"),
                                "main_field_whitelist": copilot_context.get("main_field_whitelist"),
                                "category_param_snapshot": copilot_context.get("category_param_snapshot"),
                                "skill_bundle": copilot_context.get("skill_bundle"),
                            },
                            "param_dictionary": self._build_ai_param_context(text_excerpt, limit=40),
                            "detected_method_sections": self._build_ai_method_context(text_excerpt),
                            "vision_payload": json.loads(self.vision_payload or "{}") if self.vision_payload else {},
                            "heuristic_draft": self._build_ai_enrichment_context(base_payload),
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            max_tokens=6000,
            json_mode=True,
        )
        cleaned = self._strip_json_fence(content)
        try:
            patch_payload = self._parse_json_loose(cleaned)
        except json.JSONDecodeError:
            patch_payload = self._parse_json_loose(self._repair_ai_json_response(cleaned))
        payload = self._merge_ai_enrichment_patch(base_payload, patch_payload)
        payload = self._inject_detected_method_cards(payload, text_excerpt)
        if hasattr(self, "_postprocess_generated_payload"):
            payload = self._postprocess_generated_payload(payload)

        if self.vision_payload:
            try:
                vision_payload = json.loads(self.vision_payload or "{}")
            except Exception:
                vision_payload = {}
            for bucket_name, source_name in (
                ("series", "struct"),
                ("items", "struct"),
                ("params", "struct"),
                ("category_params", "struct"),
                ("spec_values", "heuristic"),
            ):
                for row in payload.get(bucket_name) or []:
                    if isinstance(row, dict) and "source" not in row:
                        row["source"] = source_name
            for row in (vision_payload.get("methods") or []):
                if isinstance(row, dict):
                    row.setdefault("source", "vision")
        parse_version = f"vision:{vision_config['model']} + struct:{struct_config['model']} + {heuristic_version}"
        return payload, parse_version

    def action_generate_draft(self):
        for record in self:
            if not record.raw_text:
                record.action_extract_source()
            if not record.raw_text:
                raise UserError("未提取到原文，无法生成草稿。")
            if record._has_ai_role_config("struct"):
                payload, parse_version = record._generate_draft_with_openai()
                vision_config = record._get_ai_role_config("vision")
                struct_config = record._get_ai_role_config("struct")
                message = (
                    "AI 草稿已生成。\n"
                    f"视觉模型：{record._get_ai_provider_label(vision_config['provider'])} / {vision_config['model']}\n"
                    f"结构化模型：{record._get_ai_provider_label(struct_config['provider'])} / {struct_config['model']}"
                )
            else:
                payload, parse_version = record._generate_draft_heuristic()
                message = "未检测到结构化模型配置，已回退到本地增强规则生成草稿，请人工复核。"
            if hasattr(record, "_postprocess_generated_payload"):
                payload = record._postprocess_generated_payload(payload)
            record._run_encoding_precheck(payload)
            record.write(
                {
                    "draft_payload": json.dumps(payload, ensure_ascii=False, indent=2),
                    "unmatched_payload": json.dumps(payload.get("unmatched") or [], ensure_ascii=False, indent=2),
                    "parse_version": parse_version,
                    "import_status": "generated",
                    "result_message": message,
                    "skill_profile": (record.skill_profile or "generic_tds_v1+diecut_domain_v1").strip(),
                    "brand_skill_name": record._resolve_brand_skill_name(),
                    "context_used": json.dumps(record._build_copilot_context(payload), ensure_ascii=False, indent=2),
                }
            )
        return True
