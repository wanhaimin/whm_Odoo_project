# -*- coding: utf-8 -*-

import base64
import json
import os
import re
import html
from io import BytesIO

from odoo import api, models
from odoo.exceptions import UserError


class DiecutCatalogSourceDocumentRuntimeOverride(models.Model):
    _inherit = "diecut.catalog.source.document"

    _AI_PROVIDER_DEFAULTS = {
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
    }

    _METHOD_SECTIONS = [
        {
            "param_key": "pluck_testing",
            "title": "Pluck Testing",
            "next_markers": ["Torque Testing", "Static Shear", "Technical Data Sheet"],
            "category": "测试验证",
        },
        {
            "param_key": "torque_testing",
            "title": "Torque Testing",
            "next_markers": ["Static Shear", "Technical Data Sheet"],
            "category": "测试验证",
        },
        {
            "param_key": "static_shear_70c",
            "title": "Static Shear",
            "next_markers": ["Technical Data Sheet"],
            "category": "可靠性",
        },
    ]

    @api.model
    def _get_ai_runtime_config(self):
        icp = self.env["ir.config_parameter"].sudo()
        provider = (
            self.env.context.get("diecut_ai_provider")
            or icp.get_param("diecut.ai_tds_provider")
            or ("openai" if (icp.get_param("diecut.ai_tds_openai_api_key") or os.getenv("OPENAI_API_KEY")) else "disabled")
        )
        defaults = self._AI_PROVIDER_DEFAULTS.get(provider or "disabled", self._AI_PROVIDER_DEFAULTS["disabled"])
        return {
            "provider": provider or "disabled",
            "api_key": self.env.context.get("diecut_ai_api_key")
            or icp.get_param("diecut.ai_tds_openai_api_key")
            or os.getenv("OPENAI_API_KEY"),
            "api_url": self.env.context.get("diecut_ai_api_url")
            or icp.get_param("diecut.ai_tds_openai_api_url")
            or os.getenv("OPENAI_API_URL")
            or defaults["api_url"],
            "model": self.env.context.get("diecut_ai_model")
            or icp.get_param("diecut.ai_tds_openai_model")
            or os.getenv("OPENAI_MODEL")
            or defaults["model"],
        }

    def _has_openai_config(self):
        config = self._get_ai_runtime_config()
        return config["provider"] in {"openai", "deepseek", "qwen"} and bool(config["api_key"])

    @api.model
    def _get_ai_provider_label(self, provider):
        return {
            "disabled": "本地增强规则",
            "openai": "OpenAI",
            "deepseek": "DeepSeek",
            "qwen": "通义千问(Qwen)",
        }.get(provider or "disabled", provider or "AI")

    def _openai_request(self, messages, max_tokens=4000, json_mode=False):
        try:
            import requests
        except ImportError as exc:
            raise UserError("当前环境未安装 requests，无法调用 AI 接口。") from exc

        config = self._get_ai_runtime_config()
        if config["provider"] not in {"openai", "deepseek", "qwen"} or not config["api_key"]:
            raise UserError("当前未配置可用的 AI 兼容接口。")

        payload = {
            "model": config["model"],
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        timeout_seconds = self.env.context.get("diecut_ai_timeout_seconds") or 240
        response = requests.post(
            config["api_url"],
            timeout=timeout_seconds,
            headers={
                "Authorization": f"Bearer {config['api_key']}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    @api.model
    def _build_ai_param_context(self, text, limit=60):
        params = self.env["diecut.catalog.param"].sudo().search([("active", "=", True)], order="sequence, id")
        cleaned_text = (text or "").lower()
        token_pool = set(re.findall(r"[a-z0-9_]+", cleaned_text))
        keyword_boosts = {
            "peel": ["peel", "adhesion", "180", "painted", "pvc"],
            "shear": ["shear", "static", "gasoline", "wax", "water", "warm"],
            "thickness": ["thickness", "mm", "liner"],
            "color": ["gray", "grey", "white", "black", "color"],
            "adhesive": ["adhesive", "acrylic", "pressure", "sensitive"],
            "base": ["foam", "core", "material", "base"],
            "storage": ["shelf", "storage", "humidity", "temperature"],
            "torque": ["torque", "twist"],
            "pluck": ["pluck"],
        }

        def _row_for_param(param):
            return {
                "param_key": param.param_key,
                "name": param.name,
                "canonical_name_zh": param.canonical_name_zh,
                "canonical_name_en": param.canonical_name_en,
                "aliases_text": param.aliases_text,
                "method_html": param.method_html,
                "value_type": param.value_type,
                "preferred_unit": param.preferred_unit or param.unit,
                "is_main_field": param.is_main_field,
                "main_field_name": param.main_field_name,
                "spec_category": param.spec_category_id.name if param.spec_category_id else False,
            }

        scored = []
        for index, param in enumerate(params):
            haystack = " ".join(
                str(value or "")
                for value in (
                    param.param_key,
                    param.name,
                    param.canonical_name_zh,
                    param.canonical_name_en,
                    param.aliases_text,
                    param.spec_category_id.name if param.spec_category_id else "",
                )
            ).lower()
            score = 0
            if param.is_main_field:
                score += 100
            if param.method_html:
                score += 5
            for bucket in keyword_boosts.values():
                if any(keyword in cleaned_text for keyword in bucket) and any(keyword in haystack for keyword in bucket):
                    score += 12
            if any(token and token in haystack for token in token_pool):
                score += 3
            if score > 0:
                scored.append((score, index, param))

        if not scored:
            return [_row_for_param(param) for param in params[:limit]]

        rows = []
        seen_ids = set()
        for _score, _index, param in sorted(scored, key=lambda item: (-item[0], item[1])):
            if param.id in seen_ids:
                continue
            rows.append(_row_for_param(param))
            seen_ids.add(param.id)
            if len(rows) >= limit:
                break
        return rows

    @api.model
    def _build_ai_text_excerpt(self, text, limit=12000):
        cleaned = self._clean_text(text) or ""
        if not cleaned:
            return ""
        lowered = cleaned.lower()
        stop_markers = [
            "regulatory information",
            "contact information",
            "technical information:",
            "warranty, limited remedy",
            "limitation of liability",
        ]
        cut = len(cleaned)
        for marker in stop_markers:
            pos = lowered.find(marker)
            if pos > 0:
                cut = min(cut, pos)
        excerpt = cleaned[:cut].strip()
        if len(excerpt) > limit:
            excerpt = excerpt[:limit].rsplit(" ", 1)[0]
        return excerpt

    @api.model
    def _build_ai_enrichment_context(self, base_payload):
        series_rows = []
        for row in (base_payload.get("series") or [])[:3]:
            series_rows.append(
                {
                    "brand_name": row.get("brand_name"),
                    "series_name": row.get("series_name") or row.get("name"),
                    "product_description": row.get("product_description"),
                    "product_features": row.get("product_features"),
                    "main_applications": row.get("main_applications"),
                }
            )
        items = []
        for row in (base_payload.get("items") or [])[:30]:
            items.append(
                {
                    "code": row.get("code"),
                    "name": row.get("name"),
                    "thickness": row.get("thickness"),
                    "thickness_std": row.get("thickness_std"),
                    "color_name": row.get("color_name") or row.get("color"),
                    "adhesive_type_name": row.get("adhesive_type_name") or row.get("adhesive_type"),
                    "base_material_name": row.get("base_material_name") or row.get("base_material"),
                }
            )
        params = []
        for row in (base_payload.get("params") or [])[:80]:
            params.append(
                {
                    "param_key": row.get("param_key"),
                    "name": row.get("name"),
                    "spec_category_name": row.get("spec_category_name") or row.get("spec_category"),
                    "preferred_unit": row.get("preferred_unit") or row.get("unit"),
                    "is_main_field": row.get("is_main_field"),
                    "main_field_name": row.get("main_field_name"),
                    "method_html": row.get("method_html") or False,
                }
            )
        return {
            "series": series_rows,
            "items": items,
            "params": params,
            "unmatched": base_payload.get("unmatched") or [],
        }

    @api.model
    def _extract_method_sections(self, text):
        cleaned = self._clean_text(text or "")
        if not cleaned:
            return {}
        lowered = cleaned.lower()
        result = {}
        for section in self._METHOD_SECTIONS:
            title = section["title"]
            marker = title.lower()
            start = lowered.find(marker)
            if start < 0:
                continue
            end = len(cleaned)
            for next_marker in section["next_markers"]:
                next_pos = lowered.find(next_marker.lower(), start + len(marker))
                if next_pos > start:
                    end = min(end, next_pos)
            section_text = cleaned[start:end].strip()
            if section_text:
                result[section["param_key"]] = {
                    "title": title,
                    "category": section["category"],
                    "text": section_text[:2400],
                }
        return result

    @api.model
    def _build_ai_method_context(self, text):
        rows = []
        for param_key, data in self._extract_method_sections(text).items():
            rows.append(
                {
                    "param_key": param_key,
                    "title": data["title"],
                    "suggested_category": data["category"],
                    "section_text": data["text"],
                }
            )
        return rows

    @api.model
    def _parse_json_loose(self, text):
        cleaned = self._strip_json_fence(text)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", cleaned, re.S)
            if match:
                return json.loads(match.group(0))
            raise

    @api.model
    def _repair_ai_json_response(self, broken_text):
        repair_prompt = (
            "你是 JSON 修复器。"
            "请把下面内容修复成一个合法 JSON 对象。"
            "不要补充解释，不要输出 Markdown，只输出修复后的 JSON。"
            "顶层 keys 必须保持为以下之一："
            "1) series, items, params, category_params, spec_values, unmatched；"
            "2) series_updates, item_updates, param_updates, category_param_updates, unmatched。"
        )
        content = self._openai_request(
            messages=[
                {"role": "system", "content": repair_prompt},
                {"role": "user", "content": broken_text or ""},
            ],
            max_tokens=8000,
            json_mode=True,
        )
        return self._strip_json_fence(content)

    @api.model
    def _merge_ai_enrichment_patch(self, base_payload, patch_payload):
        merged = json.loads(json.dumps(base_payload or {}, ensure_ascii=False))
        patch = patch_payload if isinstance(patch_payload, dict) else {}

        def _dict_rows(value):
            if isinstance(value, dict):
                return [value]
            if not isinstance(value, list):
                return []
            return [row for row in value if isinstance(row, dict)]

        series_updates = _dict_rows(patch.get("series_updates") or [])
        if merged.get("series") and series_updates:
            merged["series"][0].update({k: v for k, v in series_updates[0].items() if v not in (None, False, "")})

        item_map = {(row.get("code") or "").strip(): row for row in (merged.get("items") or []) if row.get("code")}
        for row in _dict_rows(patch.get("item_updates") or []):
            code = (row.get("code") or "").strip()
            if code and code in item_map:
                item_map[code].update({k: v for k, v in row.items() if k != "code" and v not in (None, False, "")})

        param_map = {(row.get("param_key") or "").strip(): row for row in (merged.get("params") or []) if row.get("param_key")}
        for row in _dict_rows(patch.get("param_updates") or []):
            param_key = (row.get("param_key") or "").strip()
            if param_key and param_key in param_map:
                param_map[param_key].update({k: v for k, v in row.items() if k != "param_key" and v not in (None, False, "")})

        category_rows = merged.setdefault("category_params", [])
        existing_category_keys = {
            ((row.get("categ_name") or ""), (row.get("param_key") or ""))
            for row in category_rows
            if isinstance(row, dict)
        }
        for row in _dict_rows(patch.get("category_param_updates") or []):
            key = ((row.get("categ_name") or ""), (row.get("param_key") or ""))
            if key not in existing_category_keys:
                category_rows.append(row)
                existing_category_keys.add(key)

        merged["unmatched"] = _dict_rows(patch.get("unmatched")) or merged.get("unmatched") or []
        return self._normalize_generated_payload(merged)

    @api.model
    def _infer_source_brand_name(self, text=False):
        cleaned = (self._clean_text(text) or "").lower()
        if not cleaned:
            return False
        if "3m" in cleaned:
            return "3M"
        if "tesa" in cleaned:
            return "tesa"
        return False

    @api.model
    def _normalize_um_value(self, value):
        text = self._clean_text(value)
        if not text:
            return False
        compact = text.replace(" ", "").replace("μ", "u").replace("µ", "u")
        if compact.startswith("±") or "+/-" in compact or "+-" in compact:
            return False
        match = re.search(r"(\d+(?:\.\d+)?)", compact)
        if not match:
            return False
        number = float(match.group(1))
        if number <= 0:
            return False
        if "mm" in compact.lower():
            number *= 1000.0
        if abs(number - round(number)) < 0.01:
            return f"{int(round(number))}um"
        return f"{number:.1f}".rstrip("0").rstrip(".") + "um"

    @api.model
    def _build_canonical_thickness_std(self, thickness_value):
        text = self._clean_text(thickness_value)
        if not text:
            return False
        match = re.search(r"(\d+(?:\.\d+)?)", text)
        if not match:
            return False
        number = float(match.group(1))
        if number <= 0:
            return False
        micron = int(round(number * 1000))
        return f"{micron}um"

    def _get_vision_candidate_map(self):
        self.ensure_one()
        try:
            payload = json.loads(self.vision_payload or "{}")
        except Exception:
            payload = {}
        candidate_map = {}
        for row in payload.get("candidate_items") or []:
            if isinstance(row, str):
                code = row.strip().upper()
                if code:
                    candidate_map[code] = {"code": code}
                continue
            if not isinstance(row, dict):
                continue
            code = (row.get("code") or row.get("name") or row.get("item_code") or "").strip().upper()
            if not code:
                continue
            candidate_map[code] = row
        return candidate_map

    @api.model
    def _main_field_param_keys(self):
        return {
            "thickness",
            "thickness_std",
            "color",
            "adhesive_type",
            "base_material",
        }

    def _rebuild_main_field_spec_values(self, payload):
        self.ensure_one()
        payload = self._normalize_generated_payload(payload)
        allowed_codes = {
            (row.get("code") or "").strip()
            for row in (payload.get("items") or [])
            if isinstance(row, dict) and row.get("code")
        }
        preserved_rows = []
        for row in payload.get("spec_values") or []:
            if not isinstance(row, dict):
                continue
            item_code = (row.get("item_code") or "").strip()
            if item_code and item_code not in allowed_codes:
                continue
            if (row.get("param_key") or "").strip() in self._main_field_param_keys():
                continue
            preserved_rows.append(row)

        rebuilt_rows = []
        for item in payload.get("items") or []:
            if not isinstance(item, dict):
                continue
            code = (item.get("code") or "").strip()
            if not code:
                continue
            thickness = self._clean_text(item.get("thickness"))
            if thickness:
                rebuilt_rows.append(
                    {
                        "item_code": code,
                        "param_key": "thickness",
                        "value": thickness,
                        "unit": "mm",
                        "review_status": "pending",
                        "source": "postprocess",
                    }
                )
            thickness_std = self._clean_text(item.get("thickness_std"))
            if thickness_std:
                rebuilt_rows.append(
                    {
                        "item_code": code,
                        "param_key": "thickness_std",
                        "value": thickness_std,
                        "unit": "um",
                        "review_status": "pending",
                        "source": "postprocess",
                    }
                )
            color_name = self._clean_text(item.get("color_name") or item.get("color"))
            if color_name:
                rebuilt_rows.append(
                    {
                        "item_code": code,
                        "param_key": "color",
                        "value": color_name,
                        "review_status": "pending",
                        "source": "postprocess",
                    }
                )
            adhesive_type_name = self._clean_text(item.get("adhesive_type_name") or item.get("adhesive_type"))
            if adhesive_type_name:
                rebuilt_rows.append(
                    {
                        "item_code": code,
                        "param_key": "adhesive_type",
                        "value": adhesive_type_name,
                        "review_status": "pending",
                        "source": "postprocess",
                    }
                )
            base_material_name = self._clean_text(item.get("base_material_name") or item.get("base_material"))
            if base_material_name:
                rebuilt_rows.append(
                    {
                        "item_code": code,
                        "param_key": "base_material",
                        "value": base_material_name,
                        "review_status": "pending",
                        "source": "postprocess",
                    }
                )

        payload["spec_values"] = preserved_rows + rebuilt_rows
        return payload

    def _postprocess_generated_payload(self, payload):
        self.ensure_one()
        payload = self._normalize_generated_payload(payload)
        vision_candidates = self._get_vision_candidate_map()
        allowed_codes = set(vision_candidates.keys()) if len(vision_candidates) >= 2 else set()
        inferred_brand = self.brand_id.name or self._infer_source_brand_name(self.raw_text or self.name)
        inferred_category = self.categ_id.name or False
        inferred_series = False
        if payload.get("series") and isinstance(payload["series"][0], dict):
            inferred_series = self._clean_text(payload["series"][0].get("series_name") or payload["series"][0].get("name"))

        unmatched_rows = [row for row in (payload.get("unmatched") or []) if isinstance(row, dict)]
        filtered_items = []
        for row in payload.get("items") or []:
            if not isinstance(row, dict):
                continue
            code = (row.get("code") or "").strip().upper()
            if not code:
                continue
            if allowed_codes and code not in allowed_codes:
                unmatched_rows.append(
                    {
                        "excerpt": code,
                        "reason": "已被视觉候选型号过滤，疑似 OCR/结构化误识别",
                    }
                )
                continue
            candidate = vision_candidates.get(code, {})
            row["code"] = code
            row["name"] = self._clean_text(row.get("name")) or code
            row["brand_name"] = self._clean_text(row.get("brand_name")) or inferred_brand or False
            row["category_name"] = self._clean_text(row.get("category_name")) or inferred_category or False
            row["series_name"] = self._clean_text(row.get("series_name")) or inferred_series or False
            if candidate.get("thickness") and not self._clean_text(row.get("thickness")):
                row["thickness"] = candidate.get("thickness")
            row["thickness"] = self._clean_text(row.get("thickness")) or False
            normalized_std = self._normalize_um_value(row.get("thickness_std"))
            if not normalized_std and row.get("thickness"):
                normalized_std = self._build_canonical_thickness_std(row.get("thickness"))
            row["thickness_std"] = normalized_std or False
            row["color_name"] = self._clean_text(row.get("color_name") or row.get("color")) or False
            row["adhesive_type_name"] = self._clean_text(row.get("adhesive_type_name") or row.get("adhesive_type")) or False
            row["base_material_name"] = self._clean_text(row.get("base_material_name") or row.get("base_material")) or False
            filtered_items.append(row)

        payload["items"] = filtered_items
        for row in payload.get("series") or []:
            if not isinstance(row, dict):
                continue
            row["brand_name"] = self._clean_text(row.get("brand_name")) or inferred_brand or False
            row["series_name"] = self._clean_text(row.get("series_name") or row.get("name")) or inferred_series or False
            row["name"] = self._clean_text(row.get("name")) or row.get("series_name") or inferred_series or False

        param_name_map = {}
        for row in payload.get("params") or []:
            if not isinstance(row, dict):
                continue
            param_key = (row.get("param_key") or "").strip()
            if not param_key:
                continue
            param_name_map[param_key] = self._clean_text(row.get("name") or row.get("canonical_name_zh")) or False

        for row in payload.get("category_params") or []:
            if not isinstance(row, dict):
                continue
            param_key = (row.get("param_key") or "").strip()
            row["categ_name"] = self._clean_text(row.get("categ_name") or row.get("category_name")) or inferred_category or False
            if param_key and not self._clean_text(row.get("param_name")):
                row["param_name"] = param_name_map.get(param_key) or False

        payload["unmatched"] = unmatched_rows
        return self._rebuild_main_field_spec_values(payload)

    @api.model
    def _build_method_card_html(self, title, section_text):
        summary = ""
        if hasattr(super(), "_extract_summary_sentence"):
            try:
                summary = super()._extract_summary_sentence(section_text)
            except Exception:
                summary = ""
        if hasattr(super(), "_build_method_html"):
            try:
                return super()._build_method_html(title, section_text, summary)
            except Exception:
                pass
        lines = [line.strip() for line in (section_text or "").split("\n") if line.strip()]
        parts = [f"<h4>{html.escape(title)}</h4>"]
        if summary:
            parts.append(f"<p>{html.escape(summary)}</p>")
        if lines:
            parts.append("<ul>%s</ul>" % "".join(f"<li>{html.escape(line)}</li>" for line in lines[:8]))
        return "".join(parts)

    def _inject_detected_method_cards(self, payload, text):
        payload = self._normalize_generated_payload(payload)
        method_sections = self._extract_method_sections(text)
        if not method_sections:
            return payload

        method_meta = {
            "pluck_testing": {"name": "拔脱测试", "category": "测试验证", "value_type": "char", "preferred_unit": False},
            "torque_testing": {"name": "扭矩测试", "category": "测试验证", "value_type": "char", "preferred_unit": False},
            "static_shear_70c": {"name": "70℃静态剪切", "category": "可靠性", "value_type": "char", "preferred_unit": "hour"},
        }
        param_rows = payload.setdefault("params", [])
        param_map = {
            (row.get("param_key") or "").strip(): row
            for row in param_rows
            if isinstance(row, dict) and row.get("param_key")
        }
        category_rows = payload.setdefault("category_params", [])
        existing_category_keys = {
            ((row.get("categ_name") or row.get("category_name") or ""), (row.get("param_key") or ""))
            for row in category_rows
            if isinstance(row, dict)
        }
        categ_name = self.categ_id.name if self.categ_id else False

        for param_key, section in method_sections.items():
            meta = method_meta.get(param_key)
            if not meta:
                continue
            method_html = self._build_method_card_html(meta["name"], section["text"])
            summary = self._extract_summary_sentence(section["text"]) or False
            row = param_map.get(param_key)
            if row:
                row.setdefault("name", meta["name"])
                row.setdefault("spec_category_name", meta["category"])
                row.setdefault("value_type", meta["value_type"])
                row.setdefault("description", summary)
                row.setdefault("canonical_name_zh", meta["name"])
                row.setdefault("canonical_name_en", section["title"])
                row.setdefault("aliases_text", section["title"])
                if meta["preferred_unit"]:
                    row.setdefault("preferred_unit", meta["preferred_unit"])
                    row.setdefault("unit", meta["preferred_unit"])
                if not row.get("method_html"):
                    row["method_html"] = method_html
            else:
                new_row = {
                    "param_key": param_key,
                    "name": meta["name"],
                    "spec_category_name": meta["category"],
                    "value_type": meta["value_type"],
                    "description": summary,
                    "canonical_name_zh": meta["name"],
                    "canonical_name_en": section["title"],
                    "aliases_text": section["title"],
                    "preferred_unit": meta["preferred_unit"] or False,
                    "unit": meta["preferred_unit"] or False,
                    "method_html": method_html,
                    "candidate_new": True,
                }
                param_rows.append(new_row)
                param_map[param_key] = new_row

            if categ_name:
                key = (categ_name, param_key)
                if key not in existing_category_keys:
                    category_rows.append(
                        {
                            "categ_name": categ_name,
                            "param_key": param_key,
                            "name": meta["name"],
                            "required": False,
                            "show_in_form": True,
                            "allow_import": True,
                        }
                    )
                    existing_category_keys.add(key)
        return payload

    @api.model
    def _render_pdf_method_image_map(self, payload_bytes, filename=False):
        try:
            import pypdfium2 as pdfium
            from PIL import Image
        except ImportError:
            return {}

        method_images = {}
        pdf = pdfium.PdfDocument(payload_bytes)
        try:
            for page_index in range(len(pdf)):
                page = pdf[page_index]
                textpage = page.get_textpage()
                page_width, page_height = page.get_size()
                headings = []
                for section in self._METHOD_SECTIONS:
                    search = textpage.search(section["title"])
                    found = search.get_next()
                    search.close()
                    if not found:
                        continue
                    start, count = found
                    rect_count = textpage.count_rects(start, count)
                    if not rect_count:
                        continue
                    rects = [textpage.get_rect(i) for i in range(rect_count)]
                    left = min(rect[0] for rect in rects)
                    bottom = min(rect[1] for rect in rects)
                    right = max(rect[2] for rect in rects)
                    top = max(rect[3] for rect in rects)
                    headings.append(
                        {
                            "param_key": section["param_key"],
                            "left": left,
                            "bottom": bottom,
                            "right": right,
                            "top": top,
                        }
                    )
                if not headings:
                    continue

                headings.sort(key=lambda item: item["top"], reverse=True)
                image = page.render(scale=2).to_pil()
                img_width, img_height = image.size
                scale_y = img_height / float(page_height or 1)

                for idx, heading in enumerate(headings):
                    next_heading = headings[idx + 1] if idx + 1 < len(headings) else None
                    top_px = max(0, int((page_height - heading["top"]) * scale_y) - 50)
                    if next_heading:
                        bottom_px = int((page_height - next_heading["top"]) * scale_y) - 20
                    else:
                        bottom_px = img_height - 20
                    bottom_px = max(top_px + 160, min(img_height, bottom_px))
                    crop_left = 20
                    crop_right = max(crop_left + 200, img_width - 20)
                    cropped = image.crop((crop_left, top_px, crop_right, bottom_px))
                    buffer = BytesIO()
                    cropped.save(buffer, format="JPEG", quality=90)
                    encoded = base64.b64encode(buffer.getvalue())
                    base_name = os.path.splitext(filename or "source")[0]
                    method_images[heading["param_key"]] = {
                        "image": encoded,
                        "filename": f"{base_name}_{heading['param_key']}.jpg",
                    }
                image.close()
        finally:
            pdf.close()
        return method_images

    def _get_pdf_source_bytes(self):
        self.ensure_one()
        attachment = self._get_effective_primary_attachment()
        if attachment:
            payload_bytes = self._read_attachment_bytes(attachment)
            if payload_bytes and (
                (attachment.mimetype or "") == "application/pdf"
                or (attachment.name or "").lower().endswith(".pdf")
            ):
                return payload_bytes, attachment.name
        if self.source_file and (self.source_filename or "").lower().endswith(".pdf"):
            return self._decode_binary_field(self.source_file), self.source_filename
        return b"", False

    def _extract_and_apply_method_images(self, param_keys=None):
        self.ensure_one()
        payload_bytes, filename = self._get_pdf_source_bytes()
        if not payload_bytes:
            return {}
        image_map = self._render_pdf_method_image_map(payload_bytes, filename)
        if not image_map:
            return {}
        keys = set(param_keys or image_map.keys())
        params = self.env["diecut.catalog.param"].sudo().search([("param_key", "in", list(keys))])
        for param in params:
            data = image_map.get(param.param_key)
            if not data:
                continue
            vals = {}
            if not param.method_image:
                vals["method_image"] = data["image"]
            if not param.method_image_filename:
                vals["method_image_filename"] = data["filename"]
            if vals:
                param.write(vals)
        return image_map

    def _generate_draft_with_openai(self):
        self.ensure_one()
        text = self._clean_text(self.raw_text)
        if not text:
            raise UserError("请先提取原文，再生成 AI 草稿。")

        config = self._get_ai_runtime_config()
        base_payload, heuristic_version = self._generate_draft_heuristic()
        text_excerpt = self._build_ai_text_excerpt(text)
        prompt = (
            "你是 Odoo 材料系统的 TDS 精修引擎。"
            "系统已经先用规则抽取出基础草稿，你只负责在此基础上做精修，不要重做整份表格数值。"
            "你必须只输出一个合法 JSON 对象，不允许输出 Markdown、解释或多余文本。"
            "顶层 keys 必须严格为：series_updates, item_updates, param_updates, category_param_updates, unmatched。"
            "series_updates 只放系列摘要、产品描述、产品特点、主要应用等文本修正。"
            "item_updates 只按 code 输出需要修正的型号主字段，如颜色、胶系、基材、厚度。"
            "param_updates 只按 param_key 输出参数中文名、分类、单位、method_html 等修正。"
            "如果文档包含测试图表、图例说明、测试步骤、判读口径，请优先补充到 method_html。"
            "method_html 必须输出为简洁 HTML，可包含 <p><ul><li><strong>，不要塞整页原文。"
            "category_param_updates 只补充确实应该启用但草稿遗漏的分类参数。"
            "unmatched 只放仍无法确定映射的内容片段。"
            "不要输出 spec_values，不要重复返回整份基础草稿。"
        )
        content = self._openai_request(
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
                            "param_dictionary": self._build_ai_param_context(text_excerpt, limit=40),
                            "detected_method_sections": self._build_ai_method_context(text_excerpt),
                            "heuristic_draft": self._build_ai_enrichment_context(base_payload),
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            max_tokens=5000,
            json_mode=True,
        )
        cleaned = self._strip_json_fence(content)
        try:
            patch_payload = self._parse_json_loose(cleaned)
        except json.JSONDecodeError:
            patch_payload = self._parse_json_loose(self._repair_ai_json_response(cleaned))
        payload = self._merge_ai_enrichment_patch(base_payload, patch_payload)
        payload = self._inject_detected_method_cards(payload, text_excerpt)
        payload = self._postprocess_generated_payload(payload)
        return payload, f"ai-v1:{config['model']}+{heuristic_version}"

    def action_generate_draft(self):
        for record in self:
            if not record.raw_text:
                record.action_extract_source()
            if not record.raw_text:
                raise UserError("未提取到原文，无法生成草稿。")
            if record._has_openai_config():
                payload, parse_version = record._generate_draft_with_openai()
                config = record._get_ai_runtime_config()
                provider_label = record._get_ai_provider_label(config["provider"])
                message = f"AI 草稿已生成。当前引擎：{provider_label} / {config['model']}"
            else:
                payload, parse_version = record._generate_draft_heuristic()
                message = "未检测到 AI 配置，已使用本地增强规则生成草稿，请人工复核。"
            payload = record._postprocess_generated_payload(payload)
            record._run_encoding_precheck(payload)
            record.write(
                {
                    "draft_payload": json.dumps(payload, ensure_ascii=False, indent=2),
                    "unmatched_payload": json.dumps(payload.get("unmatched") or [], ensure_ascii=False, indent=2),
                    "parse_version": parse_version,
                    "import_status": "generated",
                    "result_message": message,
                }
            )
        return True
