# -*- coding: utf-8 -*-
"""批量将参数字典名称中文化，并同步型号参数行显示名。

用法（容器内）:
    odoo shell -d odoo --db_host=db --db_user=odoo --db_password=odoo < /mnt/extra-addons/diecut/scripts/normalize_param_display_zh.py

说明:
1. 仅更新本脚本 MAPPING 中定义的 param_key。
2. 会同步更新 `diecut.catalog.item.spec.line.param_name`，保证界面立即可读。
3. 可选将 BT3005 核心字典值切到中文（颜色/胶系/基材）。
"""

from odoo import api, SUPERUSER_ID


MAPPING = {
    "liner_material": ("离型材料", "Liner Material"),
    "shelf_life": ("保质期", "Shelf Life"),
    "adhesion_surface_note": ("粘接面说明", "Adhesion Surface Note"),
    "peel_180_headliner_immediate": ("180°剥离-顶棚-即刻", "180 Peel Headliner Immediate"),
    "peel_180_headliner_initial": ("180°剥离-顶棚-初始", "180 Peel Headliner Initial"),
    "peel_180_headliner_normal": ("180°剥离-顶棚-常态", "180 Peel Headliner Normal"),
    "peel_180_headliner_high_temp": ("180°剥离-顶棚-高温", "180 Peel Headliner High Temp"),
    "peel_180_headliner_heat_aging": ("180°剥离-顶棚-热老化", "180 Peel Headliner Heat Aging"),
    "peel_180_headliner_humidity_aging": ("180°剥离-顶棚-湿热老化", "180 Peel Headliner Humidity Aging"),
    "peel_180_painted_panel_initial": ("180°剥离-喷涂板-初始", "180 Peel Painted Panel Initial"),
    "peel_180_painted_panel_normal": ("180°剥离-喷涂板-常态", "180 Peel Painted Panel Normal"),
    "peel_180_pp_initial": ("180°剥离-PP-初始", "180 Peel PP Initial"),
    "peel_180_pp_normal": ("180°剥离-PP-常态", "180 Peel PP Normal"),
}


CORE_TAXONOMY_ZH = {
    "color": "浅蓝色",
    "adhesive_type": "丙烯酸压敏胶",
    "base_material": "无纺布",
}


def _merge_aliases(existing_text, values):
    rows = [x.strip() for x in (existing_text or "").replace("\r", "\n").split("\n") if x.strip()]
    for value in values:
        text = (value or "").strip()
        if text and text not in rows:
            rows.append(text)
    return "\n".join(rows) if rows else False


def run(env):
    Param = env["diecut.catalog.param"].sudo()
    Line = env["diecut.catalog.item.spec.line"].sudo()
    Item = env["diecut.catalog.item"].sudo()
    Color = env["diecut.color"].sudo()
    Adhesive = env["diecut.catalog.adhesive.type"].sudo()
    BaseMaterial = env["diecut.catalog.base.material"].sudo()

    updated_params = 0
    updated_lines = 0

    for param_key, (zh_name, en_name) in MAPPING.items():
        param = Param.search([("param_key", "=", param_key)], limit=1)
        if not param:
            continue
        param.write(
            {
                "name": zh_name,
                "canonical_name_zh": zh_name,
                "canonical_name_en": en_name,
                "aliases_text": _merge_aliases(param.aliases_text, [zh_name, en_name]),
            }
        )
        updated_params += 1

        lines = Line.search([("param_id", "=", param.id)])
        if lines:
            lines.write({"param_name": zh_name})
            updated_lines += len(lines)

    # 可选：把 BT3005 的核心 many2one 字典统一到中文值
    color = Color.search([("name", "=", CORE_TAXONOMY_ZH["color"])], limit=1) or Color.create({"name": CORE_TAXONOMY_ZH["color"]})
    adhesive = (
        Adhesive.search([("name", "=", CORE_TAXONOMY_ZH["adhesive_type"])], limit=1)
        or Adhesive.create({"name": CORE_TAXONOMY_ZH["adhesive_type"]})
    )
    base = (
        BaseMaterial.search([("name", "=", CORE_TAXONOMY_ZH["base_material"])], limit=1)
        or BaseMaterial.create({"name": CORE_TAXONOMY_ZH["base_material"]})
    )
    bt3005_items = Item.search([("code", "=", "BT3005")])
    if bt3005_items:
        bt3005_items.write(
            {
                "color_id": color.id,
                "adhesive_type_id": adhesive.id,
                "base_material_id": base.id,
            }
        )

    env.cr.commit()
    print(
        "normalize_param_display_zh done:",
        {
            "updated_params": updated_params,
            "updated_lines": updated_lines,
            "bt3005_count": len(bt3005_items),
        },
    )


run(env)

