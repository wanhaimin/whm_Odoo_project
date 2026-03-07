# -*- coding: utf-8 -*-
"""
一次性迁移：将厚度标准字段 variant_thickness_std 中的单位 um 统一为 μm。

用法一（Odoo shell 内执行）:
  odoo shell -d odoo -c /etc/odoo/odoo.conf
  >>> from odoo.addons.diecut.scripts.migrate_thickness_std_um_to_unicode import run_migrate
  >>> run_migrate(env)
  >>> env.cr.commit()

用法二（--shell-file 方式）:
  odoo shell -d odoo -c /etc/odoo/odoo.conf --shell-file /mnt/extra-addons/diecut/scripts/migrate_thickness_std_um_to_unicode.py --shell-interface=python
  执行后需在 shell 中手动 env.cr.commit()
"""
import re


# 统一单位：μm = 希腊字母 μ (U+03BC) + m；µm = 微米符号 µ (U+00B5) + m
_UNIFIED_UNIT = "μm"  # 统一用希腊 μ
_MICRO_SIGN_M = "\u00b5m"  # µm (U+00B5 微米符号 + m)
_THICKNESS_UM_PATTERN = re.compile(r"^(.+)(\d)um$", re.IGNORECASE)


def _thickness_std_um_to_unicode(value):
    """将 um / µm 统一为 μm（只保留一种单位）。"""
    if not value or not isinstance(value, str):
        return value
    s = value.strip()
    # 1. 先把 µm（微米符号）统一成 μm（希腊 μ）
    if _MICRO_SIGN_M in s:
        s = s.replace(_MICRO_SIGN_M, _UNIFIED_UNIT)
    # 2. 末尾「数字+um」(ASCII) 改为 「数字+μm」
    if s.endswith("um") and not s.endswith(_UNIFIED_UNIT):
        m = _THICKNESS_UM_PATTERN.match(s)
        if m:
            s = m.group(1) + m.group(2) + _UNIFIED_UNIT
        elif s.lower() == "um":
            s = _UNIFIED_UNIT
    return s


def run_migrate(env, dry_run=False):
    """
    更新 product.product 与 diecut.catalog.item 的 variant_thickness_std：um -> μm。

    :param env: odoo.api.Environment
    :param dry_run: 若 True 只打印将改动的记录，不写库
    :return: dict 统计 { 'product_product': n, 'catalog_item': n }
    """
    stats = {"product_product": 0, "catalog_item": 0}

    # product.product（选型目录变体）
    if "variant_thickness_std" in env["product.product"]._fields:
        products = env["product.product"].search(
            [
                ("variant_thickness_std", "!=", False),
                ("variant_thickness_std", "!=", ""),
            ]
        )
        for p in products:
            new_val = _thickness_std_um_to_unicode(p.variant_thickness_std)
            if new_val != p.variant_thickness_std:
                if dry_run:
                    print(f"  product.product id={p.id} default_code={p.default_code}: {p.variant_thickness_std!r} -> {new_val!r}")
                else:
                    p.with_context(skip_shadow_sync=True).write({"variant_thickness_std": new_val})
                stats["product_product"] += 1

    # diecut.catalog.item（型号清单）
    if env.get("diecut.catalog.item") and "variant_thickness_std" in env["diecut.catalog.item"]._fields:
        items = env["diecut.catalog.item"].search(
            [
                ("code", "!=", False),
                ("variant_thickness_std", "!=", False),
                ("variant_thickness_std", "!=", ""),
            ]
        )
        for item in items:
            new_val = _thickness_std_um_to_unicode(item.variant_thickness_std)
            if new_val != item.variant_thickness_std:
                if dry_run:
                    print(f"  diecut.catalog.item id={item.id} code={item.code}: {item.variant_thickness_std!r} -> {new_val!r}")
                else:
                    item.with_context(skip_shadow_sync=True).write({"variant_thickness_std": new_val})
                stats["catalog_item"] += 1

    return stats


def post_init_hook(cr, registry):
    """模块安装后钩子：首次安装时执行一次迁移。"""
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    run_migrate(env, dry_run=False)
    cr.commit()


# 供 odoo shell --shell-file 使用（shell 会注入 env）
def main():
    if "env" not in globals():
        print("ERROR: 请在 Odoo shell 中运行，或调用 run_migrate(env)")
        return
    stats = run_migrate(env, dry_run=False)
    print("迁移完成:", stats)
    print("请执行 env.cr.commit() 提交事务。")


# shell-file 执行时自动跑
try:
    main()
except NameError:
    pass
