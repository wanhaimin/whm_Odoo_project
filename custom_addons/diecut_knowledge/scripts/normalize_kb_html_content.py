# -*- coding: utf-8 -*-

import re


def _clean_style_declaration(style_text):
    parts = [part.strip() for part in (style_text or "").split(";") if part.strip()]
    kept = []
    for part in parts:
        low = part.lower().replace(" ", "")
        if low.startswith("width:") or low.startswith("max-width:") or low.startswith("min-width:") or low.startswith("float:"):
            continue
        kept.append(part)
    return "; ".join(kept)


def _replace_style_attr(match):
    quote = match.group(1)
    style_text = match.group(2)
    cleaned = _clean_style_declaration(style_text)
    if not cleaned:
        return ""
    return f" style={quote}{cleaned}{quote}"


Article = env["diecut.kb.article"].with_context(active_test=False)
records = Article.search([("content_html", "!=", False)])
updated = 0

for rec in records:
    html = rec.content_html or ""
    normalized = re.sub(r"\sstyle=(\"|')(.*?)(\1)", _replace_style_attr, html, flags=re.I | re.S)
    normalized = re.sub(r"\s(width|height)=(\"|')[^\"']*(\2)", "", normalized, flags=re.I)
    if normalized != html:
        rec.write({"content_html": normalized})
        updated += 1

print(f"[diecut_knowledge] normalized content_html rows: {updated}/{len(records)}")
