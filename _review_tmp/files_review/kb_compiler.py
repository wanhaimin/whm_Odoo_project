# -*- coding: utf-8 -*-
"""知识编译器 — Karpathy LLM Knowledge Base 的 Odoo 实现

核心理念（来自 Karpathy）：
  不是把原始数据"搬运"到检索系统，而是让 LLM "编译"原始数据为
  结构化、交叉引用、持续维护的知识文章。

本编译器的职责：
  1. 从 catalog_item（结构化产品数据）自动生成 kb_article
  2. 自动填充交叉引用（关联品牌/分类/型号）
  3. 生成的文章走现有 dify_sync 管道推送到 Dify

调用入口：
  - KbCompiler(env).compile_from_item(catalog_item)   单个产品 → 文章
  - KbCompiler(env).compile_pending(limit=10)          批量编译
  - KbCompiler(env).compile_comparison(item_ids)       对比分析文章

设计原则：
  - 用 Dify Chat API 做生成（复用已有的 DifyClient + 已部署的 Dify）
  - 不抛异常，失败写 sync_log
  - 幂等：同一个 catalog_item 重复编译会更新已有文章，不创建新的
"""

import json
import logging
from datetime import datetime
from typing import Optional

from .dify_client import DifyClient

_logger = logging.getLogger(__name__)


# ── 编译 prompt 模板 ──────────────────────────────────────────────────────

_SYSTEM_PROMPT_SINGLE = """\
你是一位模切行业的资深技术专家和技术文档编写员。
你的任务是根据下面提供的产品结构化数据，撰写一篇专业、完整的知识文章。

写作要求：
1. 用中文撰写，专业但易懂
2. 文章结构：产品概述 → 核心技术参数 → 典型应用场景 → 选型建议 → 注意事项
3. 如果数据中包含多个性能参数，用表格或列表整理
4. 在文末列出关联品牌和型号，方便交叉引用
5. 输出纯 HTML 格式（<h2>/<h3>/<p>/<ul>/<li>/<table> 等），不要 markdown
6. 不要编造数据中没有的参数值
7. 如果某些参数缺失，可以在注意事项中提醒用户查阅原始 TDS

输出格式要求：
- 直接输出 HTML 正文，不要加 ```html 代码块标记
- 第一行就是 <h2> 标签开始
"""

_SYSTEM_PROMPT_COMPARISON = """\
你是一位模切行业的资深技术专家。
你的任务是对比分析下面提供的多个产品，生成一篇对比选型文章。

写作要求：
1. 用中文撰写，专业但易懂
2. 文章结构：对比概述 → 关键参数对比表 → 各产品优劣势 → 选型建议
3. 用 HTML <table> 做参数对比表
4. 重点突出产品之间的差异，帮助用户做选型决策
5. 输出纯 HTML 格式，不要 markdown
6. 不要编造数据中没有的参数值

输出格式要求：
- 直接输出 HTML 正文，不要加 ```html 代码块标记
- 第一行就是 <h2> 标签开始
"""


class KbCompiler:
    """知识编译服务。"""

    PARAM_CHAT_URL = "diecut_knowledge.dify_chat_app_url"
    PARAM_CHAT_KEY = "diecut_knowledge.dify_chat_api_key"

    # 编译生成的文章默认分类编码
    DEFAULT_CATEGORY_CODE = "material_selection"

    def __init__(self, env):
        self.env = env

    # ── public API ──────────────────────────────────────────────────────

    def compile_from_item(self, item) -> dict:
        """从单个 catalog_item 编译生成/更新一篇知识文章。

        Returns:
            {"ok": bool, "action": str, "article_id": int|False, "error": str|None}
        """
        item.ensure_one()

        # 检查配置
        client = self._build_client()
        if not client:
            return {"ok": False, "action": "noop", "article_id": False,
                    "error": "Dify Chat API 未配置（chat_app_url / chat_api_key）"}

        # 构建产品上下文
        context_text = self._build_item_context(item)
        if not context_text or len(context_text) < 20:
            return {"ok": False, "action": "skip", "article_id": False,
                    "error": f"产品 [{item.code}] 数据过少，跳过编译"}

        # 查找已有文章（幂等）
        existing = self._find_existing_article(item)

        # 调用 Dify Chat API 生成文章内容
        prompt = f"请根据以下产品数据撰写知识文章：\n\n{context_text}"
        ok, payload, error, duration = client.chat_messages(
            query=prompt,
            user=f"kb-compiler-{self.env.user.id}",
            inputs={"system": _SYSTEM_PROMPT_SINGLE},
        )

        if not ok:
            self._log_compile(item, "failed", error, duration)
            return {"ok": False, "action": "compile", "article_id": False,
                    "error": f"Dify 生成失败：{error}"}

        answer = self._clean_answer((payload or {}).get("answer", ""))
        if not answer or len(answer) < 50:
            self._log_compile(item, "failed", "AI 返回内容过短", duration)
            return {"ok": False, "action": "compile", "article_id": False,
                    "error": "AI 返回内容过短"}

        # 生成摘要（取 answer 前200字去HTML标签）
        import re
        summary_text = re.sub(r"<[^>]+>", " ", answer)
        summary_text = re.sub(r"\s+", " ", summary_text).strip()[:200]

        # 准备文章数据
        article_vals = self._build_article_vals(item, answer, summary_text)

        # 创建或更新文章
        if existing:
            existing.write(article_vals)
            article = existing
            action = "update"
        else:
            article = self.env["diecut.kb.article"].create(article_vals)
            action = "create"

        self._log_compile(item, "success",
                          f"已{('更新' if action == 'update' else '创建')}文章 [{article.name}]",
                          duration, article_id=article.id)

        return {"ok": True, "action": action, "article_id": article.id, "error": None}

    def compile_pending(self, limit: int = 10) -> dict:
        """批量编译：找 catalog_item 中还没有对应知识文章的产品。

        Returns:
            {"total": int, "ok": int, "failed": int, "skipped": int}
        """
        # 找已有文章关联的 item ids
        existing_item_ids = set()
        articles = self.env["diecut.kb.article"].search([
            ("compile_source_item_id", "!=", False),
        ])
        for art in articles:
            existing_item_ids.add(art.compile_source_item_id.id)

        # 找还没编译的、已发布的产品
        domain = [
            ("id", "not in", list(existing_item_ids)),
            ("catalog_status", "=", "published"),
            ("active", "=", True),
        ]
        items = self.env["diecut.catalog.item"].search(domain, limit=limit, order="write_date desc")

        ok_count, fail_count, skip_count = 0, 0, 0
        for item in items:
            result = self.compile_from_item(item)
            if result.get("action") == "skip":
                skip_count += 1
            elif result.get("ok"):
                ok_count += 1
            else:
                fail_count += 1

        return {"total": len(items), "ok": ok_count, "failed": fail_count, "skipped": skip_count}

    def compile_comparison(self, items) -> dict:
        """对比编译：为多个产品生成一篇对比分析文章。

        Args:
            items: catalog.item recordset (2+)

        Returns:
            {"ok": bool, "article_id": int|False, "error": str|None}
        """
        if len(items) < 2:
            return {"ok": False, "article_id": False, "error": "对比分析至少需要 2 个产品"}

        client = self._build_client()
        if not client:
            return {"ok": False, "article_id": False,
                    "error": "Dify Chat API 未配置"}

        # 构建多产品上下文
        parts = []
        for item in items:
            parts.append(f"--- 产品 {item.code or item.name} ---\n{self._build_item_context(item)}")
        context_text = "\n\n".join(parts)

        prompt = f"请对比分析以下 {len(items)} 个产品并撰写选型文章：\n\n{context_text}"
        ok, payload, error, duration = client.chat_messages(
            query=prompt,
            user=f"kb-compiler-{self.env.user.id}",
            inputs={"system": _SYSTEM_PROMPT_COMPARISON},
        )

        if not ok:
            return {"ok": False, "article_id": False, "error": f"Dify 生成失败：{error}"}

        answer = self._clean_answer((payload or {}).get("answer", ""))
        if not answer or len(answer) < 50:
            return {"ok": False, "article_id": False, "error": "AI 返回内容过短"}

        # 生成文章标题
        codes = " vs ".join(items.mapped("code") or items.mapped("name"))
        title = f"对比分析：{codes}"[:200]

        category = self._get_compile_category()
        article = self.env["diecut.kb.article"].create({
            "name": title,
            "category_id": category.id,
            "content_html": answer,
            "summary": f"对比 {len(items)} 个产品的关键参数和选型建议",
            "state": "draft",
            "sync_status": "pending",
            "compile_source": "comparison",
            "related_item_ids": [(6, 0, items.ids)],
            "related_brand_ids": [(6, 0, items.mapped("brand_id").ids)],
            "related_categ_ids": [(6, 0, items.mapped("categ_id").ids)],
            "keywords": ", ".join(filter(None, items.mapped("code"))),
        })

        return {"ok": True, "article_id": article.id, "error": None}

    # ── internal ────────────────────────────────────────────────────────

    def _build_item_context(self, item) -> str:
        """把 catalog_item 的结构化数据转为文本描述，作为 AI 输入。"""
        parts = []
        parts.append(f"产品型号：{item.code or '未知'}")
        parts.append(f"产品名称：{item.name or '未知'}")
        if item.brand_id:
            parts.append(f"品牌：{item.brand_id.name}")
        if item.series_id:
            parts.append(f"系列：{item.series_id.name}")
        if item.categ_id:
            parts.append(f"材料分类：{item.categ_id.complete_name or item.categ_id.name}")

        # 物理属性
        attrs = []
        if item.thickness:
            attrs.append(f"总厚度：{item.thickness} mm")
        if hasattr(item, "adhesive_thickness") and item.adhesive_thickness:
            attrs.append(f"胶层厚度：{item.adhesive_thickness} mm")
        if item.color_id:
            attrs.append(f"颜色：{item.color_id.name}")
        if item.adhesive_type_id:
            attrs.append(f"胶系：{item.adhesive_type_id.name}")
        if item.base_material_id:
            attrs.append(f"基材：{item.base_material_id.name}")
        if item.fire_rating:
            attrs.append(f"防火等级：{item.fire_rating}")
        certifications = []
        if item.is_rohs:
            certifications.append("RoHS")
        if item.is_reach:
            certifications.append("REACH")
        if item.is_halogen_free:
            certifications.append("无卤")
        if certifications:
            attrs.append(f"认证：{', '.join(certifications)}")
        if attrs:
            parts.append("\n基本属性：")
            parts.extend(f"  - {a}" for a in attrs)

        # 技术参数（spec_line_ids）
        spec_lines = []
        for line in item.spec_line_ids.sorted(key=lambda l: (l.sequence, l.id)):
            param = line.param_id.name or getattr(line, "param_name", "") or ""
            value = getattr(line, "value_display", "") or ""
            unit = getattr(line, "unit", "") or ""
            method = getattr(line, "test_method", "") or ""
            if param and value:
                entry = f"  - {param}：{value}"
                if unit:
                    entry += f" {unit}"
                if method:
                    entry += f"（测试方法：{method}）"
                spec_lines.append(entry)
        if spec_lines:
            parts.append("\n技术参数：")
            parts.extend(spec_lines)

        # 产品描述
        if item.product_description:
            parts.append(f"\n产品描述：{item.product_description}")
        if item.product_features:
            parts.append(f"产品特点：{item.product_features}")
        if item.main_applications:
            parts.append(f"主要应用：{item.main_applications}")
        if item.special_applications:
            parts.append(f"特殊应用：{item.special_applications}")

        # 标签
        tags = []
        for tag_field in ("function_tag_ids", "application_tag_ids", "feature_tag_ids"):
            if hasattr(item, tag_field):
                tag_records = getattr(item, tag_field, None)
                if tag_records:
                    tags.extend(tag_records.mapped("name"))
        if tags:
            parts.append(f"\n标签：{', '.join(tags)}")

        return "\n".join(parts)

    def _build_article_vals(self, item, content_html: str, summary: str) -> dict:
        """构建 kb_article 的 create/write vals。"""
        category = self._get_compile_category()
        title = f"[{item.brand_id.name or ''}] {item.code or ''} {item.name or ''}".strip()
        if not title or title == "[]":
            title = item.name or item.code or "未命名产品"

        vals = {
            "name": title[:200],
            "category_id": category.id,
            "content_html": content_html,
            "summary": summary,
            "state": "draft",
            "sync_status": "pending",
            "compile_source": "catalog_item",
            "compile_source_item_id": item.id,
            "keywords": ", ".join(filter(None, [
                item.code, item.brand_id.name if item.brand_id else "",
                item.categ_id.name if item.categ_id else "",
            ])),
            "related_brand_ids": [(6, 0, [item.brand_id.id])] if item.brand_id else False,
            "related_categ_ids": [(6, 0, [item.categ_id.id])] if item.categ_id else False,
            "related_item_ids": [(6, 0, [item.id])],
        }
        # 清除 False 值的 M2M 字段（避免覆盖）
        vals = {k: v for k, v in vals.items() if v is not False}
        return vals

    def _find_existing_article(self, item):
        """查找 catalog_item 已关联的编译文章（幂等）。"""
        return self.env["diecut.kb.article"].search([
            ("compile_source_item_id", "=", item.id),
            ("compile_source", "=", "catalog_item"),
        ], limit=1)

    def _get_compile_category(self):
        """获取编译文章的默认分类。"""
        category = self.env["diecut.kb.category"].search([
            ("code", "=", self.DEFAULT_CATEGORY_CODE),
        ], limit=1)
        if not category:
            # 尝试用第一个分类
            category = self.env["diecut.kb.category"].search([], limit=1, order="sequence")
        if not category:
            raise Exception("知识库分类为空，请先创建至少一个分类。")
        return category

    def _build_client(self) -> Optional[DifyClient]:
        """构建 Dify Chat API 客户端。"""
        icp = self.env["ir.config_parameter"].sudo()
        # Chat API 优先用专用 URL，没有就用 base_url
        base_url = (
            icp.get_param(self.PARAM_CHAT_URL)
            or icp.get_param("diecut_knowledge.dify_base_url")
        )
        api_key = icp.get_param(self.PARAM_CHAT_KEY)
        if not base_url or not api_key:
            return None
        return DifyClient(base_url=base_url, api_key=api_key, timeout=120, retries=1)

    def _clean_answer(self, answer: str) -> str:
        """清理 AI 返回的内容。"""
        import re
        text = answer or ""
        # 去掉 think 标签
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"</?think>", "", text, flags=re.IGNORECASE)
        # 去掉 markdown 代码块标记
        text = re.sub(r"^```html?\s*\n?", "", text, flags=re.MULTILINE)
        text = re.sub(r"\n?```\s*$", "", text, flags=re.MULTILINE)
        return text.strip()

    def _log_compile(self, item, state: str, message: str, duration_ms: int = 0,
                     article_id: int = False):
        """记录编译日志到 sync_log。"""
        try:
            self.env["diecut.kb.sync.log"].sudo().create({
                "article_id": article_id or False,
                "direction": "push",
                "action": "create",
                "state": "success" if state == "success" else "failed",
                "summary": f"[AI编译] {item.code or item.name}: {message}"[:500],
                "dify_dataset_id": "",
                "dify_document_id": "",
                "duration_ms": duration_ms,
                "error_message": message if state != "success" else "",
            })
        except Exception as exc:
            _logger.warning("Failed to log compile result: %s", exc)
