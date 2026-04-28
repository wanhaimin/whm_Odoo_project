# -*- coding: utf-8 -*-
"""catalog.item → Dify 产品库同步服务

每个 catalog.item 同步成 Dify 中的一份独立 document：
  - name = "[品牌] 型号 - 名称"
  - text = 自动生成的 markdown，含基础属性 + 系列说明 + 全部 spec_line（参数/单位/测试方法）
  - metadata = brand / category / status / 标签 / 物理属性

设计要点：
- 与文章同步独立：不共用 sync_log 模型（产品量级大，独立日志会更清晰；后续可加）
- 写入时只标 sync_status=pending，真正网络调用走 cron 或手动按钮
- min_status 阈值：低于阈值的产品标 skipped（如默认仅同步 published）
"""

import json
import logging
from datetime import datetime
from typing import Optional

from .dify_client import DifyClient

_logger = logging.getLogger(__name__)

_STATUS_RANK = {"draft": 0, "review": 1, "published": 2, "deprecated": -1}


class DifyProductSync:
    PARAM_BASE_URL = "diecut_knowledge.dify_base_url"
    PARAM_API_KEY = "diecut_knowledge.dify_api_key"
    PARAM_DATASET = "diecut_knowledge.dify_products_dataset_id"
    PARAM_BATCH = "diecut_knowledge.dify_products_batch_limit"
    PARAM_MIN_STATUS = "diecut_knowledge.dify_products_min_status"

    def __init__(self, env):
        self.env = env

    # --------------------------- public -------------------------------------

    def sync_item(self, item) -> dict:
        item.ensure_one()
        client, dataset_id = self._build_client_and_dataset()

        if item.active is False and item.dify_document_id:
            return self._do_delete(item, client, dataset_id)

        if not self._should_sync(item):
            self._mark(item, "skipped", "低于同步阈值（catalog_status）")
            return {"ok": True, "action": "skip", "error": None}

        if not client:
            self._mark(item, "failed", "Dify 未配置（base_url / api_key 缺失）")
            return {"ok": False, "action": "noop", "error": "dify not configured"}
        if not dataset_id:
            self._mark(item, "failed", "未配置产品库 Dataset ID")
            return {"ok": False, "action": "noop", "error": "products dataset not configured"}

        if item.dify_document_id and item.dify_dataset_id == dataset_id:
            return self._do_update(item, client, dataset_id)
        if item.dify_document_id and item.dify_dataset_id != dataset_id:
            self._do_delete(item, client, item.dify_dataset_id)
            return self._do_create(item, client, dataset_id)
        return self._do_create(item, client, dataset_id)

    def sync_pending(self, limit: Optional[int] = None) -> dict:
        if limit is None:
            limit = int(self._get_param(self.PARAM_BATCH, default="50") or 50)

        Item = self.env["diecut.catalog.item"]
        targets = Item.search(
            [("dify_sync_status", "in", ("pending", "failed"))],
            limit=limit,
            order="write_date asc, id asc",
        )
        # 已删除/归档但还有 dify_document_id 的，也补一刀
        archived = Item.with_context(active_test=False).search(
            [("active", "=", False), ("dify_document_id", "!=", False), ("dify_sync_status", "=", "pending")],
            limit=max(0, limit - len(targets)),
        )
        all_targets = targets | archived

        ok_count, fail_count = 0, 0
        for item in all_targets:
            result = self.sync_item(item)
            if result.get("ok"):
                ok_count += 1
            else:
                fail_count += 1
        return {"total": len(all_targets), "ok": ok_count, "failed": fail_count}

    # --------------------------- actions ------------------------------------

    def _do_create(self, item, client: DifyClient, dataset_id: str) -> dict:
        text, metadata, doc_name = self._build_payload(item)
        ok, payload, error, _dur = client.create_document_by_text(
            dataset_id=dataset_id,
            name=doc_name,
            text=text,
            metadata=metadata,
        )
        if not ok:
            self._mark(item, "failed", error)
            return {"ok": False, "action": "create", "error": error}

        document = (payload or {}).get("document") or {}
        document_id = document.get("id") or (payload or {}).get("id")
        item.sudo().write({
            "dify_sync_status": "synced",
            "dify_dataset_id": dataset_id,
            "dify_document_id": document_id,
            "dify_last_sync_at": datetime.now(),
            "dify_sync_error": False,
        })
        return {"ok": True, "action": "create", "error": None}

    def _do_update(self, item, client: DifyClient, dataset_id: str) -> dict:
        text, _metadata, doc_name = self._build_payload(item)
        ok, payload, error, _dur = client.update_document_by_text(
            dataset_id=dataset_id,
            document_id=item.dify_document_id,
            name=doc_name,
            text=text,
        )
        if not ok:
            if "not_found" in (error or "").lower() or "404" in (error or ""):
                item.sudo().write({"dify_document_id": False, "dify_dataset_id": False})
                return self._do_create(item, client, dataset_id)
            self._mark(item, "failed", error)
            return {"ok": False, "action": "update", "error": error}

        item.sudo().write({
            "dify_sync_status": "synced",
            "dify_last_sync_at": datetime.now(),
            "dify_sync_error": False,
        })
        return {"ok": True, "action": "update", "error": None}

    def _do_delete(self, item, client: Optional[DifyClient], dataset_id: Optional[str]) -> dict:
        if not (client and dataset_id and item.dify_document_id):
            item.sudo().write({"dify_sync_status": "synced"})
            return {"ok": True, "action": "noop", "error": None}
        ok, payload, error, _dur = client.delete_document(dataset_id, item.dify_document_id)
        if not ok and "not_found" not in (error or "").lower() and "404" not in (error or ""):
            self._mark(item, "failed", error)
            return {"ok": False, "action": "delete", "error": error}
        item.sudo().write({
            "dify_sync_status": "synced",
            "dify_document_id": False,
            "dify_last_sync_at": datetime.now(),
            "dify_sync_error": False,
        })
        return {"ok": True, "action": "delete", "error": None}

    # --------------------------- payload ------------------------------------

    def _build_payload(self, item) -> tuple:
        sections = []
        sections.append(self._section_basic(item))
        if item.product_features or item.product_description or item.main_applications:
            sections.append(self._section_series(item))
        if item.spec_line_ids:
            sections.append(self._section_specs(item))
        if item.equivalent_type:
            sections.append(f"## 替代类型\n\n{item.equivalent_type.strip()}")
        text = "\n\n".join(filter(None, sections)).strip() or item.code or item.name

        metadata = {
            "odoo_id": item.id,
            "odoo_model": "diecut.catalog.item",
            "brand": item.brand_id.name if item.brand_id else "",
            "code": item.code or "",
            "name": item.name or "",
            "series": item.series_id.name if item.series_id else "",
            "category": item.categ_id.name if item.categ_id else "",
            "manufacturer": item.manufacturer_id.name if item.manufacturer_id else "",
            "color": item.color_id.name if item.color_id else "",
            "adhesive_type": item.adhesive_type_id.name if item.adhesive_type_id else "",
            "base_material": item.base_material_id.name if item.base_material_id else "",
            "thickness": item.thickness or "",
            "thickness_std": item.thickness_std or "",
            "fire_rating": item.fire_rating or "",
            "is_rohs": item.is_rohs,
            "is_reach": item.is_reach,
            "is_halogen_free": item.is_halogen_free,
            "catalog_status": item.catalog_status or "",
            "tags_function": ", ".join(item.effective_function_tag_ids.mapped("name")) if item.effective_function_tag_ids else "",
            "tags_application": ", ".join(item.effective_application_tag_ids.mapped("name")) if item.effective_application_tag_ids else "",
            "tags_feature": ", ".join(item.effective_feature_tag_ids.mapped("name")) if item.effective_feature_tag_ids else "",
        }
        metadata = {k: ("" if v is None else (str(v) if not isinstance(v, bool) else ("是" if v else "否"))) for k, v in metadata.items()}

        brand_prefix = f"[{item.brand_id.name}] " if item.brand_id else ""
        doc_name = f"{brand_prefix}{item.code or ''} - {item.name or ''}".strip(" -")[:200]
        return text, metadata, doc_name

    def _section_basic(self, item) -> str:
        rows = []
        rows.append(f"# {item.code or '(无型号)'} {item.name or ''}".strip())
        rows.append("")
        rows.append("## 基础属性\n")
        if item.brand_id:
            rows.append(f"- **品牌**: {item.brand_id.name}")
        if item.series_id:
            rows.append(f"- **系列**: {item.series_id.name}")
        if item.manufacturer_id:
            rows.append(f"- **制造商**: {item.manufacturer_id.name}")
        if item.categ_id:
            rows.append(f"- **材料分类**: {item.categ_id.name}")
        if item.thickness:
            std_part = f" (标准: {item.thickness_std})" if item.thickness_std else ""
            rows.append(f"- **厚度**: {item.thickness}{std_part}")
        if item.adhesive_thickness:
            rows.append(f"- **胶层厚**: {item.adhesive_thickness}")
        if item.color_id:
            rows.append(f"- **颜色**: {item.color_id.name}")
        if item.adhesive_type_id:
            rows.append(f"- **胶系**: {item.adhesive_type_id.name}")
        if item.base_material_id:
            rows.append(f"- **基材**: {item.base_material_id.name}")
        if item.fire_rating and item.fire_rating != "none":
            rows.append(f"- **防火等级**: {item.fire_rating}")
        flags = []
        if item.is_rohs:
            flags.append("RoHS")
        if item.is_reach:
            flags.append("REACH")
        if item.is_halogen_free:
            flags.append("无卤")
        if flags:
            rows.append(f"- **合规**: {' / '.join(flags)}")
        if item.catalog_status:
            rows.append(f"- **目录状态**: {item.catalog_status}")
        return "\n".join(rows)

    def _section_series(self, item) -> str:
        from ..models.kb_article import DiecutKbArticle as A
        rows = ["## 系列说明"]
        if item.product_features:
            rows.append("\n### 系列特性\n")
            rows.append(A._html_to_text(item.product_features) if "<" in item.product_features else item.product_features)
        if item.product_description:
            rows.append("\n### 系列说明\n")
            rows.append(A._html_to_text(item.product_description) if "<" in item.product_description else item.product_description)
        if item.main_applications:
            rows.append("\n### 主要应用\n")
            rows.append(A._html_to_text(item.main_applications))
        if item.special_applications:
            rows.append("\n### 型号补充\n")
            rows.append(A._html_to_text(item.special_applications))
        return "\n".join(rows)

    def _section_specs(self, item) -> str:
        rows = ["## 技术参数"]
        rows.append("")
        rows.append("| 参数 | 值 | 单位 | 测试方法 | 测试条件 |")
        rows.append("| --- | --- | --- | --- | --- |")
        for line in item.spec_line_ids.sorted(key=lambda l: (l.sequence, l.id)):
            param_name = (line.param_id.name if line.param_id else line.param_name) or "-"
            value = line.value_display or "-"
            unit = line.unit or "-"
            method = line.test_method or "-"
            condition = line.test_condition or line.condition_summary or "-"
            rows.append(f"| {param_name} | {value} | {unit} | {method} | {condition} |")
        return "\n".join(rows)

    # --------------------------- helpers ------------------------------------

    def _should_sync(self, item) -> bool:
        threshold = self._get_param(self.PARAM_MIN_STATUS, default="published") or "published"
        threshold_rank = _STATUS_RANK.get(threshold, 2)
        item_rank = _STATUS_RANK.get(item.catalog_status, 0)
        return item_rank >= threshold_rank and item.active

    def _mark(self, item, status: str, error: str = ""):
        vals = {"dify_sync_status": status}
        if status == "failed":
            vals["dify_sync_error"] = (error or "")[:2000]
        elif status == "skipped":
            vals["dify_sync_error"] = False
        item.sudo().write(vals)

    def _build_client_and_dataset(self) -> tuple:
        base_url = self._get_param(self.PARAM_BASE_URL)
        api_key = self._get_param(self.PARAM_API_KEY)
        dataset_id = self._get_param(self.PARAM_DATASET)
        if not base_url or not api_key:
            return None, dataset_id
        try:
            timeout = int(self._get_param("diecut_knowledge.dify_timeout", default="30") or 30)
        except (TypeError, ValueError):
            timeout = 30
        try:
            retries = int(self._get_param("diecut_knowledge.dify_retries", default="2") or 2)
        except (TypeError, ValueError):
            retries = 2
        return DifyClient(base_url=base_url, api_key=api_key, timeout=timeout, retries=retries), dataset_id

    def _get_param(self, key: str, default: Optional[str] = None) -> Optional[str]:
        return self.env["ir.config_parameter"].sudo().get_param(key, default=default)
