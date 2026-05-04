# -*- coding: utf-8 -*-
"""Scan a diecut Knowledge Vault into a deterministic graph manifest.

This script borrows the deterministic-parser idea from Lum1104's
Understand-Anything project (MIT License), but is adapted for the
diecut_knowledge Vault shape and does not call Odoo, Dify, or any LLM.

Usage:
    python custom_addons/diecut_knowledge/scripts/scan_vault_graph.py <vault_root>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VERSION = "diecut-vault-scan-v1"
GRAPH_DIR = ".diecut_knowledge_graph"
DEFAULT_OUTPUT = "scan-manifest.json"
SUPPORTED_RAW_EXTENSIONS = {".pdf", ".txt", ".md", ".markdown"}
INFRA_FILES = {"index.md", "log.md", "agents.md", "claude.md", "soul.md"}

WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|([^\]]+))?\]\]")
FRONTMATTER_RE = re.compile(r"^\ufeff?---\s*\n(.*?)\n---\s*\n", re.S)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.M)
LOG_ENTRY_RE = re.compile(r"^##\s+\[(\d{4}-\d{2}-\d{2})\]\s+([\w-]+)\s*\|\s*(.+)$", re.M)


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan diecut Knowledge Vault wiki/raw files into graph JSON.")
    parser.add_argument("vault_root", help="Knowledge Vault root or its wiki directory")
    parser.add_argument("--output", help="Output JSON path. Defaults to <vault_root>/.diecut_knowledge_graph/scan-manifest.json")
    parser.add_argument("--no-write", action="store_true", help="Print summary only; do not write scan-manifest.json")
    args = parser.parse_args()

    target = Path(args.vault_root).expanduser().resolve()
    manifest = scan_vault(target)
    output_path = Path(args.output).expanduser().resolve() if args.output else default_output_path(manifest)

    if not args.no_write:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    stats = manifest["stats"]
    print(
        "Detected=%s articles=%s sources=%s topics=%s wikilinks=%s unresolved=%s warnings=%s"
        % (
            manifest["detected"],
            stats["articles"],
            stats["sources"],
            stats["topics"],
            stats["wikilinks"],
            stats["unresolved"],
            len(manifest["warnings"]),
        )
    )
    if not args.no_write:
        print("Wrote %s" % output_path)
    return 0 if manifest["detected"] else 1


def scan_vault(target: Path) -> dict[str, Any]:
    vault_root, wiki_root, raw_root = resolve_roots(target)
    warnings: list[dict[str, Any]] = []
    index_path = wiki_root / "index.md"
    log_path = wiki_root / "log.md"

    detected = wiki_root.is_dir() and index_path.is_file()
    if not wiki_root.is_dir():
        warnings.append(warning("missing_wiki_root", "Wiki directory was not found.", str(wiki_root)))
    if not index_path.is_file():
        warnings.append(warning("missing_index", "wiki/index.md was not found.", str(index_path)))
    if not log_path.is_file():
        warnings.append(warning("missing_log", "wiki/log.md was not found.", str(log_path)))

    categories = parse_index(index_path) if index_path.is_file() else []
    log_entries = parse_log(log_path) if log_path.is_file() else []

    article_records = parse_articles(wiki_root, categories, warnings) if wiki_root.is_dir() else []
    article_ids = {record["id"] for record in article_records}
    name_map = build_name_map(article_records, warnings)

    topic_nodes, category_edges = build_topic_graph(categories, name_map, article_ids, warnings)
    article_nodes, related_edges = build_article_graph(article_records, name_map, article_ids, warnings)
    source_nodes = parse_sources(raw_root, vault_root, warnings) if raw_root.is_dir() else []
    orphan_warnings = find_orphans(article_nodes, related_edges)
    warnings.extend(orphan_warnings)

    nodes = article_nodes + topic_nodes + source_nodes
    edges = related_edges + category_edges
    stats = {
        "articles": len(article_nodes),
        "sources": len(source_nodes),
        "topics": len(topic_nodes),
        "wikilinks": sum(len(record["wikilinks"]) for record in article_records),
        "unresolved": len(
            [item for item in warnings if item["type"] in {"unresolved_wikilink", "unresolved_index_link"}]
        ),
        "edges": len(edges),
    }

    return {
        "version": VERSION,
        "kind": "knowledge_scan",
        "detected": bool(detected),
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "vault_root": str(vault_root),
        "wiki_root": str(wiki_root),
        "raw_root": str(raw_root),
        "stats": stats,
        "nodes": nodes,
        "edges": edges,
        "categories": categories,
        "log_entries": log_entries,
        "warnings": warnings,
    }


def resolve_roots(target: Path) -> tuple[Path, Path, Path]:
    if target.name.lower() == "wiki":
        vault_root = target.parent
        wiki_root = target
    elif (target / "wiki").is_dir():
        vault_root = target
        wiki_root = target / "wiki"
    else:
        vault_root = target
        wiki_root = target
    raw_root = vault_root / "raw"
    return vault_root, wiki_root, raw_root


def default_output_path(manifest: dict[str, Any]) -> Path:
    return Path(manifest["vault_root"]) / GRAPH_DIR / DEFAULT_OUTPUT


def parse_articles(wiki_root: Path, categories: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    category_lookup: dict[str, str] = {}
    for category in categories:
        for target in category.get("articles", []):
            category_lookup[normalize_key(target)] = category["name"]

    records = []
    for path in sorted(wiki_root.rglob("*.md"), key=lambda item: str(item).lower()):
        rel = path.relative_to(wiki_root)
        if rel.parent == Path(".") and rel.name.lower() in INFRA_FILES:
            continue

        text = path.read_text(encoding="utf-8", errors="replace")
        frontmatter = extract_frontmatter(text)
        h1 = extract_h1(text)
        stem = normalize_path_stem(rel)
        slug = (frontmatter.get("wiki_slug") or stem).strip()
        title = frontmatter.get("title") or h1 or path.stem
        category = (
            category_lookup.get(normalize_key(slug))
            or category_lookup.get(normalize_key(path.stem))
            or category_lookup.get(normalize_key(stem))
            or frontmatter.get("category")
            or ""
        )
        wikilinks = extract_wikilinks(text)
        word_count = len(re.findall(r"\S+", text))
        records.append(
            {
                "id": "article:%s" % stem,
                "stem": stem,
                "slug": slug,
                "title": title,
                "file_path": str(rel).replace("\\", "/"),
                "frontmatter": frontmatter,
                "summary": extract_first_paragraph(text),
                "headings": extract_headings(text),
                "wikilinks": wikilinks,
                "category": category,
                "word_count": word_count,
                "line_count": text.count("\n") + 1,
                "complexity": complexity_for(wikilinks, word_count),
                "content_excerpt": strip_frontmatter(text).strip()[:3000],
            }
        )
    if not records:
        warnings.append(warning("empty_wiki", "No content Markdown files were found.", str(wiki_root)))
    return records


def build_name_map(records: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> dict[str, str]:
    result: dict[str, str] = {}
    seen: dict[str, list[str]] = {}

    for record in records:
        keys = {
            record["stem"],
            Path(record["stem"]).name,
            record["slug"],
            record["title"],
            record["frontmatter"].get("title", ""),
        }
        for key in keys:
            normalized = normalize_key(key)
            if not normalized:
                continue
            seen.setdefault(normalized, []).append(record["id"])
            result.setdefault(normalized, record["id"])

    for key, ids in sorted(seen.items()):
        unique_ids = sorted(set(ids))
        if len(unique_ids) > 1:
            result.pop(key, None)
            warnings.append(
                warning(
                    "duplicate_slug",
                    "Ambiguous wiki target maps to multiple articles.",
                    key,
                    {"article_ids": unique_ids},
                )
            )
    return result


def build_article_graph(records: list[dict[str, Any]], name_map: dict[str, str], article_ids: set[str], warnings: list[dict[str, Any]]):
    nodes = []
    edges = []
    edge_keys = set()
    for record in records:
        nodes.append(
            {
                "id": record["id"],
                "type": "article",
                "name": record["title"],
                "summary": record["summary"] or "Wiki article: %s" % record["title"],
                "filePath": record["file_path"],
                "tags": sorted(set(filter(None, [record["category"], record["frontmatter"].get("wiki_page_type", "")]))),
                "complexity": record["complexity"],
                "metadata": {
                    "wiki_slug": record["slug"],
                    "frontmatter": record["frontmatter"],
                    "headings": record["headings"],
                    "word_count": record["word_count"],
                    "line_count": record["line_count"],
                    "category": record["category"] or None,
                    "wikilinks": [link["target"] for link in record["wikilinks"]],
                    "content_excerpt": record["content_excerpt"],
                },
            }
        )
        for link in record["wikilinks"]:
            target_id = resolve_wikilink(link["target"], name_map, article_ids)
            if not target_id or target_id == record["id"]:
                warnings.append(
                    warning(
                        "unresolved_wikilink",
                        "Wiki link target could not be resolved.",
                        record["file_path"],
                        {"source": record["id"], "target": link["target"]},
                    )
                )
                continue
            edge_key = (record["id"], target_id, "related")
            if edge_key in edge_keys:
                continue
            edge_keys.add(edge_key)
            edges.append(
                {
                    "source": record["id"],
                    "target": target_id,
                    "type": "related",
                    "direction": "forward",
                    "weight": 0.7,
                    "description": link.get("display") or link["target"],
                }
            )
    return nodes, edges


def build_topic_graph(categories: list[dict[str, Any]], name_map: dict[str, str], article_ids: set[str], warnings: list[dict[str, Any]]):
    nodes = []
    edges = []
    for index, category in enumerate(categories, start=1):
        topic_id = "topic:%s" % slugify(category["name"])
        nodes.append(
            {
                "id": topic_id,
                "type": "topic",
                "name": category["name"],
                "summary": "Index category: %s" % category["name"],
                "tags": ["index"],
                "complexity": "simple",
                "metadata": {"order": index, "article_targets": category.get("articles", [])},
            }
        )
        for target in category.get("articles", []):
            article_id = resolve_wikilink(target, name_map, article_ids)
            if not article_id:
                warnings.append(
                    warning(
                        "unresolved_index_link",
                        "index.md category link could not be resolved.",
                        category["name"],
                        {"target": target},
                    )
                )
                continue
            edges.append(
                {
                    "source": article_id,
                    "target": topic_id,
                    "type": "categorized_under",
                    "direction": "forward",
                    "weight": 0.6,
                }
            )
    return nodes, edges


def parse_sources(raw_root: Path, vault_root: Path, warnings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    nodes = []
    for path in sorted(raw_root.rglob("*"), key=lambda item: str(item).lower()):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_RAW_EXTENSIONS:
            continue
        rel = path.relative_to(vault_root)
        rel_text = str(rel).replace("\\", "/")
        nodes.append(
            {
                "id": "source:%s" % rel_text,
                "type": "source",
                "name": path.name,
                "summary": "Raw source file: %s" % path.name,
                "filePath": rel_text,
                "tags": ["raw", path.suffix.lower().lstrip(".")],
                "complexity": "simple",
                "metadata": {
                    "size_bytes": path.stat().st_size,
                    "sha256": hash_file(path),
                    "raw_state": raw_state_for(path),
                },
            }
        )
    if not raw_root.exists():
        warnings.append(warning("missing_raw_root", "raw directory was not found.", str(raw_root)))
    return nodes


def parse_index(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    categories = []
    current = None
    for line in text.splitlines():
        match = re.match(r"^##\s+(.+)$", line)
        if match:
            current = {"name": match.group(1).strip(), "articles": []}
            categories.append(current)
            continue
        if current:
            current["articles"].extend(link["target"] for link in extract_wikilinks(line))
    return categories


def parse_log(path: Path) -> list[dict[str, str]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    return [
        {"date": match.group(1), "operation": match.group(2), "title": match.group(3).strip()}
        for match in LOG_ENTRY_RE.finditer(text)
    ]


def extract_frontmatter(text: str) -> dict[str, str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}
    values = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values


def strip_frontmatter(text: str) -> str:
    return FRONTMATTER_RE.sub("", text, count=1)


def extract_wikilinks(text: str) -> list[dict[str, str]]:
    return [
        {"target": match.group(1).strip(), "display": (match.group(2) or "").strip()}
        for match in WIKILINK_RE.finditer(text or "")
    ]


def extract_headings(text: str) -> list[dict[str, Any]]:
    return [{"level": len(match.group(1)), "text": match.group(2).strip()} for match in HEADING_RE.finditer(text)]


def extract_h1(text: str) -> str:
    for heading in extract_headings(text):
        if heading["level"] == 1:
            return heading["text"]
    return ""


def extract_first_paragraph(text: str) -> str:
    stripped = strip_frontmatter(text).strip()
    paragraph: list[str] = []
    for raw_line in stripped.splitlines():
        line = raw_line.strip()
        if not line and paragraph:
            break
        if not line or line.startswith("#") or line.startswith(">") or re.match(r"^[-*_]{3,}$", line):
            continue
        paragraph.append(line)
    summary = " ".join(paragraph).strip()
    return summary[:197] + "..." if len(summary) > 200 else summary


def resolve_wikilink(target: str, name_map: dict[str, str], article_ids: set[str]) -> str | None:
    key = normalize_key(target)
    if not key or key.startswith("-"):
        return None
    article_id = name_map.get(key)
    return article_id if article_id in article_ids else None


def find_orphans(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    connected = {edge["source"] for edge in edges} | {edge["target"] for edge in edges}
    return [
        warning("orphan_article", "Article has no resolved wiki links.", node["filePath"], {"article_id": node["id"]})
        for node in nodes
        if node["id"] not in connected
    ]


def complexity_for(wikilinks: list[dict[str, str]], word_count: int) -> str:
    if len(wikilinks) > 15 or word_count > 2000:
        return "complex"
    if len(wikilinks) > 5 or word_count > 700:
        return "moderate"
    return "simple"


def normalize_path_stem(path: Path) -> str:
    return str(path.with_suffix("")).replace("\\", "/")


def normalize_key(value: str | None) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def slugify(value: str) -> str:
    text = normalize_key(value)
    text = re.sub(r"[^\w\u4e00-\u9fff]+", "-", text, flags=re.U)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text or "topic"


def raw_state_for(path: Path) -> str:
    parts = {part.lower() for part in path.parts}
    if "processed" in parts:
        return "processed"
    if "failed" in parts:
        return "failed"
    if "inbox" in parts:
        return "inbox"
    return "raw"


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def warning(kind: str, message: str, path: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = {"type": kind, "message": message, "path": path}
    if extra:
        payload.update(extra)
    return payload


if __name__ == "__main__":
    sys.exit(main())
