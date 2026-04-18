# -*- coding: utf-8 -*-

import re

from odoo import Command, api, models
from odoo.exceptions import UserError, ValidationError


class DiecutCatalogMergeMixin(models.AbstractModel):
    _name = "diecut.catalog.merge.mixin"
    _description = "Catalog Merge Mixin"

    @api.model
    def _check_merge_access(self):
        if not self.env.user.has_group("base.group_system"):
            raise UserError("只有系统管理员可以执行字典或参数合并。")

    def action_open_merge_wizard(self):
        self._check_merge_access()
        active_ids = self.env.context.get("active_ids") or self.ids
        return (
            self.env["diecut.catalog.merge.wizard"]
            .with_context(active_model=self._name, active_ids=active_ids)
            .action_open_from_context()
        )

    @api.model
    def _merge_alias_field_name(self):
        if "alias_text" in self._fields:
            return "alias_text"
        if "aliases_text" in self._fields:
            return "aliases_text"
        return False

    @api.model
    def _split_merge_alias_tokens(self, value):
        if not value:
            return []
        tokens = []
        for part in re.split(r"[\n,;，；]+", str(value)):
            token = re.sub(r"\s+", " ", part or "").strip()
            if token:
                tokens.append(token)
        return tokens

    def _merge_extra_alias_candidates(self):
        self.ensure_one()
        return []

    def _collect_merge_alias_tokens(self, master, sources):
        alias_field = self._merge_alias_field_name()
        master_name = (getattr(master, "name", False) or master.display_name or "").strip()
        seen = {master_name.casefold()} if master_name else set()
        tokens = []

        def _append(raw_value):
            for token in self._split_merge_alias_tokens(raw_value):
                lowered = token.casefold()
                if lowered in seen:
                    continue
                seen.add(lowered)
                tokens.append(token)

        if alias_field:
            _append(master[alias_field])
        for record in sources:
            _append(getattr(record, "name", False) or record.display_name)
            if alias_field:
                _append(record[alias_field])
            for candidate in record._merge_extra_alias_candidates():
                _append(candidate)
        return tokens

    def _prepare_merge_master_vals(self, master, sources):
        master.ensure_one()
        alias_field = self._merge_alias_field_name()
        if not alias_field:
            return {}
        aliases = self._collect_merge_alias_tokens(master, sources)
        return {alias_field: "\n".join(aliases) if aliases else False}

    @api.model
    def _merge_relation_field_blacklist(self):
        return set()

    @api.model
    def _merge_relation_specs(self):
        blacklist = self._merge_relation_field_blacklist()
        field_model = self.env["ir.model.fields"].sudo()
        specs = []
        for field in field_model.search(
            [("relation", "=", self._name), ("ttype", "in", ("many2one", "many2many"))]
        ):
            if (field.model, field.name) in blacklist:
                continue
            if field.model not in self.env:
                continue
            model = self.env[field.model]
            if getattr(model, "_transient", False):
                continue
            field_obj = model._fields.get(field.name)
            if not field_obj:
                continue
            # Non-stored relational aliases cannot be searched with SQL domains.
            if not getattr(field_obj, "store", False):
                continue
            if field_obj.compute and not field_obj.inverse:
                continue
            specs.append((field.model, field.name, field.ttype))
        return specs

    @api.model
    def _rewrite_many2one_references(self, model_name, field_name, master_id, source_ids):
        records = self.env[model_name].sudo().with_context(active_test=False).search([(field_name, "in", list(source_ids))])
        count = len(records)
        if records:
            records.write({field_name: master_id})
        return count

    @api.model
    def _rewrite_many2many_references(self, model_name, field_name, master_id, source_ids):
        records = self.env[model_name].sudo().with_context(active_test=False).search([(field_name, "in", list(source_ids))])
        changed_links = 0
        source_set = set(source_ids)
        for record in records:
            current_ids = set(record[field_name].ids)
            overlap = current_ids & source_set
            if not overlap:
                continue
            new_ids = sorted((current_ids - source_set) | {master_id})
            record.write({field_name: [Command.set(new_ids)]})
            changed_links += len(overlap)
        return changed_links

    @api.model
    def _rewrite_relational_references(self, master, sources):
        moved_refs = 0
        source_ids = tuple(sources.ids)
        for model_name, field_name, field_type in self._merge_relation_specs():
            if field_type == "many2one":
                moved_refs += self._rewrite_many2one_references(model_name, field_name, master.id, source_ids)
            elif field_type == "many2many":
                moved_refs += self._rewrite_many2many_references(model_name, field_name, master.id, source_ids)
        return moved_refs

    @api.model
    def _count_remaining_references(self, source_ids):
        remaining = 0
        for model_name, field_name, _field_type in self._merge_relation_specs():
            remaining += self.env[model_name].sudo().with_context(active_test=False).search_count(
                [(field_name, "in", list(source_ids))]
            )
        return remaining

    def _validate_merge_records(self, master, sources):
        master.ensure_one()
        if not sources:
            raise ValidationError("请选择至少一条源记录。")
        if master in sources:
            raise ValidationError("主记录不能同时作为源记录。")

    def _merge_related_records(self, master, sources):
        return {}

    @api.model
    def merge_records(self, master_id, source_ids):
        self._check_merge_access()
        master = self.with_context(active_test=False).browse(master_id).exists()
        sources = self.with_context(active_test=False).browse(source_ids).exists()
        if not master:
            raise UserError("主记录不存在，无法继续合并。")
        if len(sources) != len(set(source_ids or [])):
            raise UserError("源记录存在无效项，请刷新后重试。")
        if master.id in sources.ids:
            sources = sources - master
        if not sources:
            raise UserError("请至少保留一条源记录用于合并。")

        self._validate_merge_records(master, sources)
        master_vals = master._prepare_merge_master_vals(master, sources)
        if master_vals:
            master.write(master_vals)

        summary = dict(master._merge_related_records(master, sources) or {})
        summary["moved_refs"] = master._rewrite_relational_references(master, sources)

        refresher = getattr((master | sources), "_refresh_usage_counts", None)
        if callable(refresher):
            (master | sources)._refresh_usage_counts()

        remaining = master._count_remaining_references(sources.ids)
        if remaining:
            raise UserError(f"仍有 {remaining} 条引用未迁移完成，已终止本次合并。")

        sources.with_context(skip_merge_unlink_guard=True).unlink()

        refresher_all = getattr(master, "_refresh_all_usage_counts", None)
        if callable(refresher_all):
            master._refresh_all_usage_counts()
        else:
            refresher = getattr(master, "_refresh_usage_counts", None)
            if callable(refresher):
                master._refresh_usage_counts()

        summary["deleted_sources"] = len(sources)
        summary["master_name"] = master.display_name
        return summary
