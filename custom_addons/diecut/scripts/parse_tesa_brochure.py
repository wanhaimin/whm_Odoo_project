# -*- coding: utf-8 -*-
"""从德莎行业解决方案手册中提取系列与型号。

默认输入:
  custom_addons/diecut/scripts/tesa_tds_pdfs/德莎电子行业胶带解决方案.pdf

输出:
  custom_addons/diecut/scripts/tesa_brochure_series.csv
  custom_addons/diecut/scripts/tesa_brochure_variants.csv
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

try:
    import pdfplumber
except ImportError as exc:  # pragma: no cover
    raise SystemExit("请先安装 pdfplumber: pip install pdfplumber") from exc


SCRIPT_DIR = Path(__file__).parent.resolve()
DEFAULT_INPUT_PDF = SCRIPT_DIR / "tesa_tds_pdfs" / "德莎电子行业胶带解决方案.pdf"
DEFAULT_SERIES_OUT = SCRIPT_DIR / "tesa_brochure_series.csv"
DEFAULT_VARIANTS_OUT = SCRIPT_DIR / "tesa_brochure_variants.csv"

COLOR_CANDIDATES = [
    "哑光黑色/自然黑色",
    "白色半透明",
    "黑色,白色,半透明",
    "黑色,白色",
    "黑色,白色",
    "黑色,白色",
    "哑光黑色",
    "自然黑色",
    "浅褐色",
    "半透明",
    "琥珀色",
    "橙色",
    "灰色",
    "黑色",
    "白色",
    "透明",
]

ADHESIVE_CANDIDATES = [
    "黑色改性丙烯酸",
    "生物基丙烯酸",
    "导电结构胶",
    "导电丙烯酸",
    "合成橡胶",
    "硅胶/丙烯酸",
    "改性丙烯酸",
    "丁腈橡胶/酚醛树脂",
    "交联聚氨酯",
    "热塑性聚氨酯",
    "光固化",
    "UV固化",
    "特殊结构",
    "特殊",
    "丙烯酸",
    "PSA",
]

BASE_CANDIDATES = [
    "消费后回收再利用PET",
    "PE泡棉,有PET加强膜",
    "织布,无纺布",
    "织布,铜箔",
    "软泡棉",
    "超软泡棉",
    "缓冲泡棉",
    "无纺布",
    "无基材",
    "消费后回收再利用PET",
    "PET",
    "PI",
    "PU",
    "铜箔",
    "PE泡棉",
    "丙烯酸",
    "-",
]

TYPE_A_STOP_LABELS = [
    "颜色", "胶系", "基材", "类型", "特性", "厚度", "参比产品", "剥离力", "推出力", "DuPont", "动态剪切力",
    "接触电阻", "表面电阻", "屏蔽效能", "回弹力", "恢复率", "透光率", "雾度", "折射率", "间隙填补", "介电常数",
    "储存模量", "WVTR", "阻隔延迟时间", "测试板材", "分类概览", "典型应用", "产品性能", "产品特性",
]


def model_to_series(model: str) -> tuple[str, str]:
    """和 scrape_tesa.py 保持一致的系列映射规则。"""
    series_prefix_map: dict[str, tuple[str, str]] = {
        "626": ("catalog_tesa_6262x", "6262x"),
        "628": ("catalog_tesa_628xx", "628xx"),
        "666": ("catalog_tesa_666xx", "666xx"),
        "668": ("catalog_tesa_668xx", "668xx"),
        "754": ("catalog_tesa_754xx", "754xx/756xx"),
        "756": ("catalog_tesa_754xx", "754xx/756xx"),
        "757": ("catalog_tesa_757xx", "757xx"),
        "758": ("catalog_tesa_758xx", "758xx"),
        "759": ("catalog_tesa_759xx", "759xx"),
        "751": ("catalog_tesa_751xx", "751xx"),
        "761": ("catalog_tesa_761xx", "761xx"),
        "471": ("catalog_tesa_471x", "471x"),
        "473": ("catalog_tesa_473x", "473x"),
        "610": ("catalog_tesa_610xx", "610xx"),
        "661": ("catalog_tesa_661xx", "661xx"),
    }
    for prefix, (xml_id, name) in series_prefix_map.items():
        if model.startswith(prefix):
            return xml_id, name
    prefix3 = model[:3]
    return f"catalog_tesa_{prefix3}xx", f"{prefix3}xx"


def extract_page_texts(pdf_path: Path) -> list[str]:
    """按页提取 PDF 文本。"""
    parts: list[str] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            txt = page.extract_text() or ""
            if txt:
                parts.append(txt)
    return parts


def build_series_rules(text: str) -> list[tuple[str, str, int]]:
    """从 'tesa 754xx/756xx' 这类标识中构建型号匹配规则。"""
    raw_tokens = re.findall(r"tesa[®\s]*([0-9]{2,5}x{1,2}(?:/[0-9]{2,5}x{1,2})*)", text, flags=re.IGNORECASE)
    rules: set[tuple[str, str, int]] = set()
    for token_group in raw_tokens:
        for token in token_group.lower().split("/"):
            token = token.strip()
            m = re.fullmatch(r"([0-9]+)(x+)", token)
            if not m:
                continue
            prefix = m.group(1)
            total_len = len(token)
            rules.add((token, prefix, total_len))
    return sorted(rules)


def extract_models(text: str, rules: list[tuple[str, str, int]]) -> list[str]:
    """基于规则提取手册中的具体型号。"""
    if not rules:
        return []

    candidates = re.findall(r"\b\d{4,6}\b", text)
    models: set[str] = set()
    for code in candidates:
        for _, prefix, total_len in rules:
            if len(code) == total_len and code.startswith(prefix):
                models.add(code)
                break
    return sorted(models)


def extract_model_thickness_map(text: str) -> dict[str, str]:
    """从手册的厚度行提取型号 -> 厚度(um)。"""
    result: dict[str, str] = {}
    pattern = re.compile(r"([\d,]{1,5})\s*[µμu]m\s+([^\n]+)", flags=re.IGNORECASE)
    for m in pattern.finditer(text):
        raw = m.group(1).replace(",", "")
        if not raw.isdigit():
            continue
        val = int(raw)
        if val <= 0 or val > 5000:
            continue
        thickness = f"{val}um"
        tail = m.group(2)
        for code in re.findall(r"\b\d{4,6}\b", tail):
            result[code] = thickness
    return result


def _normalize_cell_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).replace("， ", "，").replace(", ", ",").replace(" / ", "/").strip()


def _extract_line_block(lines: list[str], label: str, stop_labels: list[str]) -> str:
    for idx, line in enumerate(lines):
        if not line.startswith(label):
            continue
        tail = line[len(label):].strip()
        chunks: list[str] = [tail] if tail else []
        j = idx + 1
        while j < len(lines):
            cur = lines[j].strip()
            if any(cur.startswith(s) for s in stop_labels):
                break
            chunks.append(cur)
            j += 1
        return _normalize_cell_text(" ".join(chunks))
    return ""


def _extract_type_a_series_tokens(lines: list[str]) -> list[str]:
    tokens: list[str] = []
    for line in lines:
        found = re.findall(r"tesa[®\s]*([0-9]{2,5}x{1,2}(?:/[0-9]{2,5}x{1,2})*)", line, flags=re.IGNORECASE)
        if not found:
            continue
        for grp in found:
            tok = grp.strip().lower()
            if re.fullmatch(r"[0-9]{2,5}x{1,2}(?:/[0-9]{2,5}x{1,2})*", tok) and tok not in tokens:
                tokens.append(tok)
    return tokens


def _extract_type_a_sus_peel_values(lines: list[str], expected: int) -> list[str]:
    peel_text = _extract_line_block(lines, "剥离力", TYPE_A_STOP_LABELS)
    if not peel_text:
        return []

    sus_match = re.search(r"SUS\s+(.+)", peel_text)
    if sus_match:
        sus_vals = re.findall(r"\b\d+(?:\.\d+)?/\d+(?:\.\d+)?\b", sus_match.group(1))
        if len(sus_vals) >= expected:
            return [f"{x} N/cm" for x in sus_vals[:expected]]

    vals = re.findall(r"\b\d+(?:\.\d+)?/\d+(?:\.\d+)?\b", peel_text)
    if len(vals) >= expected:
        return [f"{x} N/cm" for x in vals[:expected]]
    return []


def is_type_a_page(page_text: str) -> bool:
    """识别矩阵型分类概览页面。"""
    if "分类概览" not in page_text:
        return False
    has_series = bool(re.search(r"tesa[®\s]*[0-9]{2,5}x{1,2}", page_text, flags=re.IGNORECASE))
    has_thickness = bool(re.search(r"\b\d{1,4}\s*[µμu]m\b", page_text, flags=re.IGNORECASE))
    has_metric = ("剥离力" in page_text) or ("参比产品" in page_text)
    return has_series and has_thickness and has_metric


def parse_type_a_page(page_text: str) -> tuple[dict[str, dict[str, str]], dict[str, str]]:
    """解析 Type-A 页面，返回系列画像与型号厚度。"""
    lines = [ln.strip() for ln in page_text.splitlines() if ln.strip()]
    series_tokens = _extract_type_a_series_tokens(lines)
    if not series_tokens:
        return {}, {}

    n = len(series_tokens)
    color_text = _extract_line_block(lines, "颜色", TYPE_A_STOP_LABELS)
    adhesive_text = _extract_line_block(lines, "胶系", TYPE_A_STOP_LABELS)
    base_text = _extract_line_block(lines, "基材", TYPE_A_STOP_LABELS)

    color_vals = _extract_values_by_candidates(color_text, COLOR_CANDIDATES, n)
    adhesive_vals = _extract_values_by_candidates(adhesive_text, ADHESIVE_CANDIDATES, n)
    base_vals = _extract_values_by_candidates(base_text, BASE_CANDIDATES, n)
    peel_vals = _extract_type_a_sus_peel_values(lines, n)

    if not color_vals:
        color_vals = _extract_values_by_candidates(page_text, COLOR_CANDIDATES, n)
    if not adhesive_vals:
        adhesive_vals = _extract_values_by_candidates(page_text, ADHESIVE_CANDIDATES, n)
    if not base_vals:
        base_vals = _extract_values_by_candidates(page_text, BASE_CANDIDATES, n)

    profiles: dict[str, dict[str, str]] = {}
    for i, token_group in enumerate(series_tokens):
        profile = {
            "variant_color": color_vals[i] if color_vals else "",
            "variant_adhesive_type": adhesive_vals[i] if adhesive_vals else "",
            "variant_base_material": base_vals[i] if base_vals else "",
            "variant_peel_strength": peel_vals[i] if peel_vals else "",
        }
        for token in token_group.split("/"):
            tok = token.strip().lower()
            if re.fullmatch(r"[0-9]{2,5}x{1,2}", tok):
                profiles[tok] = profile

    thickness_map: dict[str, str] = {}
    pending_codes: list[str] = []
    pending_thickness: str = ""
    for line in lines:
        codes = re.findall(r"\b\d{4,6}\b", line)
        m = re.match(r"^([\d,]{1,5})\s*[µμu]?[mM](?:\s+(.+))?$", line, flags=re.IGNORECASE)

        if m:
            raw = m.group(1).replace(",", "")
            if raw.isdigit():
                val = int(raw)
                if 0 < val <= 5000:
                    thickness = f"{val}um"
                    tail = (m.group(2) or "")
                    tail_codes = re.findall(r"\b\d{4,6}\b", tail)
                    if tail_codes:
                        for code in tail_codes:
                            thickness_map[code] = thickness
                    elif pending_codes:
                        for code in pending_codes:
                            thickness_map[code] = thickness
                        pending_codes = []
                    else:
                        pending_thickness = thickness
            continue

        if codes and pending_thickness:
            for code in codes:
                thickness_map[code] = pending_thickness
            pending_thickness = ""
            continue

        if codes:
            pending_codes.extend(codes)

    return profiles, thickness_map


def _extract_values_by_candidates(text: str, candidates: list[str], expected: int) -> list[str]:
    if not text:
        return []
    pattern = "|".join(sorted((re.escape(x) for x in candidates), key=len, reverse=True))
    if not pattern:
        return []
    values = [m.group(0) for m in re.finditer(pattern, text)]
    if len(values) >= expected:
        return values[:expected]
    return []


def _extract_peel_values(text: str, expected: int) -> list[str]:
    if not text:
        return []
    vals = re.findall(r"\b\d+(?:\.\d+)?/\d+(?:\.\d+)?\b", text)
    if len(vals) >= expected:
        return [f"{x} N/cm" for x in vals[:expected]]
    return []


def parse_series_profiles(page_texts: list[str]) -> dict[str, dict[str, str]]:
    """从每页'分类概览'结构中提取系列属性（颜色/胶系/基材/剥离力）。"""
    profiles: dict[str, dict[str, str]] = {}
    stop_labels = TYPE_A_STOP_LABELS
    for page in page_texts:
        if "分类概览" not in page:
            continue
        lines = [ln.strip() for ln in page.splitlines() if ln.strip()]
        series_tokens = _extract_type_a_series_tokens(lines)
        if not series_tokens:
            continue

        n = len(series_tokens)
        color_text = _extract_line_block(lines, "颜色", stop_labels)
        adhesive_text = _extract_line_block(lines, "胶系", stop_labels)
        base_text = _extract_line_block(lines, "基材", stop_labels)
        peel_text = _extract_line_block(lines, "剥离力", stop_labels)

        color_vals = _extract_values_by_candidates(color_text, COLOR_CANDIDATES, n)
        adhesive_vals = _extract_values_by_candidates(adhesive_text, ADHESIVE_CANDIDATES, n)
        base_vals = _extract_values_by_candidates(base_text, BASE_CANDIDATES, n)
        peel_vals = _extract_peel_values(peel_text, n)

        for i, token_group in enumerate(series_tokens):
            for token in token_group.split("/"):
                tok = token.strip().lower()
                if not re.fullmatch(r"[0-9]{2,5}x{1,2}", tok):
                    continue
                p = profiles.setdefault(tok, {"variant_color": "", "variant_adhesive_type": "", "variant_base_material": "", "variant_peel_strength": ""})
                if color_vals:
                    p["variant_color"] = color_vals[i]
                if adhesive_vals:
                    p["variant_adhesive_type"] = adhesive_vals[i]
                if base_vals:
                    p["variant_base_material"] = base_vals[i]
                if peel_vals:
                    p["variant_peel_strength"] = peel_vals[i]

    return profiles


def get_profile_for_model(model: str, rules: list[tuple[str, str, int]], profiles: dict[str, dict[str, str]]) -> dict[str, str]:
    for token, prefix, total_len in rules:
        if len(model) == total_len and model.startswith(prefix):
            if token in profiles:
                return profiles[token]
    return {"variant_color": "", "variant_adhesive_type": "", "variant_base_material": "", "variant_peel_strength": ""}


def write_series_csv(
    series_out: Path,
    models: list[str],
    rules: list[tuple[str, str, int]],
    profiles: dict[str, dict[str, str]],
) -> int:
    headers = [
        "brand_id_xml",
        "categ_id_xml",
        "series_xml_id",
        "name",
        "series_name",
        "catalog_base_material",
        "catalog_adhesive_type",
        "catalog_characteristics",
        "catalog_features",
        "catalog_applications",
    ]
    series_map: dict[str, dict[str, str]] = {}
    for model in models:
        xml_id, series_name = model_to_series(model)
        profile = get_profile_for_model(model, rules, profiles)
        if xml_id not in series_map:
            series_map[xml_id] = {
                "series_name": series_name,
                "catalog_base_material": profile.get("variant_base_material", ""),
                "catalog_adhesive_type": profile.get("variant_adhesive_type", ""),
            }

    with open(series_out, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for xml_id in sorted(series_map):
            row = series_map[xml_id]
            series_name = row["series_name"]
            writer.writerow(
                {
                    "brand_id_xml": "brand_tesa",
                    "categ_id_xml": "category_tape_foam",
                    "series_xml_id": xml_id,
                    "name": f"tesa® {series_name} 胶带",
                    "series_name": series_name,
                    "catalog_base_material": row["catalog_base_material"],
                    "catalog_adhesive_type": row["catalog_adhesive_type"],
                    "catalog_characteristics": "",
                    "catalog_features": "来源: 德莎电子行业胶带应用解决方案(01/2023)",
                    "catalog_applications": "",
                }
            )
    return len(series_map)


def write_variants_csv(
    variants_out: Path,
    models: list[str],
    rules: list[tuple[str, str, int]],
    profiles: dict[str, dict[str, str]],
    thickness_map: dict[str, str],
) -> int:
    headers = [
        "series_xml_id",
        "default_code",
        "variant_thickness",
        "variant_color",
        "variant_adhesive_type",
        "variant_base_material",
        "variant_peel_strength",
        "variant_adhesive_std",
        "variant_base_material_std",
        "variant_color_std",
        "variant_fire_rating",
        "variant_holding_power",
        "variant_pe_peel",
        "variant_sus_peel",
        "variant_thickness_std",
    ]
    with open(variants_out, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for model in models:
            series_xml_id, _ = model_to_series(model)
            profile = get_profile_for_model(model, rules, profiles)

            thickness = thickness_map.get(model, "")
            color = profile.get("variant_color", "")
            adhesive = profile.get("variant_adhesive_type", "")
            base_mat = profile.get("variant_base_material", "")
            peel = profile.get("variant_peel_strength", "")

            writer.writerow(
                {
                    "series_xml_id": series_xml_id,
                    "default_code": model,
                    "variant_thickness": thickness,
                    "variant_color": color,
                    "variant_adhesive_type": adhesive,
                    "variant_base_material": base_mat,
                    "variant_peel_strength": peel,
                    "variant_adhesive_std": adhesive,
                    "variant_base_material_std": base_mat,
                    "variant_color_std": color,
                    "variant_fire_rating": "none",
                    "variant_holding_power": "",
                    "variant_pe_peel": "",
                    "variant_sus_peel": "",
                    "variant_thickness_std": thickness,
                }
            )
    return len(models)


def main() -> None:
    parser = argparse.ArgumentParser(description="从德莎行业解决方案 PDF 提取系列与型号")
    parser.add_argument("--pdf", default=str(DEFAULT_INPUT_PDF), help="输入 PDF 文件路径")
    parser.add_argument("--series-out", default=str(DEFAULT_SERIES_OUT), help="输出 series CSV")
    parser.add_argument("--variants-out", default=str(DEFAULT_VARIANTS_OUT), help="输出 variants CSV")
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        raise SystemExit(f"PDF 不存在: {pdf_path}")

    page_texts = extract_page_texts(pdf_path)
    text = "\n".join(page_texts)
    rules = build_series_rules(text)
    models = extract_models(text, rules)
    thickness_map = extract_model_thickness_map(text)
    profiles = parse_series_profiles(page_texts)

    type_a_page_count = 0
    type_a_profiles: dict[str, dict[str, str]] = {}
    type_a_thickness: dict[str, str] = {}
    for page in page_texts:
        if not is_type_a_page(page):
            continue
        type_a_page_count += 1
        p_profiles, p_thickness = parse_type_a_page(page)
        for k, v in p_profiles.items():
            type_a_profiles[k] = v
        for code, th in p_thickness.items():
            type_a_thickness[code] = th

    # Type-A 专用提取优先覆盖
    profiles.update(type_a_profiles)
    thickness_map.update(type_a_thickness)

    if not models:
        raise SystemExit("未提取到任何型号，请检查 PDF 文本质量或规则。")

    series_count = write_series_csv(Path(args.series_out), models, rules, profiles)
    variant_count = write_variants_csv(
        Path(args.variants_out),
        models,
        rules,
        profiles,
        thickness_map,
    )

    print(f"提取完成: 型号 {variant_count} 个, 系列 {series_count} 个")
    print(f"Type-A 命中页数: {type_a_page_count}")
    print(f"Type-A 提取厚度数: {len(type_a_thickness)}")
    print(f"series 输出: {args.series_out}")
    print(f"variants 输出: {args.variants_out}")


if __name__ == "__main__":
    main()
