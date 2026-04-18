# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import UserError


class ChatterAiHandbookReview(models.Model):
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _name = "chatter.ai.handbook.review"
    _description = "AI Handbook Review"
    _order = "create_date desc, id desc"

    name = fields.Char(required=True)
    source_document_id = fields.Many2one(
        "diecut.catalog.source.document",
        string="Source Document",
        required=True,
        ondelete="cascade",
        index=True,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("identified", "Identified"),
            ("reviewing", "Reviewing"),
            ("completed", "Completed"),
        ],
        default="identified",
        required=True,
        index=True,
    )
    family_name = fields.Char(string="Family Name")
    document_outline = fields.Text(string="Document Outline")
    summary = fields.Text(string="Summary")
    trace_id = fields.Char(string="OpenClaw Trace ID", index=True)
    confidence = fields.Float(string="Confidence")
    series_ids = fields.One2many(
        "chatter.ai.handbook.review.series",
        "review_id",
        string="Series Overview",
    )
    series_count = fields.Integer(compute="_compute_counts", string="Series Count")
    model_count = fields.Integer(compute="_compute_counts", string="Model Count")
    param_total = fields.Integer(compute="_compute_counts", string="Parameter Count")
    reused_param_count = fields.Integer(compute="_compute_counts", string="Reused Existing")
    pending_param_count = fields.Integer(compute="_compute_counts", string="Pending Review")
    issue_count = fields.Integer(compute="_compute_counts", string="Issues")

    @api.depends(
        "series_ids",
        "series_ids.model_count",
        "series_ids.param_total",
        "series_ids.reused_param_count",
        "series_ids.pending_param_count",
        "series_ids.issue_count",
    )
    def _compute_counts(self):
        for review in self:
            review.series_count = len(review.series_ids)
            review.model_count = sum(review.series_ids.mapped("model_count"))
            review.param_total = sum(review.series_ids.mapped("param_total"))
            review.reused_param_count = sum(review.series_ids.mapped("reused_param_count"))
            review.pending_param_count = sum(review.series_ids.mapped("pending_param_count"))
            review.issue_count = sum(review.series_ids.mapped("issue_count"))

    def action_open_source_document(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Source Document",
            "res_model": "diecut.catalog.source.document",
            "view_mode": "form",
            "res_id": self.source_document_id.id,
            "target": "current",
        }


class ChatterAiHandbookReviewSeries(models.Model):
    _name = "chatter.ai.handbook.review.series"
    _description = "AI Handbook Review Series"
    _order = "review_id, sequence, id"

    review_id = fields.Many2one(
        "chatter.ai.handbook.review",
        required=True,
        ondelete="cascade",
        index=True,
    )
    source_document_id = fields.Many2one(
        related="review_id.source_document_id",
        store=True,
        readonly=True,
    )
    sequence = fields.Integer(default=10)
    series_display_name = fields.Char(string="Series Display Name")
    series_long_name = fields.Char(string="Series Name", required=True)
    page_range = fields.Char(string="Pages")
    series_description = fields.Text(string="Description")
    series_features = fields.Text(string="Features")
    series_applications = fields.Text(string="Applications")
    confidence = fields.Float(string="Confidence")
    evidence = fields.Text(string="Evidence")
    model_ids = fields.One2many(
        "chatter.ai.handbook.review.model",
        "series_id",
        string="Models",
    )
    model_count = fields.Integer(compute="_compute_series_counts", string="Model Count")
    param_total = fields.Integer(compute="_compute_series_counts", string="Parameter Count")
    reused_param_count = fields.Integer(compute="_compute_series_counts", string="Reused Existing")
    pending_param_count = fields.Integer(compute="_compute_series_counts", string="Pending Review")
    issue_count = fields.Integer(compute="_compute_series_counts", string="Issues")

    @api.depends(
        "model_ids",
        "model_ids.param_total",
        "model_ids.reused_param_count",
        "model_ids.pending_param_count",
        "model_ids.issue_count",
    )
    def _compute_series_counts(self):
        for series in self:
            series.model_count = len(series.model_ids)
            series.param_total = sum(series.model_ids.mapped("param_total"))
            series.reused_param_count = sum(series.model_ids.mapped("reused_param_count"))
            series.pending_param_count = sum(series.model_ids.mapped("pending_param_count"))
            series.issue_count = sum(series.model_ids.mapped("issue_count"))

    def action_open_models(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.series_long_name,
            "res_model": "chatter.ai.handbook.review.model",
            "view_mode": "list,form",
            "domain": [("series_id", "=", self.id)],
            "target": "current",
        }


class ChatterAiHandbookReviewModel(models.Model):
    _name = "chatter.ai.handbook.review.model"
    _description = "AI Handbook Review Model"
    _order = "series_id, sequence, id"

    series_id = fields.Many2one(
        "chatter.ai.handbook.review.series",
        required=True,
        ondelete="cascade",
        index=True,
    )
    review_id = fields.Many2one(
        related="series_id.review_id",
        store=True,
        readonly=True,
    )
    source_document_id = fields.Many2one(
        related="series_id.source_document_id",
        store=True,
        readonly=True,
    )
    sequence = fields.Integer(default=10)
    material_code = fields.Char(string="Model Code", index=True)
    display_name = fields.Char(string="Display Name", required=True)
    page_range = fields.Char(string="Pages")
    confidence = fields.Float(string="Confidence")
    evidence = fields.Text(string="Evidence")
    main_field_hits = fields.Integer(string="Main Field Hits", default=0)
    param_total = fields.Integer(string="Parameter Count", default=0)
    reused_param_count = fields.Integer(string="Reused Existing", default=0)
    pending_param_count = fields.Integer(string="Pending Review", default=0)
    issue_count = fields.Integer(string="Issues", default=0)
    status = fields.Selection(
        [
            ("review_needed", "Review Needed"),
            ("auto_ready", "Auto Ready"),
        ],
        compute="_compute_status",
        store=True,
        string="Status",
    )

    @api.depends("confidence", "pending_param_count", "issue_count")
    def _compute_status(self):
        for model in self:
            model.status = (
                "auto_ready"
                if (model.confidence or 0.0) >= 0.85 and not model.pending_param_count and not model.issue_count
                else "review_needed"
            )


class DiecutCatalogSourceDocument(models.Model):
    _inherit = "diecut.catalog.source.document"

    handbook_review_id = fields.Many2one(
        "chatter.ai.handbook.review",
        string="Handbook Review",
        copy=False,
        readonly=True,
    )
    handbook_review_family_name = fields.Char(
        related="handbook_review_id.family_name",
        readonly=True,
        string="Handbook Family",
    )
    handbook_review_document_outline = fields.Text(
        related="handbook_review_id.document_outline",
        readonly=True,
        string="Handbook Outline",
    )
    handbook_review_summary = fields.Text(
        related="handbook_review_id.summary",
        readonly=True,
        string="Handbook Summary",
    )
    handbook_review_confidence = fields.Float(
        related="handbook_review_id.confidence",
        readonly=True,
        string="Handbook Confidence",
    )
    handbook_review_series_count = fields.Integer(
        related="handbook_review_id.series_count",
        readonly=True,
        string="Series Count",
    )
    handbook_review_model_count = fields.Integer(
        related="handbook_review_id.model_count",
        readonly=True,
        string="Model Count",
    )
    handbook_review_param_total = fields.Integer(
        related="handbook_review_id.param_total",
        readonly=True,
        string="Parameter Count",
    )
    handbook_review_reused_param_count = fields.Integer(
        related="handbook_review_id.reused_param_count",
        readonly=True,
        string="Reused Existing",
    )
    handbook_review_pending_param_count = fields.Integer(
        related="handbook_review_id.pending_param_count",
        readonly=True,
        string="Pending Review",
    )
    handbook_review_issue_count = fields.Integer(
        related="handbook_review_id.issue_count",
        readonly=True,
        string="Issues",
    )
    handbook_review_series_ids = fields.One2many(
        related="handbook_review_id.series_ids",
        readonly=True,
        string="Handbook Series Overview",
    )

    def action_identify_handbook_structure(self):
        run_model = self.env["chatter.ai.run"]
        for record in self:
            run_model.create_document_run(
                record,
                document_action="identify_handbook",
                prompt_text="识别手册结构，生成系列总览与型号明细。",
                requesting_user=self.env.user,
            )
        return True

    def action_open_handbook_review(self):
        self.ensure_one()
        if not self.handbook_review_id:
            raise UserError("当前记录还没有手册结构审阅结果。")
        return {
            "type": "ir.actions.act_url",
            "url": "#handbook-review",
            "target": "self",
        }

    def _refresh_handbook_review_from_current_draft(self, *, summary=False, confidence=False):
        for record in self:
            if not record.handbook_review_id:
                continue
            try:
                draft_payload = record._load_draft_payload() if record.draft_payload else {}
            except Exception:
                draft_payload = {}
            payload = {
                "family_name": record.handbook_review_id.family_name or False,
                "document_outline": summary
                or record.handbook_review_id.document_outline
                or record.result_message
                or False,
                "confidence": (
                    record.handbook_review_id.confidence
                    if confidence is False
                    else confidence
                )
                or 0.0,
                "draft_payload": draft_payload,
            }
            normalized = record._normalize_handbook_review_payload(payload)
            existing_review = record.handbook_review_id.sudo()
            existing_series_count = len(existing_review.series_ids)
            new_series_count = len(normalized.get("series_groups") or [])
            new_model_count = sum(
                len(group.get("models") or [])
                for group in (normalized.get("series_groups") or [])
                if isinstance(group, dict)
            )
            # Handbook reparse often produces a local correction delta such as
            # "merge/remove one family row" instead of a full rebuilt structure.
            # Do not let such sparse deltas wipe a previously richer overview.
            if existing_series_count > 1 and new_series_count <= 1 and new_model_count == 0:
                existing_review.write(
                    {
                        "document_outline": normalized.get("document_outline") or existing_review.document_outline or False,
                        "summary": normalized.get("document_outline") or existing_review.summary or False,
                        "confidence": normalized.get("confidence") or existing_review.confidence or 0.0,
                    }
                )
                continue
            record._upsert_handbook_review(normalized)

    def _handbook_review_family_name(self, payload):
        family_name = (payload.get("family_name") or "").strip()
        if family_name:
            return family_name
        brand = self._handbook_brand_name()
        title = (self.name or "").strip()
        if brand and title.lower().startswith(brand.lower()):
            remainder = title[len(brand):].strip(" -_")
            return remainder or title
        return title or brand or "Handbook"

    def _handbook_brand_name(self):
        brand = (self.brand_id.name or "").strip()
        if brand:
            return brand
        title = (self.name or "").strip()
        if title and len(title) <= 20:
            return title
        return ""

    def _handbook_series_long_name(self, family_name, series_display_name):
        brand = self._handbook_brand_name()
        display = self._normalize_series_display_name(series_display_name)
        family = (family_name or "").strip()
        if not display:
            return False
        vhb_children = {
            "4910系列",
            "4950系列",
            "5952系列",
            "5981系列",
            "GPH系列",
            "LSE系列",
            "RP系列",
        }
        if display in vhb_children:
            family = ("%s VHB 胶带" % brand).strip() if brand else "VHB 胶带"
        lowered = display.lower()
        if brand and lowered.startswith(brand.lower()):
            return display
        include_brand = bool(brand)
        if brand and family and family.lower().startswith(brand.lower()):
            include_brand = False
        parts = [part for part in ([brand] if include_brand else []) + [family, display] if part]
        return " ".join(parts).replace("  ", " ").strip()

    def _normalize_series_display_name(self, display_name):
        display = (display_name or "").strip()
        mapping = {
            "4910胶带系列": "4910系列",
            "4950胶带系列": "4950系列",
            "5952胶带系列": "5952系列",
            "5981胶带系列": "5981系列",
            "GPH胶带系列": "GPH系列",
            "LSE胶带系列": "LSE系列",
            "RP胶带系列": "RP系列",
        }
        return mapping.get(display, display)

    def _handbook_split_key_from_code(self, code):
        code = (code or "").strip().upper()
        if not code:
            return False
        if code.startswith("RP"):
            return "RP系列"
        if code.startswith("GPH-"):
            return "GPH系列"
        if code.startswith("LSE-"):
            return "LSE系列"
        if code.startswith("5981"):
            return "5981系列"
        if code.startswith("4910") or code == "4905":
            return "4910系列"
        if (
            code.startswith("495")
            or code.startswith("493")
            or code.startswith("492")
            or code.startswith("4914")
            or code.startswith("4941")
        ):
            return "4950系列"
        if code.startswith("59"):
            return "5952系列"
        return False

    def _handbook_group_hints(self, display_name):
        display_name = self._normalize_series_display_name(display_name)
        lowered = display_name.lower()
        return {
            "is_family": "家族" in display_name or "family" in lowered,
            "is_combined_children": "子系列" in display_name or "功能" in display_name or "各" in display_name,
        }

    def _handbook_family_context_for_group(self, family_name, group):
        display_name = (group.get("series_display_name") or "").strip()
        long_name = (group.get("series_long_name") or "").strip()
        source = long_name or display_name or (family_name or "")
        if "VHB" in source.upper():
            brand = (self.brand_id.name or "").strip()
            return ("%s VHB 胶带" % brand).strip() if brand else "VHB 胶带"
        return family_name

    def _handbook_expand_series_group(self, family_name, group):
        display_name = self._normalize_series_display_name(group.get("series_display_name"))
        models = [row for row in (group.get("models") or []) if isinstance(row, dict)]
        if not models:
            return [group]
        hints = self._handbook_group_hints(display_name)
        if not hints["is_combined_children"]:
            return [group]
        family_context = self._handbook_family_context_for_group(family_name, group)

        split_map = {}
        remainder = []
        for model_row in models:
            split_key = self._handbook_split_key_from_code(model_row.get("material_code"))
            if split_key:
                split_map.setdefault(split_key, []).append(model_row)
            else:
                remainder.append(model_row)
        if len(split_map) < 2 and not (len(split_map) == 1 and not remainder):
            return [group]

        expanded = []
        base_sequence = int(group.get("sequence") or 10)
        for offset, split_key in enumerate(sorted(split_map.keys()), start=0):
            expanded.append(
                {
                    **group,
                    "sequence": base_sequence + offset,
                    "series_display_name": split_key,
                    "series_long_name": self._handbook_series_long_name(family_context, split_key),
                    "models": split_map[split_key],
                    "confidence": max(float(group.get("confidence") or 0.0), 0.90),
                    "evidence": ((group.get("evidence") or "") + "\n按型号前缀拆分为子系列。").strip(),
                }
            )
        if remainder:
            expanded.append(
                {
                    **group,
                    "sequence": base_sequence + len(expanded),
                    "series_display_name": display_name,
                    "series_long_name": self._handbook_series_long_name(family_name, display_name),
                    "models": remainder,
                    "confidence": min(float(group.get("confidence") or 0.0), 0.75),
                    "evidence": ((group.get("evidence") or "") + "\n剩余型号暂未能自动归入具体子系列。").strip(),
                }
            )
        return expanded

    def _handbook_model_metrics_from_payload(self, draft_payload, code):
        payload = draft_payload if isinstance(draft_payload, dict) else {}
        params_by_key = {
            (row.get("param_key") or "").strip().lower(): row
            for row in payload.get("params") or []
            if isinstance(row, dict) and row.get("param_key")
        }
        spec_rows = []
        for row in payload.get("spec_values") or []:
            if not isinstance(row, dict):
                continue
            item_code = (row.get("item_code") or row.get("code") or "").strip()
            if not code or item_code == code:
                spec_rows.append(row)
        unique_keys = {(row.get("param_key") or "").strip().lower() for row in spec_rows if row.get("param_key")}
        reused = 0
        pending = 0
        main_hits = 0
        for param_key in unique_keys:
            param_row = params_by_key.get(param_key) or {}
            if param_row.get("is_main_field"):
                main_hits += 1
            if param_row.get("candidate_new"):
                pending += 1
            else:
                reused += 1
        return {
            "param_total": len(spec_rows),
            "reused_param_count": reused,
            "pending_param_count": pending,
            "main_field_hits": main_hits,
            "issue_count": pending,
        }

    def _fallback_handbook_review_payload(self, payload):
        self.ensure_one()
        draft_payload = payload.get("draft_payload")
        if not isinstance(draft_payload, dict) and self.draft_payload:
            try:
                draft_payload = self._load_draft_payload()
            except Exception:
                draft_payload = {}
        draft_payload = draft_payload if isinstance(draft_payload, dict) else {}
        family_name = self._handbook_review_family_name(payload)
        series_rows = [row for row in (draft_payload.get("series") or []) if isinstance(row, dict)]
        item_rows = [row for row in (draft_payload.get("items") or []) if isinstance(row, dict)]
        if not series_rows and item_rows:
            series_rows = [{"name": family_name}]
        groups = []
        for index, series_row in enumerate(series_rows, start=1):
            display_name = series_row.get("series_name") or series_row.get("name") or family_name
            models = []
            for item_index, item_row in enumerate(item_rows, start=1):
                item_series = (item_row.get("series_name") or display_name or "").strip()
                if item_series and display_name and item_series != display_name:
                    continue
                code = (item_row.get("code") or "").strip()
                metrics = self._handbook_model_metrics_from_payload(draft_payload, code)
                models.append(
                    {
                        "sequence": item_index,
                        "material_code": code or False,
                        "display_name": item_row.get("name") or code or display_name,
                        "page_range": item_row.get("source_ref") or series_row.get("source_ref") or False,
                        "confidence": float(item_row.get("confidence") or 0.72),
                        "evidence": item_row.get("source_excerpt") or False,
                        **metrics,
                    }
                )
            groups.append(
                {
                    "sequence": index,
                    "series_display_name": display_name,
                    "series_long_name": self._handbook_series_long_name(family_name, display_name),
                    "page_range": series_row.get("source_ref") or False,
                    "series_description": series_row.get("product_description") or series_row.get("description") or False,
                    "series_features": series_row.get("product_features") or series_row.get("features") or False,
                    "series_applications": series_row.get("main_applications") or series_row.get("applications") or False,
                    "confidence": float(series_row.get("confidence") or 0.65),
                    "evidence": series_row.get("source_excerpt") or False,
                    "models": models,
                }
            )
        return {
            "family_name": family_name,
            "document_outline": payload.get("document_outline") or payload.get("summary") or self.result_message or False,
            "confidence": float(payload.get("confidence") or 0.6),
            "series_groups": groups,
        }

    def _normalize_handbook_review_payload(self, payload):
        self.ensure_one()
        review_payload = payload.get("handbook_review") if isinstance(payload.get("handbook_review"), dict) else payload
        if not isinstance(review_payload, dict):
            review_payload = {}
        if not review_payload.get("series_groups"):
            review_payload = self._fallback_handbook_review_payload(payload)

        family_name = self._handbook_review_family_name(review_payload)
        normalized_groups = []
        for index, group in enumerate(review_payload.get("series_groups") or [], start=1):
            if not isinstance(group, dict):
                continue
            display_name = self._normalize_series_display_name(
                group.get("series_display_name")
                or group.get("series_name")
                or group.get("name")
                or False
            )
            if not display_name:
                continue
            models = []
            for model_index, candidate in enumerate(group.get("models") or group.get("model_candidates") or [], start=1):
                if not isinstance(candidate, dict):
                    continue
                code = (candidate.get("material_code") or candidate.get("code") or "").strip()
                metrics = self._handbook_model_metrics_from_payload(candidate.get("draft_payload") or {}, code)
                metrics.update(
                    {
                        "sequence": candidate.get("sequence") or model_index,
                        "material_code": code or False,
                        "display_name": candidate.get("name") or candidate.get("display_name") or code or display_name,
                        "page_range": candidate.get("page_range") or candidate.get("pages_summary") or False,
                        "confidence": float(candidate.get("confidence") or 0.0),
                        "evidence": candidate.get("evidence") or candidate.get("summary") or False,
                    }
                )
                metrics["param_total"] = candidate.get("param_total", metrics["param_total"])
                metrics["reused_param_count"] = candidate.get("reused_param_count", metrics["reused_param_count"])
                metrics["pending_param_count"] = candidate.get("pending_param_count", metrics["pending_param_count"])
                metrics["issue_count"] = candidate.get("issue_count", metrics["issue_count"])
                metrics["main_field_hits"] = candidate.get("main_field_hits", metrics["main_field_hits"])
                models.append(metrics)
            normalized_groups.append(
                {
                    "sequence": group.get("sequence") or index,
                    "series_display_name": display_name,
                    "series_long_name": self._handbook_series_long_name(family_name, display_name),
                    "page_range": group.get("page_range") or group.get("pages_summary") or False,
                    "series_description": group.get("series_description") or group.get("description") or False,
                    "series_features": group.get("series_features") or group.get("features") or False,
                    "series_applications": group.get("series_applications") or group.get("applications") or False,
                    "confidence": float(group.get("confidence") or 0.0),
                    "evidence": group.get("evidence") or False,
                    "models": models,
                }
            )

        expanded_groups = []
        for group in normalized_groups:
            expanded_groups.extend(self._handbook_expand_series_group(family_name, group))

        merged_groups = []
        merged_index = {}
        for group in expanded_groups:
            key = (
                group.get("series_display_name") or "",
                group.get("series_long_name") or "",
            )
            existing = merged_index.get(key)
            if not existing:
                copied = dict(group)
                copied["models"] = list(group.get("models") or [])
                merged_groups.append(copied)
                merged_index[key] = copied
                continue
            existing["models"].extend(group.get("models") or [])
            existing["confidence"] = max(float(existing.get("confidence") or 0.0), float(group.get("confidence") or 0.0))
            if not existing.get("page_range") and group.get("page_range"):
                existing["page_range"] = group.get("page_range")
            if group.get("series_description") and not existing.get("series_description"):
                existing["series_description"] = group.get("series_description")
            if group.get("series_features") and not existing.get("series_features"):
                existing["series_features"] = group.get("series_features")
            if group.get("series_applications") and not existing.get("series_applications"):
                existing["series_applications"] = group.get("series_applications")
            if group.get("evidence"):
                existing["evidence"] = "\n".join(
                    part for part in [existing.get("evidence"), group.get("evidence")] if part
                )

        for index, group in enumerate(merged_groups, start=1):
            group["sequence"] = index

        return {
            "family_name": family_name,
            "document_outline": review_payload.get("document_outline") or payload.get("summary") or False,
            "confidence": float(review_payload.get("confidence") or payload.get("confidence") or 0.0),
            "series_groups": merged_groups,
        }

    def _upsert_handbook_review(self, payload):
        self.ensure_one()
        review_model = self.env["chatter.ai.handbook.review"].sudo()
        series_model = self.env["chatter.ai.handbook.review.series"].sudo()
        model_model = self.env["chatter.ai.handbook.review.model"].sudo()
        review = self.handbook_review_id.sudo() if self.handbook_review_id else review_model
        vals = {
            "name": "%s Handbook Review" % (self.display_name or self.name),
            "source_document_id": self.id,
            "state": "identified",
            "family_name": payload.get("family_name") or False,
            "document_outline": payload.get("document_outline") or False,
            "summary": payload.get("document_outline") or False,
            "trace_id": self.chatter_ai_trace_id or False,
            "confidence": payload.get("confidence") or 0.0,
        }
        if review and review.id:
            review.write(vals)
            review.series_ids.unlink()
        else:
            review = review_model.create(vals)

        for group in payload.get("series_groups") or []:
            series = series_model.create(
                {
                    "review_id": review.id,
                    "sequence": group.get("sequence") or 10,
                    "series_display_name": group.get("series_display_name") or False,
                    "series_long_name": group.get("series_long_name"),
                    "page_range": group.get("page_range") or False,
                    "series_description": group.get("series_description") or False,
                    "series_features": group.get("series_features") or False,
                    "series_applications": group.get("series_applications") or False,
                    "confidence": group.get("confidence") or 0.0,
                    "evidence": group.get("evidence") or False,
                }
            )
            for model_row in group.get("models") or []:
                model_model.create(
                    {
                        "series_id": series.id,
                        "sequence": model_row.get("sequence") or 10,
                        "material_code": model_row.get("material_code") or False,
                        "display_name": model_row.get("display_name") or model_row.get("material_code") or "Model",
                        "page_range": model_row.get("page_range") or False,
                        "confidence": model_row.get("confidence") or 0.0,
                        "evidence": model_row.get("evidence") or False,
                        "main_field_hits": int(model_row.get("main_field_hits") or 0),
                        "param_total": int(model_row.get("param_total") or 0),
                        "reused_param_count": int(model_row.get("reused_param_count") or 0),
                        "pending_param_count": int(model_row.get("pending_param_count") or 0),
                        "issue_count": int(model_row.get("issue_count") or 0),
                    }
                )
        self.write({"handbook_review_id": review.id})
        return review
