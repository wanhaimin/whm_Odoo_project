# -*- coding: utf-8 -*-
import base64
import json
import mimetypes
from pathlib import Path

from odoo import Command


SOURCE_NAME = "3M 300LSE \u6c7d\u8f66\u5e94\u7528\u624b\u518c"
PDF_PATH = Path("/mnt/extra-addons/diecut/scripts/tesa_tds_pdfs/3m_300lse_auto_brochure.pdf")
DRAFT_PATH = Path("/mnt/extra-addons/diecut/scripts/tds_import_drafts/3m_300lse_auto_brochure_draft.json")

CATEGORY_PET_DOUBLE = "PET\u53cc\u9762\u80f6\u5e26"
CATEGORY_NO_SUBSTRATE = "\u65e0\u57fa\u6750\u53cc\u9762\u80f6\u5e26"
SERIES_NAME = "3M 300LSE\u7cfb\u5217"
BRAND_NAME = "3M"


def lines(*values):
    return "\n".join(str(value).strip() for value in values if value).strip()


def html_list(items):
    clean_items = [str(item).strip() for item in items if str(item).strip()]
    if not clean_items:
        return False
    return "<div data-oe-version=\"2.0\"><ul>%s</ul></div>" % "".join(
        "<li>%s</li>" % item for item in clean_items
    )


def float_or_false(value):
    if value in (None, False, ""):
        return False
    return float(value)


COMMON_DESCRIPTION = (
    "3M 300LSE\u7cfb\u5217\u9ad8\u5f3a\u5ea6\u4e19\u70ef\u9178\u80f6\u5e26\u5177\u6709\u8d85\u5f3a\u7c98\u63a5\u529b\uff0c"
    "\u5bf9\u7edd\u5927\u591a\u6570\u6750\u6599\u8868\u9762\u5177\u6709\u5f88\u9ad8\u7684\u7c98\u63a5\u5f3a\u5ea6\uff0c"
    "\u5305\u62ec\u591a\u6570\u4f4e\u8868\u9762\u80fd\u5851\u80f6\u6750\u6599\uff0c\u4f8b\u5982\u805a\u4e19\u70ef\uff0c"
    "\u7c89\u672b\u6d82\u5c42\u7b49\u3002\u8be5\u7cfb\u5217\u80f6\u5e26\u4e5f\u5bf9\u8f7b\u5fae\u6cb9\u6c61\u8868\u9762"
    "\u6709\u4f18\u5f02\u7684\u7c98\u63a5\u5f3a\u5ea6\uff0c\u4f7f\u8bbe\u8ba1\u66f4\u8f7b\u677e\u3002"
)

COMMON_FEATURES = lines(
    "\u9ad8\u521d\u59cb\u7c98\u5408\u5f3a\u5ea6",
    "\u9ad8\u6297\u526a\u5f3a\u5ea6",
    "\u4f18\u5f02\u7684\u6297\u8d77\u7fd8\u6027\u80fd",
    "\u53cc\u9762\u80f6\u5e26\u65b9\u4fbf\u6a21\u5207\u3001\u52a0\u5de5\u4ee5\u53ca\u5e94\u7528",
    "\u65e0\u9700\u5e95\u6f06\u5242",
    "\u65e0\u6eb6\u5242\u6280\u672f",
    "\u9002\u5408\u4f4e\u8868\u9762\u80fd\u5851\u6599\u4e0e\u8f7b\u5fae\u6cb9\u6c61\u8868\u9762",
)

COMMON_APPLICATIONS = html_list(
    [
        "\u96be\u7c98\u6750\u6599\u7c98\u63a5",
        "\u6c7d\u8f66\u5185\u9970\u7c98\u63a5",
        "\u7535\u5b50\u90e8\u4ef6\u56fa\u5b9a",
        "\u5bb6\u7535\u90e8\u4ef6\u7c98\u63a5",
    ]
)

COMMON_SPECIAL = lines(
    "\u9002\u7528\u4e8e ABS\u3001\u5c3c\u9f99\u6d82\u5c42\u94dd\u6750\u3001\u94dc\u7248\u7eb8\u3001EPDM \u6a61\u80f6\u3001"
    "\u6ce1\u68c9\u3001\u77f3\u58a8\u3001\u91d1\u5c5e\u7f51\u7eb1\u3001\u6f06\u9762\u3001PET \u819c\u3001\u5e26\u6d82\u5c42 PC\u3001"
    "PP\u3001\u7c89\u672b\u6d82\u5c42\u8868\u9762\u3001\u805a\u6c28\u916f\u6a61\u80f6\u3001SIS \u6a61\u80f6\u3001\u6728\u6750"
    "\u7b49\u96be\u7c98\u6750\u6599\u3002",
    "\u53ef\u5e2e\u52a9\u8bbe\u8ba1\u66ff\u4ee3\u673a\u68b0\u5361\u6263\u3002",
)

ITEM_ROWS = [
    {
        "code": "93005LE",
        "name": "3M 93005LE",
        "category_name": CATEGORY_PET_DOUBLE,
        "thickness": 0.05,
        "color_name": "\u900f\u660e",
        "adhesive_type_name": "\u4e19\u70ef\u9178",
        "base_material_name": "PET",
        "liner": "58\u53f7PCK\uff0c83\u53f7PCK",
        "special_applications": lines("\u91d1\u5c5e\u7f51\u7eb1\u7c98\u63a5\u5851\u6599\u3002", "\u9002\u5408\u8d85\u8584\u624b\u673a\u8bbe\u8ba1\u3002"),
        "application_tags": ["\u96be\u7c98\u6750\u6599\u7c98\u63a5", "\u7535\u5b50\u90e8\u4ef6\u56fa\u5b9a", "\u91d1\u5c5e\u7f51\u7eb1\u7c98\u63a5\u5851\u6599"],
        "feature_tags": ["\u4f4e\u8868\u9762\u80fd\u7c98\u63a5", "\u9ad8\u521d\u7c98", "\u9ad8\u6297\u526a\u5f3a\u5ea6", "\u6613\u6a21\u5207", "\u65e0\u9700\u5e95\u6f06\u5242", "\u65e0\u6eb6\u5242\u6280\u672f"],
    },
    {
        "code": "93005LEB",
        "name": "3M 93005LEB",
        "category_name": CATEGORY_PET_DOUBLE,
        "thickness": 0.05,
        "color_name": "\u9ed1",
        "adhesive_type_name": "\u4e19\u70ef\u9178",
        "base_material_name": "PET",
        "liner": "58\u53f7PCK\uff0c83\u53f7PCK",
        "special_applications": lines("\u9ed1\u8272\u7248\u672c\uff0c\u9002\u5408\u9700\u8981\u906e\u853d\u5916\u89c2\u6216\u9ed1\u8272\u7ed3\u6784\u4ef6\u7684\u96be\u7c98\u6750\u6599\u8d34\u5408\u3002"),
        "application_tags": ["\u96be\u7c98\u6750\u6599\u7c98\u63a5", "\u7535\u5b50\u90e8\u4ef6\u56fa\u5b9a"],
        "feature_tags": ["\u4f4e\u8868\u9762\u80fd\u7c98\u63a5", "\u9ad8\u521d\u7c98", "\u9ad8\u6297\u526a\u5f3a\u5ea6", "\u6613\u6a21\u5207", "\u65e0\u9700\u5e95\u6f06\u5242", "\u65e0\u6eb6\u5242\u6280\u672f"],
    },
    {
        "code": "9471LE",
        "name": "3M 9471LE",
        "category_name": CATEGORY_NO_SUBSTRATE,
        "thickness": 0.06,
        "color_name": "\u900f\u660e",
        "adhesive_type_name": "\u4e19\u70ef\u9178",
        "base_material_name": "\u65e0\u57fa\u6750",
        "liner": "58\u53f7PCK",
        "special_applications": lines("\u5851\u6599\u7c98\u5408\u5851\u6599\u3002", "\u9002\u5408\u533b\u7597\u8bbe\u5907\u5e94\u7528\u3002"),
        "application_tags": ["\u96be\u7c98\u6750\u6599\u7c98\u63a5", "\u533b\u7597\u8bbe\u5907\u7c98\u63a5", "\u5851\u6599\u7c98\u5408\u5851\u6599"],
        "feature_tags": ["\u4f4e\u8868\u9762\u80fd\u7c98\u63a5", "\u9ad8\u521d\u7c98", "\u9ad8\u6297\u526a\u5f3a\u5ea6", "\u6613\u6a21\u5207", "\u65e0\u9700\u5e95\u6f06\u5242", "\u65e0\u6eb6\u5242\u6280\u672f"],
    },
    {
        "code": "9671LE",
        "name": "3M 9671LE",
        "category_name": CATEGORY_NO_SUBSTRATE,
        "thickness": 0.06,
        "color_name": "\u900f\u660e",
        "adhesive_type_name": "\u4e19\u70ef\u9178",
        "base_material_name": "\u65e0\u57fa\u6750",
        "liner": "83\u53f7PCK",
        "special_applications": lines("\u65e0\u57fa\u6750\u8d85\u8584\u7ed3\u6784\uff0c\u9002\u5408\u96be\u7c98\u8868\u9762\u8584\u578b\u8d34\u5408\u3002"),
        "application_tags": ["\u96be\u7c98\u6750\u6599\u7c98\u63a5", "\u7535\u5b50\u90e8\u4ef6\u56fa\u5b9a"],
        "feature_tags": ["\u4f4e\u8868\u9762\u80fd\u7c98\u63a5", "\u9ad8\u521d\u7c98", "\u9ad8\u6297\u526a\u5f3a\u5ea6", "\u6613\u6a21\u5207", "\u65e0\u9700\u5e95\u6f06\u5242", "\u65e0\u6eb6\u5242\u6280\u672f"],
    },
    {
        "code": "93010LE",
        "name": "3M 93010LE",
        "category_name": CATEGORY_PET_DOUBLE,
        "thickness": 0.10,
        "color_name": "\u900f\u660e",
        "adhesive_type_name": "\u4e19\u70ef\u9178",
        "base_material_name": "PET",
        "liner": "58\u53f7PCK",
        "special_applications": lines("\u5851\u6599\u7c98\u5408\u91d1\u5c5e\u3002", "\u6709\u52a9\u4e8e\u589e\u52a0\u4ea7\u54c1\u8010\u7528\u6027\u3002"),
        "application_tags": ["\u96be\u7c98\u6750\u6599\u7c98\u63a5", "\u6c7d\u8f66\u5185\u9970\u7c98\u63a5", "\u5851\u6599\u7c98\u5408\u91d1\u5c5e"],
        "feature_tags": ["\u4f4e\u8868\u9762\u80fd\u7c98\u63a5", "\u9ad8\u521d\u7c98", "\u9ad8\u6297\u526a\u5f3a\u5ea6", "\u6613\u6a21\u5207", "\u65e0\u9700\u5e95\u6f06\u5242", "\u65e0\u6eb6\u5242\u6280\u672f"],
    },
    {
        "code": "9472LE",
        "name": "3M 9472LE",
        "category_name": CATEGORY_NO_SUBSTRATE,
        "thickness": 0.13,
        "color_name": "\u900f\u660e",
        "adhesive_type_name": "\u4e19\u70ef\u9178",
        "base_material_name": "\u65e0\u57fa\u6750",
        "liner": "58\u53f7PCK",
        "special_applications": lines("\u65e0\u57fa\u6750\u7ed3\u6784\uff0c\u9002\u5408\u9700\u8981\u66f4\u9ad8\u8d34\u670d\u6027\u7684\u96be\u7c98\u6750\u6599\u8584\u578b\u7c98\u63a5\u3002"),
        "application_tags": ["\u96be\u7c98\u6750\u6599\u7c98\u63a5", "\u7535\u5b50\u90e8\u4ef6\u56fa\u5b9a"],
        "feature_tags": ["\u4f4e\u8868\u9762\u80fd\u7c98\u63a5", "\u9ad8\u521d\u7c98", "\u9ad8\u6297\u526a\u5f3a\u5ea6", "\u6613\u6a21\u5207", "\u65e0\u9700\u5e95\u6f06\u5242", "\u65e0\u6eb6\u5242\u6280\u672f"],
    },
    {
        "code": "9672LE",
        "name": "3M 9672LE",
        "category_name": CATEGORY_NO_SUBSTRATE,
        "thickness": 0.13,
        "color_name": "\u900f\u660e",
        "adhesive_type_name": "\u4e19\u70ef\u9178",
        "base_material_name": "\u65e0\u57fa\u6750",
        "liner": "83\u53f7PCK",
        "special_applications": lines("\u65e0\u57fa\u6750\u7ed3\u6784\uff0c\u9002\u5408\u6a21\u5207\u548c\u7cbe\u5bc6\u90e8\u4ef6\u8d34\u5408\u3002"),
        "application_tags": ["\u96be\u7c98\u6750\u6599\u7c98\u63a5", "\u7535\u5b50\u90e8\u4ef6\u56fa\u5b9a"],
        "feature_tags": ["\u4f4e\u8868\u9762\u80fd\u7c98\u63a5", "\u9ad8\u521d\u7c98", "\u9ad8\u6297\u526a\u5f3a\u5ea6", "\u6613\u6a21\u5207", "\u65e0\u9700\u5e95\u6f06\u5242", "\u65e0\u6eb6\u5242\u6280\u672f"],
    },
    {
        "code": "93015LE",
        "name": "3M 93015LE",
        "category_name": CATEGORY_PET_DOUBLE,
        "thickness": 0.15,
        "color_name": "\u900f\u660e",
        "adhesive_type_name": "\u4e19\u70ef\u9178",
        "base_material_name": "PET",
        "liner": "58\u53f7PCK",
        "special_applications": lines(
            "\u7c98\u5408\u5851\u6599\u5f2f\u66f2\u8868\u9762\u3002",
            "\u53ef\u5feb\u901f\u7c98\u5408\u66f2\u9762\u5851\u6599\u4e0e\u6ce1\u68c9\u6216\u5851\u6599\u3002",
            "\u5265\u79bb\u529b\u6458\u8981\uff1a\u4e0d\u9508\u94a2 12.6 N/cm\uff1bABS\u5851\u6599 9.7 N/cm\uff1bPC 6.7 N/cm\uff1bPP 9.0 N/cm\u3002",
        ),
        "application_tags": ["\u96be\u7c98\u6750\u6599\u7c98\u63a5", "\u6c7d\u8f66\u5185\u9970\u7c98\u63a5", "\u66f2\u9762\u5851\u6599\u7c98\u63a5"],
        "feature_tags": ["\u4f4e\u8868\u9762\u80fd\u7c98\u63a5", "\u9ad8\u521d\u7c98", "\u9ad8\u6297\u526a\u5f3a\u5ea6", "\u6297\u8d77\u7fd8", "\u6613\u6a21\u5207", "\u65e0\u9700\u5e95\u6f06\u5242", "\u65e0\u6eb6\u5242\u6280\u672f"],
    },
    {
        "code": "9495LE",
        "name": "3M 9495LE",
        "category_name": CATEGORY_PET_DOUBLE,
        "thickness": 0.17,
        "color_name": "\u900f\u660e",
        "adhesive_type_name": "\u4e19\u70ef\u9178",
        "base_material_name": "PET",
        "liner": "58\u53f7PCK",
        "special_applications": lines("\u91d1\u5c5e\u7c98\u5408\u5851\u6599\u3002", "\u9002\u5408\u517c\u987e\u5916\u89c2\u8bbe\u8ba1\u4e0e\u9ad8\u79d1\u6280\u98ce\u683c\u7684\u7ed3\u6784\u7c98\u63a5\u3002"),
        "application_tags": ["\u96be\u7c98\u6750\u6599\u7c98\u63a5", "\u7535\u5b50\u90e8\u4ef6\u56fa\u5b9a", "\u91d1\u5c5e\u7c98\u5408\u5851\u6599"],
        "feature_tags": ["\u4f4e\u8868\u9762\u80fd\u7c98\u63a5", "\u9ad8\u521d\u7c98", "\u9ad8\u6297\u526a\u5f3a\u5ea6", "\u6613\u6a21\u5207", "\u65e0\u9700\u5e95\u6f06\u5242", "\u65e0\u6eb6\u5242\u6280\u672f"],
    },
    {
        "code": "93020LE",
        "name": "3M 93020LE",
        "category_name": CATEGORY_PET_DOUBLE,
        "thickness": 0.20,
        "color_name": "\u900f\u660e",
        "adhesive_type_name": "\u4e19\u70ef\u9178",
        "base_material_name": "PET",
        "liner": "58\u53f7PCK",
        "special_applications": lines("\u5851\u6599\u7c98\u5408\u7c89\u672b\u6d82\u5c42\u91d1\u5c5e\u3002", "\u63d0\u4f9b\u6301\u4e45\u7c98\u63a5\u5f3a\u5ea6\uff0c\u4e5f\u9002\u7528\u4e8e\u5f2f\u66f2\u8868\u9762\u3002"),
        "application_tags": ["\u96be\u7c98\u6750\u6599\u7c98\u63a5", "\u5bb6\u7535\u90e8\u4ef6\u7c98\u63a5", "\u5851\u6599\u7c98\u5408\u7c89\u672b\u6d82\u5c42\u91d1\u5c5e"],
        "feature_tags": ["\u4f4e\u8868\u9762\u80fd\u7c98\u63a5", "\u9ad8\u521d\u7c98", "\u9ad8\u6297\u526a\u5f3a\u5ea6", "\u6297\u8d77\u7fd8", "\u6613\u6a21\u5207", "\u65e0\u9700\u5e95\u6f06\u5242", "\u65e0\u6eb6\u5242\u6280\u672f"],
    },
]

COMMON_PEEL_COMPARISON = [("\u4e0d\u9508\u94a2", "12.6"), ("ABS\u5851\u6599", "9.7"), ("PC", "6.7"), ("PP", "9.0")]
COMMON_PEEL_SUMMARY = "\uff1b".join(
    f"{substrate} {value} N/cm" for substrate, value in COMMON_PEEL_COMPARISON
)
COMMON_SHARED_SPECS = [
    {
        "param_key": "adhesion_hse_level",
        "name": "\u9ad8\u8868\u9762\u80fd\u7c98\u63a5\u7b49\u7ea7",
        "spec_category_name": "\u7c98\u63a5\u6027\u80fd",
        "value_type": "char",
        "preferred_unit": False,
        "value": "\u9ad8",
    },
    {
        "param_key": "adhesion_lse_level",
        "name": "\u4f4e\u8868\u9762\u80fd\u7c98\u63a5\u7b49\u7ea7",
        "spec_category_name": "\u7c98\u63a5\u6027\u80fd",
        "value_type": "char",
        "preferred_unit": False,
        "value": "\u9ad8",
    },
    {
        "param_key": "long_term_heat_resistance",
        "name": "\u957f\u671f\u8010\u6e29",
        "spec_category_name": "\u8010\u4e45\u6027",
        "value_type": "float",
        "preferred_unit": "\u00b0C",
        "value": "93",
        "unit": "\u00b0C",
    },
    {
        "param_key": "short_term_heat_resistance",
        "name": "\u77ed\u671f\u8010\u6e29",
        "spec_category_name": "\u8010\u4e45\u6027",
        "value_type": "float",
        "preferred_unit": "\u00b0C",
        "value": "149",
        "unit": "\u00b0C",
    },
    {
        "param_key": "solvent_resistance_level",
        "name": "\u8010\u6eb6\u5242\u6027\u7b49\u7ea7",
        "spec_category_name": "\u8010\u4e45\u6027",
        "value_type": "char",
        "preferred_unit": False,
        "value": "\u4e2d",
    },
]


def build_payload():
    payload = {
        "series": [
            {
                "series_name": SERIES_NAME,
                "brand_name": BRAND_NAME,
                "category_name": CATEGORY_PET_DOUBLE,
                "name": SERIES_NAME,
                "product_description": COMMON_DESCRIPTION,
                "product_features": COMMON_FEATURES,
                "main_applications": COMMON_APPLICATIONS,
                "special_applications": COMMON_SPECIAL,
                "source_page": 1,
                "source_text": SOURCE_NAME,
                "source_label": "manual_visual_import",
            }
        ],
        "items": [],
        "params": [
            {
                "param_key": "liner_description",
                "name": "\u79bb\u578b\u6750\u6599",
                "spec_category_name": "\u7ed3\u6784\u4e0e\u79bb\u578b",
                "value_type": "char",
                "preferred_unit": False,
                "is_main_field": False,
                "main_field_name": False,
            },
            {
                "param_key": "peel_strength_180",
                "name": "180\u00b0\u5265\u79bb\u529b",
                "spec_category_name": "\u7c98\u63a5\u6027\u80fd",
                "value_type": "float",
                "preferred_unit": "N/cm",
                "is_main_field": False,
                "main_field_name": False,
            },
        ]
        + [
            {
                "param_key": spec["param_key"],
                "name": spec["name"],
                "spec_category_name": spec["spec_category_name"],
                "value_type": spec["value_type"],
                "preferred_unit": spec.get("preferred_unit"),
                "is_main_field": False,
                "main_field_name": False,
            }
            for spec in COMMON_SHARED_SPECS
        ],
        "category_params": [],
        "spec_values": [],
        "unmatched": [],
    }

    for category_name in [CATEGORY_PET_DOUBLE, CATEGORY_NO_SUBSTRATE]:
        payload["category_params"].append(
            {
                "category_name": category_name,
                "categ_name": category_name,
                "param_key": "liner_description",
                "name": "\u79bb\u578b\u6750\u6599",
                "required": False,
                "show_in_form": True,
                "allow_import": True,
            }
        )
        payload["category_params"].append(
            {
                "category_name": category_name,
                "categ_name": category_name,
                "param_key": "peel_strength_180",
                "name": "180\u00b0\u5265\u79bb\u529b",
                "required": False,
                "show_in_form": True,
                "allow_import": True,
            }
        )

    sequence = 10
    for row in ITEM_ROWS:
        payload["items"].append(
            {
                "code": row["code"],
                "name": row["name"],
                "brand_name": BRAND_NAME,
                "series_name": SERIES_NAME,
                "category_name": row["category_name"],
                "catalog_status": "published",
                "active": True,
                "sequence": sequence,
                "thickness": float_or_false(row["thickness"]),
                "color_name": row["color_name"],
                "adhesive_type_name": row["adhesive_type_name"],
                "base_material_name": row["base_material_name"],
                "product_features": COMMON_FEATURES,
                "product_description": COMMON_DESCRIPTION,
                "main_applications": COMMON_APPLICATIONS,
                "special_applications": row["special_applications"],
                "source_page": 1,
                "source_text": row["code"],
                "source_label": "manual_visual_import",
            }
        )
        payload["spec_values"].append(
            {
                "item_code": row["code"],
                "param_key": "liner_description",
                "value": row["liner"],
                "source_page": 1,
                "source_text": row["code"],
                "source_label": "manual_visual_import",
                "source_excerpt": f"{row['code']} \u79bb\u578b\u7eb8 {row['liner']}",
                "review_status": "pending",
            }
        )
        sequence += 10

    for row in ITEM_ROWS:
        for spec in COMMON_SHARED_SPECS:
            payload["spec_values"].append(
                {
                    "item_code": row["code"],
                    "param_key": spec["param_key"],
                    "value": spec["value"],
                    "unit": spec.get("unit"),
                    "source_page": 1,
                    "source_text": row["code"],
                    "source_label": "manual_visual_import",
                    "source_excerpt": f"{row['code']} {spec['name']} {spec['value']}{(' ' + spec['unit']) if spec.get('unit') else ''}",
                    "review_status": "pending",
                }
            )
        for substrate, value in COMMON_PEEL_COMPARISON:
            payload["spec_values"].append(
                {
                    "item_code": row["code"],
                    "param_key": "peel_strength_180",
                    "value": value,
                    "unit": "N/cm",
                    "test_condition": "180\u00b0\u5265\u79bb\u529b\uff0c\u5ba4\u6e29\u4e0b\uff0870\u2103\u4e0b\u6d78\u6da672\u5c0f\u65f6\uff09",
                    "conditions": [
                        {
                            "condition_key": "substrate",
                            "condition_label": "\u88ab\u8d34\u5408\u7269",
                            "condition_value": substrate,
                        },
                        {
                            "condition_key": "state",
                            "condition_label": "\u72b6\u6001",
                            "condition_value": "\u9ad8\u6e29\u6d78\u6da672\u5c0f\u65f6\u540e",
                        },
                    ],
                    "source_page": 1,
                    "source_text": row["code"],
                    "source_label": "manual_visual_import",
                    "source_excerpt": f"{row['code']} \u5265\u79bb\u529b\u5bf9\u6bd4\uff1a{COMMON_PEEL_SUMMARY}",
                    "review_status": "pending",
                }
            )
    return payload


def upsert_source_document(payload):
    brand = env["diecut.brand"].sudo().search([("name", "=", BRAND_NAME)], limit=1)
    source = env["diecut.catalog.source.document"].sudo().search([("name", "=", SOURCE_NAME)], limit=1)
    vals = {
        "name": SOURCE_NAME,
        "source_type": "pdf",
        "source_filename": PDF_PATH.name,
        "brand_id": brand.id or False,
        "import_status": "generated",
        "parse_version": "manual-vision-v1",
        "draft_payload": json.dumps(payload, ensure_ascii=False, indent=2),
        "unmatched_payload": "[]",
        "result_message": "\u57fa\u4e8e PDF \u9875\u9762\u8868\u683c\u4e0e\u5e94\u7528\u793a\u610f\u4eba\u5de5\u6821\u6838\u751f\u6210\u7684 3M 300LSE \u6c7d\u8f66\u5e94\u7528\u624b\u518c\u5bfc\u5165\u8349\u7a3f\u3002",
    }
    if source:
        source.write(vals)
    else:
        source = env["diecut.catalog.source.document"].sudo().create(vals)

    attachment_model = env["ir.attachment"].sudo()
    datas = base64.b64encode(PDF_PATH.read_bytes()).decode()
    mimetype = mimetypes.guess_type(str(PDF_PATH))[0] or "application/pdf"
    attachment = attachment_model.search(
        [
            ("res_model", "=", "diecut.catalog.source.document"),
            ("res_id", "=", source.id),
            ("res_field", "=", False),
            ("name", "=", PDF_PATH.name),
        ],
        limit=1,
    )
    if attachment:
        attachment.write({"datas": datas, "mimetype": mimetype, "type": "binary"})
    else:
        attachment = attachment_model.create(
            {
                "name": PDF_PATH.name,
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
            "source_filename": PDF_PATH.name,
        }
    )
    return source


def get_or_create(model_name, name, aliases=None):
    if not name:
        return False
    model = env[model_name].sudo()
    record = model.search([("name", "=", name)], limit=1)
    alias_text = "\n".join(str(alias).strip() for alias in aliases or [] if str(alias).strip()) or False
    if record:
        if alias_text and "alias_text" in model._fields:
            merged = [part for part in [record.alias_text or "", alias_text] if part]
            record.write({"alias_text": "\n".join(merged)})
        return record
    vals = {"name": name}
    if alias_text and "alias_text" in model._fields:
        vals["alias_text"] = alias_text
    return model.create(vals)


def sync_item_fields_and_tags():
    item_model = env["diecut.catalog.item"].sudo()
    series_model = env["diecut.catalog.series"].sudo()
    param_model = env["diecut.catalog.param"].sudo()

    series = series_model.search([("name", "=", SERIES_NAME), ("brand_id.name", "=", BRAND_NAME)], limit=1)
    function_tag = get_or_create("product.tag", "\u7c98\u63a5\u56fa\u5b9a", aliases=["\u7ed3\u6784\u56fa\u5b9a"])
    application_meta = {
        "\u96be\u7c98\u6750\u6599\u7c98\u63a5": ["\u4f4e\u8868\u9762\u80fd\u6750\u6599\u7c98\u63a5", "\u96be\u7c98\u8868\u9762\u7c98\u63a5"],
        "\u6c7d\u8f66\u5185\u9970\u7c98\u63a5": ["\u6c7d\u8f66\u5e02\u573a\u96be\u7c98\u6750\u6599\u7c98\u5408"],
        "\u7535\u5b50\u90e8\u4ef6\u56fa\u5b9a": ["\u7535\u5b50\u5e02\u573a\u96be\u7c98\u6750\u6599\u7c98\u5408", "\u8d85\u8584\u624b\u673a\u8bbe\u8ba1"],
        "\u5bb6\u7535\u90e8\u4ef6\u7c98\u63a5": ["\u5bb6\u7535\u5e02\u573a\u96be\u7c98\u6750\u6599\u7c98\u5408"],
        "\u533b\u7597\u8bbe\u5907\u7c98\u63a5": ["\u533b\u7597\u5e02\u573a\u96be\u7c98\u6750\u6599\u7c98\u5408"],
        "\u66f2\u9762\u5851\u6599\u7c98\u63a5": ["\u7c98\u5408\u5851\u6599\u5f2f\u66f2\u8868\u9762", "\u66f2\u9762\u5851\u6599\u8d34\u5408"],
        "\u5851\u6599\u7c98\u5408\u91d1\u5c5e": [],
        "\u91d1\u5c5e\u7f51\u7eb1\u7c98\u63a5\u5851\u6599": [],
        "\u91d1\u5c5e\u7c98\u5408\u5851\u6599": ["\u5408\u91d1\u7c98\u5408\u5851\u6599"],
        "\u5851\u6599\u7c98\u5408\u7c89\u672b\u6d82\u5c42\u91d1\u5c5e": [],
        "\u5851\u6599\u7c98\u5408\u5851\u6599": [],
    }
    feature_meta = {
        "\u4f4e\u8868\u9762\u80fd\u7c98\u63a5": ["LSE\u7c98\u63a5"],
        "\u9ad8\u521d\u7c98": ["\u9ad8\u521d\u59cb\u7c98\u5408\u5f3a\u5ea6"],
        "\u9ad8\u6297\u526a\u5f3a\u5ea6": [],
        "\u6297\u8d77\u7fd8": ["\u4f18\u5f02\u7684\u6297\u8d77\u7fd8\u6027\u80fd"],
        "\u6613\u6a21\u5207": ["\u65b9\u4fbf\u6a21\u5207", "\u4fbf\u4e8e\u6a21\u5207\u52a0\u5de5"],
        "\u65e0\u9700\u5e95\u6f06\u5242": ["\u65e0\u9700\u5e95\u6f06"],
        "\u65e0\u6eb6\u5242\u6280\u672f": ["\u65e0\u6eb6\u5242"],
    }

    app_tags = {name: get_or_create("diecut.catalog.application.tag", name, aliases) for name, aliases in application_meta.items()}
    feature_tags = {name: get_or_create("diecut.catalog.feature.tag", name, aliases) for name, aliases in feature_meta.items()}
    peel_param = param_model.search([("param_key", "=", "peel_strength_180")], limit=1)
    shared_spec_params = {
        spec["param_key"]: param_model.search([("param_key", "=", spec["param_key"])], limit=1)
        for spec in COMMON_SHARED_SPECS
    }
    legacy_peel_params = param_model.search([("param_key", "in", ["peel_strength", "foil_peel_strength"])])

    if peel_param:
        peel_param.write(
            {
                "name": "180\u00b0\u5265\u79bb\u529b",
                "canonical_name_zh": "180\u00b0\u5265\u79bb\u529b",
                "aliases_text": lines("\u5265\u79bb\u529b", "180\u5ea6\u5265\u79bb\u529b", "180 peel"),
                "condition_schema_json": json.dumps(
                    [
                        {"condition_key": "substrate", "label": "\u88ab\u8d34\u5408\u7269", "sequence": 10},
                        {"condition_key": "state", "label": "\u72b6\u6001", "sequence": 20},
                        {"condition_key": "temperature", "label": "\u6e29\u5ea6", "sequence": 30},
                        {"condition_key": "dwell_time", "label": "\u9a7b\u7559\u65f6\u95f4", "sequence": 40},
                    ],
                    ensure_ascii=False,
                ),
                "description": lines(
                    "\u6807\u51c6\u5316\u4e3b\u53c2\u6570\uff1a180\u00b0\u5265\u79bb\u529b\u3002",
                    "\u88ab\u8d34\u5408\u7269\u3001\u72b6\u6001\u3001\u6e29\u5ea6\u3001\u9a7b\u7559\u65f6\u95f4\u8bf7\u5199\u5165\u6761\u4ef6\u660e\u7ec6\uff0c\u4e0d\u518d\u62c6\u6210\u591a\u4e2a param_key\u3002",
                ),
            }
        )
    for legacy_param in legacy_peel_params:
        legacy_param.write(
            {
                "description": lines(
                    legacy_param.description,
                    "\u5386\u53f2\u517c\u5bb9\u53c2\u6570\uff0c\u65b0\u6570\u636e\u8bf7\u4f18\u5148\u4f7f\u7528 peel_strength_180 \u5e76\u4f7f\u7528 conditions \u627f\u8f7d\u88ab\u8d34\u5408\u7269/\u72b6\u6001\u7b49\u6761\u4ef6\u3002",
                ),
            }
        )

    if series:
        series.write(
            {
                "product_features": COMMON_FEATURES,
                "product_description": COMMON_DESCRIPTION,
                "main_applications": COMMON_APPLICATIONS,
                "default_function_tag_ids": [Command.set([function_tag.id])],
                "default_application_tag_ids": [
                    Command.set(
                        sorted(
                            {
                                app_tags[name].id
                                for name in [
                                    "\u96be\u7c98\u6750\u6599\u7c98\u63a5",
                                    "\u6c7d\u8f66\u5185\u9970\u7c98\u63a5",
                                    "\u7535\u5b50\u90e8\u4ef6\u56fa\u5b9a",
                                    "\u5bb6\u7535\u90e8\u4ef6\u7c98\u63a5",
                                ]
                                if app_tags.get(name)
                            }
                        )
                    )
                ],
                "default_feature_tag_ids": [Command.set(sorted({tag.id for tag in feature_tags.values() if tag}))],
            }
        )

    for row in ITEM_ROWS:
        item = item_model.search([("brand_id.name", "=", BRAND_NAME), ("code", "=", row["code"])], limit=1)
        if not item:
            continue
        color = get_or_create("diecut.color", row["color_name"])
        adhesive = get_or_create("diecut.catalog.adhesive.type", row["adhesive_type_name"])
        base_material = get_or_create("diecut.catalog.base.material", row["base_material_name"])
        item.write(
            {
                "thickness": str(row["thickness"]),
                "color_id": color.id if color else False,
                "adhesive_type_id": adhesive.id if adhesive else False,
                "base_material_id": base_material.id if base_material else False,
                "special_applications": row["special_applications"],
                "product_features": COMMON_FEATURES,
                "product_description": COMMON_DESCRIPTION,
                "main_applications": COMMON_APPLICATIONS,
                "override_product_features": True,
                "override_product_description": True,
                "override_main_applications": True,
                "function_tag_ids": [Command.set([function_tag.id])],
                "application_tag_ids": [
                    Command.set(sorted({app_tags[tag_name].id for tag_name in row["application_tags"] if app_tags.get(tag_name)}))
                ],
                "feature_tag_ids": [
                    Command.set(sorted({feature_tags[tag_name].id for tag_name in row["feature_tags"] if feature_tags.get(tag_name)}))
                ],
            }
        )
        if legacy_peel_params:
            item.spec_line_ids.filtered(lambda line: line.param_id in legacy_peel_params).unlink()
        for spec in COMMON_SHARED_SPECS:
            param = shared_spec_params.get(spec["param_key"])
            if not param:
                continue
            item.apply_param_payload(
                param=param,
                raw_value=spec["value"],
                unit=spec.get("unit"),
                source_excerpt=f"{item.code} {spec['name']} {spec['value']}{(' ' + spec['unit']) if spec.get('unit') else ''}",
            )
        if peel_param:
            for substrate, value in COMMON_PEEL_COMPARISON:
                item.apply_param_payload(
                    param=peel_param,
                    raw_value=value,
                    unit="N/cm",
                    test_condition="180\u00b0\u5265\u79bb\u529b\uff0c\u5ba4\u6e29\u4e0b\uff0870\u2103\u4e0b\u6d78\u6da672\u5c0f\u65f6\uff09",
                    source_excerpt=f"{item.code} \u5265\u79bb\u529b\u5bf9\u6bd4\uff1a{COMMON_PEEL_SUMMARY}",
                    conditions=[
                        {
                            "condition_key": "substrate",
                            "condition_label": "\u88ab\u8d34\u5408\u7269",
                            "condition_value": substrate,
                        },
                        {
                            "condition_key": "state",
                            "condition_label": "\u72b6\u6001",
                            "condition_value": "\u9ad8\u6e29\u6d78\u6da672\u5c0f\u65f6\u540e",
                        },
                    ],
                )


def main():
    if not PDF_PATH.exists():
        raise FileNotFoundError(f"pdf not found: {PDF_PATH}")

    payload = build_payload()
    DRAFT_PATH.parent.mkdir(parents=True, exist_ok=True)
    DRAFT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    source = upsert_source_document(payload)
    source._run_encoding_precheck(payload)
    source.action_validate_draft()
    source.action_apply_draft()
    sync_item_fields_and_tags()
    env.cr.commit()

    print("source_id=%s" % source.id)
    print("draft_path=%s" % DRAFT_PATH)
    print("series_count=%s" % len(payload["series"]))
    print("item_count=%s" % len(payload["items"]))
    print("param_count=%s" % len(payload["params"]))
    print("spec_count=%s" % len(payload["spec_values"]))


main()
