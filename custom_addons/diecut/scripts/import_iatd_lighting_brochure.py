# -*- coding: utf-8 -*-
import base64
import json
import mimetypes
from pathlib import Path


SOURCE_NAME = "3M 照明胶粘手册"
SOURCE_FILENAME_KEYWORD = "lighting-applications-brochure"
PDF_DIR = Path("/mnt/extra-addons/diecut/scripts/tesa_tds_pdfs")
DRAFT_PATH = Path("/mnt/extra-addons/diecut/scripts/tds_import_drafts/iatd_lighting_brochure_draft.json")

CATEGORY_FOAM = "泡棉胶带"
CATEGORY_PET_DOUBLE = "PET双面胶带"
CATEGORY_TISSUE = "棉纸/无纺布双面胶带"
CATEGORY_NO_SUBSTRATE = "无基材双面胶带"
CATEGORY_OTHER = "其他辅料"


def lines(*values):
    return "\n".join(str(value).strip() for value in values if value).strip()


def html_list(items):
    clean_items = [str(item).strip() for item in items if item]
    if not clean_items:
        return False
    return "<div data-oe-version=\"2.0\"><ul>%s</ul></div>" % "".join(
        "<li>%s</li>" % item for item in clean_items
    )


def float_or_false(value):
    if value in (None, False, ""):
        return False
    return float(value)


def build_payload():
    payload = {
        "series": [],
        "items": [],
        "params": [],
        "category_params": [],
        "spec_values": [],
        "unmatched": [],
    }
    params_seen = set()
    category_param_seen = set()

    def add_param(
        param_key,
        name,
        spec_category_name,
        value_type="char",
        preferred_unit=False,
        categories=None,
    ):
        if param_key not in params_seen:
            payload["params"].append(
                {
                    "param_key": param_key,
                    "name": name,
                    "spec_category_name": spec_category_name,
                    "value_type": value_type,
                    "preferred_unit": preferred_unit or False,
                    "is_main_field": False,
                    "main_field_name": False,
                }
            )
            params_seen.add(param_key)
        for category_name in categories or []:
            key = (category_name, param_key)
            if key in category_param_seen:
                continue
            payload["category_params"].append(
                {
                    "category_name": category_name,
                    "categ_name": category_name,
                    "param_key": param_key,
                    "name": name,
                    "required": False,
                    "show_in_form": True,
                    "allow_import": True,
                }
            )
            category_param_seen.add(key)

    def add_series(series_name, category_name, product_description, product_features, main_applications, special_applications, source_page):
        payload["series"].append(
            {
                "series_name": series_name,
                "brand_name": "3M",
                "category_name": category_name,
                "name": series_name,
                "product_description": product_description,
                "product_features": product_features,
                "main_applications": main_applications,
                "special_applications": special_applications,
                "source_page": source_page,
                "source_text": SOURCE_NAME,
                "source_label": "manual_visual_import",
            }
        )

    def add_item(
        code,
        name,
        series_name,
        category_name,
        thickness=False,
        color_name=False,
        adhesive_type_name=False,
        base_material_name=False,
        product_features=False,
        product_description=False,
        main_applications=False,
        special_applications=False,
        sequence=10,
        source_page=None,
    ):
        payload["items"].append(
            {
                "code": code,
                "name": name,
                "brand_name": "3M",
                "series_name": series_name,
                "category_name": category_name,
                "catalog_status": "published",
                "active": True,
                "sequence": sequence,
                "thickness": float_or_false(thickness),
                "color_name": color_name or False,
                "adhesive_type_name": adhesive_type_name or False,
                "base_material_name": base_material_name or False,
                "product_features": product_features or False,
                "product_description": product_description or False,
                "main_applications": main_applications or False,
                "special_applications": special_applications or False,
                "source_page": source_page,
                "source_text": code,
                "source_label": "manual_visual_import",
            }
        )

    def add_specs(item_codes, spec_map, source_page):
        unit_map = {
            "short_term_heat_resistance": "°C",
            "long_term_heat_resistance": "°C",
            "flash_point_c": "°C",
            "max_service_temp_c": "°C",
            "min_service_temp_c": "°C",
            "coverage_rate_m2_per_l": "m²/L",
            "density_g_per_l": "g/L",
            "construction_thickness_mil": "mil",
        }
        for item_code in item_codes:
            for param_key, value in spec_map.items():
                if value in (None, False, ""):
                    continue
                payload["spec_values"].append(
                    {
                        "item_code": item_code,
                        "param_key": param_key,
                        "value": value,
                        "unit": unit_map.get(param_key) or False,
                        "source_page": source_page,
                        "source_text": item_code,
                        "source_label": "manual_visual_import",
                        "review_status": "pending",
                    }
                )

    base_categories = [CATEGORY_FOAM, CATEGORY_PET_DOUBLE, CATEGORY_TISSUE, CATEGORY_NO_SUBSTRATE]
    add_param("short_term_heat_resistance", "短期耐温", "耐温性能", "float", "°C", base_categories)
    add_param("long_term_heat_resistance", "长期耐温", "耐温性能", "float", "°C", base_categories)
    add_param("solvent_resistance_level", "耐溶剂性等级", "粘接性能", "char", False, base_categories)
    add_param("adhesion_hse_level", "高表面能粘接等级", "粘接性能", "char", False, base_categories)
    add_param("adhesion_lse_level", "低表面能粘接等级", "粘接性能", "char", False, base_categories)
    add_param("liner_description", "离型材料", "结构与离型", "char", False, base_categories + [CATEGORY_OTHER])
    add_param("solvent_name", "溶剂", "化学与工艺", "char", False, [CATEGORY_OTHER])
    add_param("effective_ingredient", "有效成分", "化学与工艺", "char", False, [CATEGORY_OTHER])
    add_param("density_g_per_l", "密度", "化学与工艺", "float", "g/L", [CATEGORY_OTHER])
    add_param("flash_point_c", "闪点", "化学与工艺", "float", "°C", [CATEGORY_OTHER])
    add_param("coverage_rate_m2_per_l", "覆盖率", "化学与工艺", "float", "m²/L", [CATEGORY_OTHER])
    add_param("supported_printing_methods", "适用印刷方式", "印刷与标签", "char", False, [CATEGORY_OTHER])
    add_param("max_service_temp_c", "最高工作温度", "印刷与标签", "float", "°C", [CATEGORY_OTHER])
    add_param("min_service_temp_c", "最低工作温度", "印刷与标签", "float", "°C", [CATEGORY_OTHER])
    add_param("construction_thickness_mil", "结构厚度", "印刷与标签", "char", "mil", [CATEGORY_OTHER])

    vhb_application_html = html_list(
        [
            "硅胶灯带背胶",
            "户外灯饰背胶",
            "LED灯带结构粘接",
            "小夜灯固定",
            "LED扩散板粘接",
            "植物灯结构粘接",
        ]
    )
    vhb_common_features = lines(
        "100%丙烯酸胶粘剂构成",
        "100%闭孔泡棉结构",
        "独特的结构设计，兼顾强度与贴服性",
        "优异耐老化与耐候性",
        "防水密封可达IPX7",
        "易于模切，适合多种照明结构件设计",
    )
    vhb_common_special = lines(
        "适合户外耐候与防水要求较高的照明产品。",
        "适合替代螺丝、铆接或硅胶固定的结构设计。",
    )
    vhb_series_rows = [
        ("3M VHB LSE系列", "特别针对低表面能表面设计，适用于PP、TPE、TPO等低表面能材料。", 150, 100, "高", "高", "高", "白", [("LSE060", 0.6), ("LSE110", 1.0), ("LSE160", 1.6)]),
        ("3M VHB LVO系列", "低VOC、低气味VHB泡棉胶带，适用于高中低表面能材料，耐温性能好并具FDA认证。", 121, 93, "高", "高", "中", "黑", [("LVO-060BF", 0.6), ("LVO-110BF", 1.1), ("LVO-160BF", 1.6)]),
        ("3M VHB 4941系列", "贴服性好，具有出色粘接强度，适合高与中高表面，耐增塑剂并通过UL746C。", 149, 93, "高", "高", "中", "灰", [("4926", 0.4), ("4936", 0.6), ("4941", 1.1), ("4956", 1.6), ("4991", 2.3)]),
        ("3M VHB 5952系列", "泡棉更柔软、贴服性佳，适合高中高表面能及多种喷涂表面的粘接，并通过UL746C。", 149, 93, "高", "高", "中", "黑", [("5915", 0.4), ("5925", 0.6), ("5930", 0.8), ("5952", 1.1), ("5962", 1.6)]),
        ("3M VHB 4910系列", "透明VHB胶带，适用于有透明粘接需求的照明与结构固定场景。", 149, 93, "高", "高", "中", "透明", [("4905", 0.5), ("4910", 1.0), ("4915", 1.5), ("4918", 2.0)]),
        ("3M VHB RP+系列", "兼顾粘接强度、耐候性和耐温性，适合多种中高表面能材料结构粘接。", 230, 121, "高", "高", "中", "灰", [("RP+040", 0.4), ("RP+060", 0.6), ("RP+080", 0.8), ("RP+110", 1.1), ("RP+160", 1.6), ("RP+230", 2.3)]),
        ("3M VHB GPH系列", "适用于多种金属、塑料、涂层等基材，耐高温性能较好，适合粉末喷涂预贴合与高温应用。", 230, 150, "高", "高", "中", "灰", [("GPH060", 0.6), ("GPH110", 1.1), ("GPH160", 1.6)]),
        ("3M VHB 4950系列", "适合金属、玻璃、涂层及多种易粘接塑料表面，粘接强度高，并通过UL746C。", 149, 93, "高", "高", "低", "白", [("4914", 0.25), ("4920", 0.4), ("4930", 0.8), ("4950", 1.1)]),
        ("3M VHB GPL系列", "泡棉较柔软、贴服性好，适用于多种中高表面能材料，同时具备良好初粘与低温操作性能，并通过UL746C。", 110, 85, "高", "高", "中", "灰", [("GPL040", 0.4), ("GPL060", 0.6), ("GPL080", 0.8), ("GPL110", 1.1), ("GPL160", 1.6), ("GPL200", 2.0)]),
        ("3M VHB 5611系列", "对金属及中高表面能材料具有较高粘接力，耐温性好，兼具较高性价比。", 149, 93, "高", "高", "低", False, [("5604", 0.4), ("5608", 0.8), ("5611", 1.1)]),
    ]
    sequence = 10
    for series_name, description, short_temp, long_temp, solvent_level, hse_level, lse_level, color_name, items in vhb_series_rows:
        add_series(series_name, CATEGORY_FOAM, description, vhb_common_features, vhb_application_html, vhb_common_special, 2)
        codes = []
        for code, thickness in items:
            codes.append(code)
            add_item(
                code=code,
                name=f"3M {code}",
                series_name=series_name,
                category_name=CATEGORY_FOAM,
                thickness=thickness,
                color_name=color_name,
                adhesive_type_name="丙烯酸",
                base_material_name="丙烯酸泡棉",
                product_features=vhb_common_features,
                product_description=description,
                main_applications=vhb_application_html,
                special_applications=vhb_common_special,
                sequence=sequence,
                source_page=4,
            )
            sequence += 10
        add_specs(
            codes,
            {
                "short_term_heat_resistance": short_temp,
                "long_term_heat_resistance": long_temp,
                "solvent_resistance_level": solvent_level,
                "adhesion_hse_level": hse_level,
                "adhesion_lse_level": lse_level,
            },
            4,
        )

    thin_common_applications = html_list(["柔性LED灯条背胶", "铭板粘贴", "显示面板固定", "泡棉与塑料件贴合"])
    thin_rows = [
        ("3M 转移胶膜系列", CATEGORY_NO_SUBSTRATE, "F9469PC", 0.13, "透明", "丙烯酸", "无基材", "58# 涂布牛皮纸", 260, 149, "高", "高", "低", "具有很强粘性和优异物理、化学稳定性，可起到密封作用，并兼具抗溶剂、抗紫外和抗温度急变特性。"),
        ("3M 转移胶膜系列", CATEGORY_NO_SUBSTRATE, "468MP", 0.13, "透明", "丙烯酸", "无基材", "58# 涂布牛皮纸", 204, 149, "高", "高", "低", "无基材转移胶膜，可为金属和高表面能塑料提供优异粘附力，具备优异剪切强度与环境适应性。"),
        ("3M PET双面胶系列", CATEGORY_PET_DOUBLE, "9495LE", 0.17, "透明", "丙烯酸", "PET", "58# 聚酯涂布牛皮纸(PCK)", 149, 93, "中", "高", "高", "模切性能优异，适合低表面能材料及轻微油污表面的粘接。"),
        ("3M PET双面胶系列", CATEGORY_PET_DOUBLE, "93015LE", 0.15, "透明", "丙烯酸", "PET", "58# 聚酯涂布牛皮纸(PCK)", 149, 93, "中", "高", "高", "适合多种低表面能塑料与轻微油污表面的模切粘接应用。"),
        ("3M PET双面胶系列", CATEGORY_PET_DOUBLE, "9495MP", 0.14, "透明", "丙烯酸", "PET", "58# 聚酯涂布牛皮纸(PCK)", 149, 93, "中", "高", "高", "对高表面能材料具有良好粘接强度。"),
        ("3M 棉纸双面胶系列", CATEGORY_TISSUE, "9080A", 0.15, "半透明", "改性丙烯酸", "棉纸/无纺布", "76# 聚酯涂布牛皮纸(PCK)", 150, 80, "中", "高", "高", "模切性能优异，适合多数表面，耐高温，耐剪切强度表现优异。"),
        ("3M 棉纸双面胶系列", CATEGORY_TISSUE, "9448A", 0.15, "半透明", "丙烯酸", "棉纸/无纺布", "120g聚酯涂布牛皮纸(PCK)", 150, 70, "中", "高", "高", "中等强度丙烯酸胶系，操作与加工效率高，适合PE及不锈钢等基材粘接。"),
        ("3M 棉纸双面胶系列", CATEGORY_TISSUE, "55210", 0.10, "半透明", "丙烯酸", "棉纸/无纺布", "120gsm白色PCK，灰色3M标记", 150, 70, "中", "中", "中", "0.1mm双面棉纸胶带，适用于多种常见粘接表面，性价比高。"),
        ("3M 棉纸双面胶系列", CATEGORY_TISSUE, "56215", 0.15, "透明", "丙烯酸", "棉纸/无纺布", "聚酯涂层牛皮纸", 121, 82, "高", "高", "低", "无溶剂涂布技术生产，具备可重工、高初粘和良好低温性能，特别适合泡棉粘接。"),
        ("3M 棉纸双面胶系列", CATEGORY_TISSUE, "56415", 0.15, "半透明", "丙烯酸", "棉纸/无纺布", "聚酯涂层牛皮纸", 121, 82, "高", "高", "低", "无溶剂涂布技术生产，对低表面能材料也有出色粘接性能，同时具备可重工和高初粘特点。"),
    ]
    seen_series = set()
    for row in thin_rows:
        series_name, category_name, code, thickness, color_name, adhesive_type, base_material, liner, short_temp, long_temp, solvent_level, hse_level, lse_level, description = row
        if series_name not in seen_series:
            add_series(series_name, category_name, description, "适合模切与薄型结构固定。", thin_common_applications, "适用于柔性LED灯条背胶及精密贴合场景。", 6)
            seen_series.add(series_name)
        add_item(
            code=code,
            name=f"3M {code}",
            series_name=series_name,
            category_name=category_name,
            thickness=thickness,
            color_name=color_name,
            adhesive_type_name=adhesive_type,
            base_material_name=base_material,
            product_features="适合模切与薄型结构固定。",
            product_description=description,
            main_applications=thin_common_applications,
            special_applications=lines("离型材料：%s" % liner, "适用于柔性LED灯条背胶与结构件贴合。"),
            sequence=sequence,
            source_page=6,
        )
        sequence += 10
        add_specs(
            [code],
            {
                "short_term_heat_resistance": short_temp,
                "long_term_heat_resistance": long_temp,
                "solvent_resistance_level": solvent_level,
                "adhesion_hse_level": hse_level,
                "adhesion_lse_level": lse_level,
                "liner_description": liner,
            },
            6,
        )

    foam_led_applications = html_list(
        [
            "LED灯箱模组背胶",
            "标志、铭牌",
            "显示面板",
            "塑料挂钩、支架",
            "电线电缆固定",
            "家电与展示柜部件",
            "电子设备装饰件",
        ]
    )
    add_series("3M PE泡棉胶带系列", CATEGORY_FOAM, "面向LED照明模组背胶应用的PE泡棉胶带。", "高初粘、轻量、适合小部件粘接且易模切。", foam_led_applications, "适用于LED照明模组背胶场景。", 7)
    for code, description in [("CIP66", "性价比高，综合性能好"), ("1600T", "性价比高，高剪切力")]:
        add_item(
            code=code,
            name=f"3M {code}",
            series_name="3M PE泡棉胶带系列",
            category_name=CATEGORY_FOAM,
            thickness=1.1,
            color_name="白色",
            adhesive_type_name="丙烯酸胶粘剂",
            base_material_name="PE泡棉",
            product_features="高初粘、轻量、适合小部件粘接且易模切。",
            product_description=description,
            main_applications=foam_led_applications,
            special_applications="推荐用于LED照明模组背胶。",
            sequence=sequence,
            source_page=7,
        )
        sequence += 10

    label_print_map = {
        "7613T": "柔印、UV喷墨、丝网印刷",
        "7110": "柔印、UV喷墨、丝网印刷",
        "7871V": "柔印、UV喷墨、激光/碳粉、丝网印刷",
        "57817CN": "柔印、热转印、丝网印刷",
    }
    add_series("3M 防篡改标签系列", CATEGORY_OTHER, "面向照明变压器、电源及关键部件的防篡改标签材料。", "揭除即破坏，适合防伪与防拆封。", html_list(["照明变压器标签", "电源标签", "防篡改封签"]), "适用于需要防拆、防伪与密封证明的场景。", 7)
    add_series("3M 耐久性标签系列", CATEGORY_OTHER, "面向照明变压器、电源及部件铭牌的耐久性标签材料。", "支持多种印刷方式，适合长期识别。", html_list(["照明变压器标签", "电源铭牌", "耐久性标识"]), "适用于长期识别、铭牌与追溯标签场景。", 7)
    label_rows = [
        ("3M 防篡改标签系列", "7613T", "3M 7613T 防篡改标签材料", "哑白", "聚氯乙烯", "丙烯酸", "#55白色涂硅致密牛皮纸", "2.0/0.8/3.2", 149, -40, "易碎性聚氯乙烯标签材料，尺寸稳定性高，适用于高低表面能、纹理面、粉末喷涂及轻微油污表面；揭除时标签会被破坏。"),
        ("3M 防篡改标签系列", "7110", "3M 7110 防篡改标签材料", "哑白", "防篡改纸", "丙烯酸", "白色致密牛皮纸离型纸", "2.7/0.8/2.5", 121, -40, "纸质易碎防伪标签材料，可牢固贴合于多种材料表面，适合防篡改密封应用。"),
        ("3M 耐久性标签系列", "7871V", "3M 7871V 耐久性标签材料", "亮白", "聚酯", "丙烯酸", "#55致密牛皮纸", "2.0/0.8/3.2", 149, -40, "PET耐久标签材料，适合多种印刷方式，适用于高低表面能、纹理、粉末喷涂及轻微油污表面。"),
        ("3M 耐久性标签系列", "57817CN", "3M 57817CN 耐久性标签材料", "亮白", "聚酯", "丙烯酸", "80#格拉辛纸", "2.7/0.8/2.5", 149, -40, "热转印聚酯标签材料，可防止溢胶，牢固贴合多种塑料与金属，适合热转印和部分传统印刷工艺。"),
    ]
    for series_name, code, name, color_name, base_material, adhesive_type, liner, construction, max_temp, min_temp, description in label_rows:
        add_item(
            code=code,
            name=name,
            series_name=series_name,
            category_name=CATEGORY_OTHER,
            color_name=color_name,
            adhesive_type_name=adhesive_type,
            base_material_name=base_material,
            product_features="适用印刷方式：%s" % label_print_map[code],
            product_description=description,
            main_applications=html_list(["照明变压器/电源标签", "部件铭牌", "追溯标识"]),
            special_applications=lines("结构厚度(mil)：%s" % construction, "离型材料：%s" % liner),
            sequence=sequence,
            source_page=7,
        )
        sequence += 10
        add_specs(
            [code],
            {
                "liner_description": liner,
                "construction_thickness_mil": construction,
                "max_service_temp_c": max_temp,
                "min_service_temp_c": min_temp,
                "supported_printing_methods": label_print_map[code],
            },
            7,
        )

    add_series("3M 底涂剂系列", CATEGORY_OTHER, "用于难粘接基材表面处理、提升胶带系统附着力的底涂剂与表面处理辅料。", "适合难粘接材料预处理，可提升金属、塑料、玻璃等表面的附着力。", html_list(["胶带粘接前表面处理", "金属与塑料基材附着力提升", "玻璃基材底涂"]), "页面同时给出清洁、压力、温度和时间的施工建议。", 5)
    primer_rows = [
        ("AP111", "3M AP111 底涂剂", "透明", "促进裸金属和涂漆表面的附着力。", "异丙醇(IPA)", "重量百分比 5%", 708, 11, 19),
        ("AP115", "3M AP115 底涂剂", "透明", "促进更好的玻璃附着力，并改善表面附着力。", "异丙醇和水", "小于重量百分比 1%", 728, 12, 20),
        ("94底涂剂", "3M 94 底涂剂", "透明至淡黄/深黄", "促进聚乙烯、聚丙烯、ABS、PET/PBT及混合物等多种塑料表面的更好附着力。", "详见SDS", "详见SDS", 755, -20, 15),
        ("UPUV底涂剂", "3M UPUV 底涂剂", "透明", "与3M 94底涂剂相比，改善环境、健康和安全特性。", "详见SDS", "透明的淡黄色", 429, -21, 15),
    ]
    for code, name, color_name, description, solvent_name, effective_ingredient, density, flash_point, coverage in primer_rows:
        add_item(
            code=code,
            name=name,
            series_name="3M 底涂剂系列",
            category_name=CATEGORY_OTHER,
            color_name=color_name,
            product_features="用于难粘接基材的附着力提升。",
            product_description=description,
            main_applications=html_list(["金属表面", "玻璃表面", "塑料表面", "VHB结构胶带配套底涂"]),
            special_applications=lines("溶剂：%s" % solvent_name, "有效成分：%s" % effective_ingredient),
            sequence=sequence,
            source_page=5,
        )
        sequence += 10
        add_specs(
            [code],
            {
                "solvent_name": solvent_name,
                "effective_ingredient": effective_ingredient,
                "density_g_per_l": density,
                "flash_point_c": flash_point,
                "coverage_rate_m2_per_l": coverage,
            },
            5,
        )

    return payload


def locate_pdf():
    for path in sorted(PDF_DIR.glob("*.pdf")):
        if SOURCE_FILENAME_KEYWORD in path.name:
            return path
    raise FileNotFoundError("lighting brochure pdf not found")


def upsert_source_document(pdf_path, payload):
    brand = env["diecut.brand"].sudo().search([("name", "ilike", "3M")], limit=1)
    source = env["diecut.catalog.source.document"].sudo().search([("name", "=", SOURCE_NAME)], limit=1)
    vals = {
        "name": SOURCE_NAME,
        "source_type": "pdf",
        "source_filename": pdf_path.name,
        "brand_id": brand.id or False,
        "import_status": "generated",
        "parse_version": "manual-vision-v1",
        "draft_payload": json.dumps(payload, ensure_ascii=False, indent=2),
        "unmatched_payload": "[]",
        "result_message": "基于页面渲染与人工校核生成的照明选型手册导入草稿。",
    }
    if source:
        source.write(vals)
    else:
        source = env["diecut.catalog.source.document"].sudo().create(vals)

    attachment_model = env["ir.attachment"].sudo()
    datas = base64.b64encode(pdf_path.read_bytes()).decode()
    mimetype = mimetypes.guess_type(str(pdf_path))[0] or "application/pdf"
    attachment = attachment_model.search(
        [
            ("res_model", "=", "diecut.catalog.source.document"),
            ("res_id", "=", source.id),
            ("res_field", "=", False),
            ("name", "=", pdf_path.name),
        ],
        limit=1,
    )
    if attachment:
        attachment.write({"datas": datas, "mimetype": mimetype, "type": "binary"})
    else:
        attachment = attachment_model.create(
            {
                "name": pdf_path.name,
                "type": "binary",
                "datas": datas,
                "mimetype": mimetype,
                "res_model": "diecut.catalog.source.document",
                "res_id": source.id,
            }
        )
    source.write(
        {
            "primary_attachment_id": attachment.id,
            "source_file": datas,
            "source_filename": pdf_path.name,
        }
    )
    return source


def _get_or_create_name_record(model_name, name):
    if not name:
        return False
    record = env[model_name].sudo().search([("name", "=", name)], limit=1)
    if record:
        return record
    return env[model_name].sudo().create({"name": name})


def sync_main_fields_from_payload(payload):
    for row in payload.get("items") or []:
        code = (row.get("code") or "").strip()
        if not code:
            continue
        item = env["diecut.catalog.item"].sudo().search([("code", "=", code)], limit=1)
        if not item:
            continue
        vals = {}
        thickness = row.get("thickness")
        if thickness not in (None, False, ""):
            vals["thickness"] = float(thickness)
        color = _get_or_create_name_record("diecut.color", row.get("color_name"))
        if color:
            vals["color_id"] = color.id
        adhesive = _get_or_create_name_record("diecut.catalog.adhesive.type", row.get("adhesive_type_name"))
        if adhesive:
            vals["adhesive_type_id"] = adhesive.id
        base_material = _get_or_create_name_record("diecut.catalog.base.material", row.get("base_material_name"))
        if base_material:
            vals["base_material_id"] = base_material.id
        if vals:
            item.write(vals)


payload = build_payload()
pdf_path = locate_pdf()
DRAFT_PATH.parent.mkdir(parents=True, exist_ok=True)
DRAFT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
source = upsert_source_document(pdf_path, payload)
source._run_encoding_precheck(payload)
source.action_validate_draft()
source.action_apply_draft()
sync_main_fields_from_payload(payload)
env.cr.commit()

print("source_id=%s" % source.id)
print("draft_path=%s" % DRAFT_PATH)
print("series_count=%s" % len(payload["series"]))
print("item_count=%s" % len(payload["items"]))
print("param_count=%s" % len(payload["params"]))
print("spec_count=%s" % len(payload["spec_values"]))
