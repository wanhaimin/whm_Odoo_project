# -*- coding: utf-8 -*-
{
    "name": "Chatter AI Assistant",
    "summary": "Bridge chatter mentions to OpenClaw",
    "version": "19.0.2.0.0",
    "category": "Productivity/Discuss",
    "author": "OpenAI Codex",
    "license": "LGPL-3",
    "depends": ["mail", "mail_bot", "base_setup", "diecut"],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron.xml",
        "data/retire_handbook_batch.xml",
        "views/chatter_ai_run_views.xml",
        "views/diecut_source_document_views.xml",
        "views/handbook_review_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "chatter_ai_assistant/static/src/js/chatter_ai_auto_refresh.js",
        ],
    },
    "installable": True,
    "application": False,
}
