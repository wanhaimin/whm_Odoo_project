# -*- coding: utf-8 -*-
{
    "name": "模切知识库",
    "version": "1.0",
    "category": "Manufacturing",
    "summary": "材料选型知识库（后台）",
    "author": "Diecut Team",
    "license": "LGPL-3",
    "depends": ["base", "web", "mail", "diecut"],
    "data": [
        "security/ir.model.access.csv",
        "views/kb_article_views.xml",
        "views/kb_editor_action.xml",
        "views/kb_menu.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "diecut_knowledge/static/src/scss/kb_article.scss",
            "diecut_knowledge/static/src/scss/kb_workspace.scss",
            "diecut_knowledge/static/src/js/components/page_tree.js",
            "diecut_knowledge/static/src/js/kb_workspace.js",
            "diecut_knowledge/static/src/xml/components/page_tree.xml",
            "diecut_knowledge/static/src/xml/kb_workspace.xml",
        ],
    },
    "installable": True,
    "application": False,
}
