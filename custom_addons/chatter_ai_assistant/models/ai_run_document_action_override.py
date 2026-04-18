# -*- coding: utf-8 -*-

from odoo import api, models


class ChatterAiRunDocumentActionOverride(models.Model):
    _inherit = "chatter.ai.run"

    @api.model
    def _document_action_from_text(self, model_name, plain_text):
        text = (plain_text or "").strip().lower()
        if model_name != "diecut.catalog.source.document" or not text:
            return False
        if any(token in text for token in ("提取原文", "提取正文", "抽取原文", "extract source", "extract text")):
            return "extract_source"
        reparse_tokens = (
            "重新解析",
            "重解析",
            "重新识别",
            "重新整理",
            "重新生成草稿",
            "重新生成json",
            "重新生成json文档",
            "更新草稿",
            "覆盖草稿",
            "reparse",
        )
        revise_tokens = ("修改", "修正", "调整", "更正", "覆盖")
        revise_targets = ("草稿", "json", "识别", "结果", "参数", "规格", "文档")
        if any(token in text for token in reparse_tokens):
            return "reparse"
        if any(token in text for token in revise_tokens) and any(token in text for token in revise_targets):
            return "reparse"
        if any(token in text for token in ("总结", "摘要", "概括", "summary", "summarize")):
            return "summarize"
        if any(token in text for token in ("参数", "规格")) and any(
            token in text for token in ("提取", "抽取", "整理", "解析", "extract")
        ):
            return "extract_params"
        if any(
            token in text
            for token in ("解析", "整理", "草稿", "结构化", "parse", "analyze", "analyse")
        ):
            return "parse"
        return False
