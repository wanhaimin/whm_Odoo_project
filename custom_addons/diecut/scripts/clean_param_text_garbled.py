# -*- coding: utf-8 -*-
"""清洗参数字典中隐藏字段的乱码占位符（如 ???）。

用途:
1. 解决“系统里看起来正常，但 CSV->DB 校验仍报乱码”的问题。
2. 重点清理 diecut.catalog.param 的 aliases_text / parse_hint / canonical_name_*。

执行:
    进入 odoo shell 后执行本脚本内容，或通过管道方式执行。
"""

import re

from odoo.addons.diecut.tools.encoding_guard import repair_mojibake_text


def _normalize_spaces(text):
    text = re.sub(r"[ \t]+", " ", text or "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _clean_placeholder(text):
    if not text:
        return False
    fixed = repair_mojibake_text(text)
    # 常见占位噪声：连续问号、锟斤拷、替换符
    fixed = fixed.replace("锟斤拷", " ")
    fixed = fixed.replace("\ufffd", " ")
    # 180??? -> 180°（历史里常见度符号损坏）
    fixed = re.sub(r"180\?{2,}", "180°", fixed)
    # 其它连续问号移除
    fixed = re.sub(r"\?{2,}", " ", fixed)
    fixed = _normalize_spaces(fixed)
    return fixed or False


def run(env):
    Param = env["diecut.catalog.param"].sudo()
    params = Param.search([])
    touched = 0
    for p in params:
        vals = {}
        for field_name in ("aliases_text", "parse_hint", "canonical_name_zh", "canonical_name_en", "name"):
            raw = p[field_name]
            cleaned = _clean_placeholder(raw) if raw else raw
            if cleaned != raw:
                vals[field_name] = cleaned
        if vals:
            p.write(vals)
            touched += 1
    env.cr.commit()
    print("clean_param_text_garbled done:", {"touched_params": touched, "total_params": len(params)})


run(env)
