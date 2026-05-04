# -*- coding: utf-8 -*-
{
    "name": "模切行业知识库",
    "version": "2.0.0",
    "category": "Manufacturing",
    "summary": "材料选型 / 模切工艺 / 刀模设计 / 行业标准 / 客户问答 知识库，支持同步到 Dify 做 AI 检索",
    "description": """
模切行业知识库
================

将公司沉淀的行业知识（材料选型、模切工艺、刀模设计、行业标准、客户问答）
作为结构化数据管理在 Odoo 中，并自动同步到 Dify 知识库，
为销售/技术/客服提供统一的 AI 智能问答入口。

主要模型：
- diecut.kb.category   知识分类
- diecut.kb.article    知识文章（主表）
- diecut.kb.attachment 关联附件 + 解析状态
- diecut.kb.sync.log   同步日志
""",
    "author": "Diecut Team",
    "license": "LGPL-3",
    "depends": ["base", "web", "mail", "diecut", "chatter_ai_assistant"],
    "data": [
        "security/ir.model.access.csv",
        "data/kb_category_data.xml",
        "data/kb_compile_rule_data.xml",
        "data/kb_compile_rule_schema_data.xml",
        "data/ir_cron.xml",
        "data/ir_asset_ai_advisor.xml",
        "views/kb_category_views.xml",
        "views/kb_article_views.xml",
        "views/kb_wiki_link_views.xml",
        "views/kb_wiki_log_views.xml",
        "views/kb_citation_views.xml",
        "views/kb_compile_rule_views.xml",
        "views/llm_model_profile_views.xml",
        "views/kb_ai_session_views.xml",
        "views/kb_wiki_graph_views.xml",
        "views/kb_attachment_views.xml",
        "views/kb_qa_ticket_views.xml",
        "views/kb_lint_log_views.xml",
        "views/kb_sync_log_views.xml",
        "views/catalog_item_views.xml",
        "views/source_document_compile_views.xml",
        "views/res_config_settings_views.xml",
        "views/kb_dashboard_views.xml",
        "views/kb_compile_job_views.xml",
        "views/kb_menu.xml",
    ],
    "external_dependencies": {
        "python": ["requests", "pdfplumber"],
    },
    "installable": True,
    "application": False,
}
