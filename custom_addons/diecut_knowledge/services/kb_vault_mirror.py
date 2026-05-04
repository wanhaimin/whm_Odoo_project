# -*- coding: utf-8 -*-

import base64
import hashlib
import mimetypes
import os
import re
import shutil
from datetime import datetime
from pathlib import Path

from odoo import fields
from odoo.exceptions import UserError

from .prompt_loader import load_schema


SUPPORTED_RAW_EXTENSIONS = {".pdf", ".txt", ".md", ".markdown"}
RAW_SCAN_EXCLUDED_DIRS = {"failed", ".obsidian", "__pycache__"}
RAW_SCAN_EXCLUDED_FILES = {"AGENTS.md", "index.md", "log.md"}


class KbVaultMirror:
    """Synchronize a local Karpathy-style raw/wiki vault with Odoo records."""

    def __init__(self, env):
        self.env = env
        self.config = env["ir.config_parameter"].sudo()

    def vault_root(self):
        raw_root = self.config.get_param("diecut_knowledge.vault_root_path") or ""
        root = self._normalize_vault_root(raw_root)
        if not root:
            raise UserError("请先在知识库设置中配置 Vault 根目录。")
        normalized_for_storage = root
        current_for_storage = self._strip_user_path(raw_root)
        if normalized_for_storage != current_for_storage:
            self.config.set_param("diecut_knowledge.vault_root_path", normalized_for_storage)
        return Path(root).expanduser()

    def _strip_user_path(self, value):
        root = (value or "").strip()
        if len(root) >= 2 and root[0] == root[-1] and root[0] in {"'", '"'}:
            root = root[1:-1].strip()
        return root

    def _normalize_vault_root(self, value):
        root = self._strip_user_path(value)
        if not root:
            return ""
        normalized = root.replace("\\", "/")
        if re.match(r"^[A-Za-z]:/", normalized):
            if os.name == "nt":
                return root
            lowered = normalized.lower()
            project_custom_addons = "e:/workspace/my_odoo_project/custom_addons"
            if lowered == project_custom_addons:
                return "/mnt/extra-addons"
            if lowered.startswith(project_custom_addons + "/"):
                return "/mnt/extra-addons" + normalized[len(project_custom_addons):]
            raise UserError(
                "当前 Odoo 在 Docker 容器中运行，不能直接使用 Windows 路径：%s。"
                "请改用容器路径，例如 /mnt/extra-addons/.diecut_knowledge_vault；"
                "如果要放在模块目录内，可使用 /mnt/extra-addons/diecut_knowledge/knowledge_vault。"
                % root
            )
        return root

    def ensure_structure(self):
        root = self.vault_root()
        for rel in (
            "raw/inbox",
            "raw/processed",
            "raw/failed",
            "wiki/brands",
            "wiki/materials",
            "wiki/applications",
            "wiki/processes",
            "wiki/faq",
            "wiki/sources",
            "wiki/concepts",
            "wiki/comparisons",
            "wiki/query-answers",
            "assets",
        ):
            (root / rel).mkdir(parents=True, exist_ok=True)
        self._write_agents_file(root)
        return root

    def scan_raw_inbox(self, limit=None, generate_plan=True, enqueue_compile=False):
        """Compatibility entrypoint; now syncs the full raw source registry."""
        return self.sync_raw_sources(
            limit=limit,
            generate_plan=generate_plan,
            enqueue_compile=enqueue_compile,
        )

    def sync_raw_sources(self, limit=None, generate_plan=True, enqueue_compile=False):
        root = self.ensure_structure()
        raw_root = root / "raw"
        files = self._discover_raw_source_files(raw_root)
        if limit:
            files = files[: int(limit)]

        created = self.env["diecut.catalog.source.document"].sudo().browse()
        updated = self.env["diecut.catalog.source.document"].sudo().browse()
        unchanged = self.env["diecut.catalog.source.document"].sudo().browse()
        missing = self._mark_missing_raw_sources(root, files)
        errors = []
        for path in files:
            try:
                source, action = self._sync_raw_file(path, generate_plan=generate_plan)
                if action == "created":
                    created |= source
                elif action == "updated":
                    updated |= source
                elif source:
                    unchanged |= source
            except Exception as exc:
                errors.append("%s: %s" % (path.name, exc))
                self._mark_failed_raw_file(path, exc)
        queued = 0
        if enqueue_compile:
            queued = self._enqueue_incremental_compile_jobs(created | updated | unchanged, force_sources=created | updated)
        return {
            "created": len(created),
            "created_ids": created.ids,
            "updated": len(updated),
            "updated_ids": updated.ids,
            "unchanged": len(unchanged),
            "unchanged_ids": unchanged.ids,
            "missing": len(missing),
            "missing_ids": missing.ids,
            "queued": queued,
            "errors": errors,
            "inbox_path": str(raw_root / "inbox"),
            "raw_path": str(raw_root),
        }

    def export_wiki(self, domain=None, limit=None):
        root = self.ensure_structure()
        Article = self.env["diecut.kb.article"].sudo()
        search_domain = domain or [("active", "=", True), ("state", "in", ["review", "published"])]
        articles = Article.search(search_domain, order="category_id, name, id", limit=limit)
        exported = 0
        for article in articles:
            if not article.content_md and not article.content_html:
                continue
            path = self._article_path(root, article)
            path.parent.mkdir(parents=True, exist_ok=True)
            markdown = self._render_article_markdown(article)
            old_hash = article.vault_wiki_hash or ""
            new_hash = self._hash_text(markdown)
            if path.exists() and old_hash and self._hash_file(path) != old_hash:
                article.write({
                    "vault_sync_state": "conflict",
                    "vault_error": "Wiki 文件已有外部修改，导出已跳过，请先导入或人工处理。",
                })
                continue
            path.write_text(markdown, encoding="utf-8", newline="\n")
            article.write({
                "vault_wiki_path": str(path),
                "vault_wiki_hash": new_hash,
                "vault_last_exported_at": fields.Datetime.now(),
                "vault_sync_state": "exported",
                "vault_error": False,
            })
            exported += 1
        self._refresh_wiki_index_files(root)
        return {"exported": exported}

    def import_wiki_changes(self, limit=None):
        root = self.ensure_structure()
        wiki_root = root / "wiki"
        files = [
            item
            for item in sorted(wiki_root.rglob("*.md"), key=lambda p: str(p).lower())
            if item.name not in {"index.md", "log.md"}
        ]
        if limit:
            files = files[: int(limit)]

        Article = self.env["diecut.kb.article"].sudo()
        imported = 0
        skipped = 0
        errors = []
        for path in files:
            try:
                text = path.read_text(encoding="utf-8")
                frontmatter, body = self._split_frontmatter(text)
                article = Article.browse(int(frontmatter.get("odoo_article_id") or 0)).exists()
                if not article:
                    slug = frontmatter.get("wiki_slug") or path.stem
                    article = Article.search([("wiki_slug", "=", slug)], limit=1)
                if not article:
                    skipped += 1
                    continue
                current_hash = self._hash_text(text)
                if article.vault_wiki_hash == current_hash:
                    skipped += 1
                    continue
                values = {
                    "content_md": body.strip(),
                    "vault_wiki_path": str(path),
                    "vault_wiki_hash": current_hash,
                    "vault_last_imported_at": fields.Datetime.now(),
                    "vault_sync_state": "imported",
                    "vault_error": False,
                    "sync_status": "pending",
                }
                if article.state == "published":
                    values["state"] = "review"
                article.with_context(skip_auto_enrich=True).write(values)
                self._sync_links_from_markdown(article, body)
                self._log("query", "Wiki 文件导入：%s" % article.name, article=article, summary=str(path))
                imported += 1
            except Exception as exc:
                errors.append("%s: %s" % (path.name, exc))
        return {"imported": imported, "skipped": skipped, "errors": errors}

    def _discover_raw_source_files(self, raw_root):
        scope = (self.config.get_param("diecut_knowledge.vault_scan_scope") or "all_raw").strip()
        roots = [raw_root / "inbox"] if scope == "inbox" else [raw_root]
        files = []
        seen = set()
        for scan_root in roots:
            if not scan_root.exists():
                continue
            for item in sorted(scan_root.rglob("*"), key=lambda p: str(p).lower()):
                if not item.is_file():
                    continue
                try:
                    rel_parts = item.relative_to(raw_root).parts
                except ValueError:
                    rel_parts = item.parts
                if any(part in RAW_SCAN_EXCLUDED_DIRS or part.startswith(".") for part in rel_parts[:-1]):
                    continue
                if item.name in RAW_SCAN_EXCLUDED_FILES:
                    continue
                if item.suffix.lower() not in SUPPORTED_RAW_EXTENSIONS:
                    continue
                key = str(item.resolve())
                if key not in seen:
                    seen.add(key)
                    files.append(item)
        return files

    def _mark_missing_raw_sources(self, root, current_files):
        Source = self.env["diecut.catalog.source.document"].sudo()
        known_paths = {str(path) for path in current_files}
        raw_root = str(root / "raw")
        candidates = Source.search([
            ("vault_file_hash", "!=", False),
            ("vault_raw_path", "!=", False),
            ("vault_raw_path", "like", raw_root),
            ("vault_sync_state", "!=", "missing"),
        ])
        missing = Source.browse()
        for source in candidates:
            if source.vault_raw_path not in known_paths and not Path(source.vault_raw_path).exists():
                source.write({
                    "vault_sync_state": "missing",
                    "vault_last_synced_at": fields.Datetime.now(),
                    "vault_error": "Vault raw file was not found during source registry sync.",
                })
                missing |= source
        return missing

    def _sync_raw_file(self, path, generate_plan=True):
        file_hash = self._hash_file(path)
        Source = self.env["diecut.catalog.source.document"].sudo()
        path_string = str(path)
        source = Source.search([("vault_file_hash", "=", file_hash)], limit=1)
        path_source = Source.search([("vault_raw_path", "=", path_string)], limit=1)
        source = source or path_source

        data = path.read_bytes()
        mimetype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        source_type = "pdf" if path.suffix.lower() == ".pdf" else "manual"
        raw_text = self._read_text_file(path) if path.suffix.lower() in {".txt", ".md", ".markdown"} else False
        vault_state = self._raw_state_for_path(path)

        if source:
            changed = (
                source.vault_file_hash != file_hash
                or source.vault_raw_path != path_string
                or source.source_filename != path.name
            )
            vals = {
                "vault_raw_path": path_string,
                "vault_file_hash": file_hash,
                "vault_sync_state": vault_state,
                "vault_last_synced_at": fields.Datetime.now(),
                "vault_error": False,
            }
            if changed:
                vals.update({
                    "source_type": source_type,
                    "source_file": base64.b64encode(data),
                    "source_filename": path.name,
                    "raw_text": raw_text,
                    "knowledge_parse_state": "pending",
                    "knowledge_parsed_text": False,
                    "knowledge_parsed_markdown": False,
                    "knowledge_parse_error": False,
                    "knowledge_parsed_at": False,
                    "route_plan_state": "draft",
                    "route_plan_error": False,
                    "result_message": "Vault raw source changed; waiting for incremental ingest planning.",
                })
            source.write(vals)
            self._sync_attachment_mimetype(source, mimetype)
            if changed:
                self._log("ingest", "Vault raw source updated: %s" % source.name, source=source, summary=path_string)
                if generate_plan:
                    self._generate_route_plan_safely(source)
                return source, "updated"
            return source, "unchanged"

        source = Source.create({
            "name": path.stem,
            "source_type": source_type,
            "source_file": base64.b64encode(data),
            "source_filename": path.name,
            "raw_text": raw_text,
            "import_status": "draft",
            "result_message": "Imported from Vault raw source registry; waiting for Ingest Plan.",
            "vault_raw_path": path_string,
            "vault_file_hash": file_hash,
            "vault_sync_state": vault_state,
            "vault_last_synced_at": fields.Datetime.now(),
            "vault_error": False,
        })
        self._sync_attachment_mimetype(source, mimetype)
        if generate_plan:
            self._generate_route_plan_safely(source)
        self._log("ingest", "Vault raw source registered: %s" % source.name, source=source, summary=path_string)
        return source, "created"

    def _raw_state_for_path(self, path):
        parts = set(path.parts)
        if "processed" in parts:
            return "processed"
        if "failed" in parts:
            return "failed"
        return "discovered"

    def _sync_attachment_mimetype(self, source, mimetype):
        if source.primary_attachment_id:
            source.primary_attachment_id.write({"mimetype": mimetype})

    def _generate_route_plan_safely(self, source):
        if source.route_plan_state not in ("draft", "failed"):
            return
        try:
            source.action_generate_route_plan()
        except Exception as exc:
            source.write({
                "route_plan_state": "failed",
                "route_plan_error": "Vault raw source synced, but Ingest Plan generation failed: %s" % exc,
            })

    def _enqueue_incremental_compile_jobs(self, sources, force_sources=False):
        result = self.env["diecut.catalog.source.document"]._enqueue_incremental_wiki_compile(sources=sources)
        return result.get("created", 0)

    def _mark_failed_raw_file(self, path, exc):
        Source = self.env["diecut.catalog.source.document"].sudo()
        source = Source.search([("vault_raw_path", "=", str(path))], limit=1)
        if source:
            source.write({
                "vault_sync_state": "failed",
                "vault_last_synced_at": fields.Datetime.now(),
                "vault_error": str(exc),
            })

    def _ingest_raw_file(self, path, processed_dir, generate_plan=True):
        source, action = self._sync_raw_file(path, generate_plan=generate_plan)
        return source, action != "created"
        file_hash = self._hash_file(path)
        Source = self.env["diecut.catalog.source.document"].sudo()
        existing = Source.search([("vault_file_hash", "=", file_hash)], limit=1)
        if existing:
            self._move_file_safely(path, processed_dir / path.name)
            return existing, True

        data = path.read_bytes()
        mimetype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        source_type = "pdf" if path.suffix.lower() == ".pdf" else "manual"
        raw_text = self._read_text_file(path) if path.suffix.lower() in {".txt", ".md", ".markdown"} else False
        source = Source.create({
            "name": path.stem,
            "source_type": source_type,
            "source_file": base64.b64encode(data),
            "source_filename": path.name,
            "raw_text": raw_text,
            "import_status": "draft",
            "result_message": "由 raw/inbox 文件夹镜像导入，等待生成 Ingest Plan。",
            "vault_raw_path": str(path),
            "vault_file_hash": file_hash,
            "vault_sync_state": "imported",
            "vault_last_synced_at": fields.Datetime.now(),
        })
        if source.primary_attachment_id:
            source.primary_attachment_id.write({"mimetype": mimetype})
        if generate_plan:
            try:
                source.action_generate_route_plan()
            except Exception as exc:
                source.write({
                    "route_plan_state": "failed",
                    "route_plan_error": "raw/inbox 导入成功，但生成 Ingest Plan 失败：%s" % exc,
                })
        moved_path = self._move_file_safely(path, processed_dir / path.name)
        source.write({"vault_raw_path": str(moved_path), "vault_sync_state": "processed"})
        self._log("ingest", "Raw 文件入库：%s" % source.name, source=source, summary=str(moved_path))
        return source, False

    def _render_article_markdown(self, article):
        frontmatter = {
            "odoo_article_id": article.id,
            "title": article.name or "",
            "state": article.state or "",
            "compile_source": article.compile_source or "",
            "wiki_page_type": article.wiki_page_type or "",
            "wiki_slug": article.wiki_slug or article._make_wiki_slug(article.name),
            "compiled_at": article.compiled_at.isoformat() if article.compiled_at else "",
            "source_document_id": article.compile_source_document_id.id if article.compile_source_document_id else "",
            "source_item_id": article.compile_source_item_id.id if article.compile_source_item_id else "",
        }
        body = article.content_md or article.content_text or ""
        related = self._related_links_markdown(article)
        return "---\n%s---\n\n%s%s" % (
            "".join("%s: %s\n" % (key, value) for key, value in frontmatter.items()),
            body.strip(),
            related,
        )

    def _related_links_markdown(self, article):
        links = article.outbound_link_ids.filtered(lambda link: link.active and link.target_article_id)
        if not links:
            return "\n"
        lines = ["", "## Related pages"]
        for link in links:
            target = link.target_article_id
            slug = target.wiki_slug or target._make_wiki_slug(target.name)
            lines.append("- [[%s|%s]]" % (slug, target.name))
        return "\n" + "\n".join(lines) + "\n"

    def _sync_links_from_markdown(self, article, markdown):
        slugs = re.findall(r"\[\[([^\]|#]+)(?:\|[^\]]+)?\]\]", markdown or "")
        if not slugs:
            return
        Article = self.env["diecut.kb.article"].sudo()
        Link = self.env["diecut.kb.wiki.link"].sudo()
        for slug in sorted(set(s.strip() for s in slugs if s.strip())):
            target = Article.search([("wiki_slug", "=", slug), ("id", "!=", article.id)], limit=1)
            if not target:
                continue
            existing = Link.search([
                ("source_article_id", "=", article.id),
                ("target_article_id", "=", target.id),
                ("link_type", "=", "mentions"),
            ], limit=1)
            vals = {
                "source_article_id": article.id,
                "target_article_id": target.id,
                "link_type": "mentions",
                "anchor_text": target.name,
                "reason": "从 Wiki Markdown 双链导入。",
                "confidence": 0.7,
                "active": True,
            }
            if existing:
                existing.write(vals)
            else:
                Link.create(vals)

    def _article_path(self, root, article):
        folder = {
            "brand": "brands",
            "material": "materials",
            "material_category": "materials",
            "application": "applications",
            "process": "processes",
            "faq": "faq",
            "comparison": "comparisons",
            "concept": "concepts",
            "query_answer": "query-answers",
            "source_summary": "sources",
        }.get(article.wiki_page_type or "", "sources")
        slug = article.wiki_slug or article._make_wiki_slug(article.name)
        return root / "wiki" / folder / ("%s.md" % self._safe_filename(slug))

    def _refresh_wiki_index_files(self, root):
        Article = self.env["diecut.kb.article"].sudo()
        articles = Article.search([("active", "=", True), ("state", "in", ["review", "published"])], order="name")
        index_lines = ["# Wiki Index", ""]
        for article in articles:
            slug = article.wiki_slug or article._make_wiki_slug(article.name)
            index_lines.append("- [[%s|%s]] - %s" % (slug, article.name, (article.summary or "")[:120]))
        (root / "wiki" / "index.md").write_text("\n".join(index_lines) + "\n", encoding="utf-8", newline="\n")
        self._export_log_file(root)

    def _write_agents_file(self, root):
        path = root / "AGENTS.md"
        if path.exists():
            return
        schema = load_schema(default="")
        text = "# LLM Wiki Vault Rules\n\nThis vault mirrors Odoo diecut_knowledge.\n\n%s\n" % schema
        path.write_text(text, encoding="utf-8", newline="\n")

    def _split_frontmatter(self, text):
        if not text.startswith("---\n"):
            return {}, text
        end = text.find("\n---", 4)
        if end < 0:
            return {}, text
        raw = text[4:end].strip()
        body = text[end + 4 :].lstrip("\r\n")
        data = {}
        for line in raw.splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            data[key.strip()] = value.strip()
        return data, body

    def _read_text_file(self, path):
        data = path.read_bytes()
        for encoding in ("utf-8-sig", "utf-8", "gb18030"):
            try:
                return data.decode(encoding)
            except UnicodeDecodeError:
                continue
        return data.decode("utf-8", errors="replace")

    def _hash_file(self, path):
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _hash_text(self, text):
        return hashlib.sha256((text or "").encode("utf-8")).hexdigest()

    def _move_file_safely(self, source, target):
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            stem = target.stem
            suffix = target.suffix
            stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
            target = target.with_name("%s-%s%s" % (stem, stamp, suffix))
        shutil.move(str(source), str(target))
        return target

    def _export_log_file(self, root):
        log_path = root / "wiki" / "log.md"
        Log = self.env["diecut.kb.wiki.log"].sudo()
        entries = Log.search([], limit=200, order="create_date desc, id desc")
        if not entries:
            log_path.write_text("# Wiki Log\n\n", encoding="utf-8", newline="\n")
            return
        lines = ["# Wiki Log", ""]
        for entry in reversed(list(entries)):
            date_str = (entry.create_date or fields.Datetime.now()).strftime("%Y-%m-%d")
            event_label = dict(entry._fields["event_type"].selection).get(entry.event_type, entry.event_type or "event")
            lines.append("## [%s] %s | %s" % (date_str, event_label, (entry.name or "")[:200]))
            if entry.summary:
                lines.append("")
                lines.append(entry.summary.strip()[:500])
            lines.append("")
        log_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    def _safe_filename(self, value):
        text = re.sub(r"[\\/:*?\"<>|]+", "-", value or "wiki-page")
        text = re.sub(r"\s+", "-", text).strip(".- ")
        return text[:120] or "wiki-page"

    def _log(self, event_type, name, source=False, article=False, summary=""):
        vals = {"event_type": event_type, "name": name[:200], "summary": summary}
        if source:
            vals["source_document_id"] = source.id
        if article:
            vals["article_id"] = article.id
        self.env["diecut.kb.wiki.log"].sudo().create(vals)
