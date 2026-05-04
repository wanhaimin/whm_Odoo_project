# -*- coding: utf-8 -*-

import logging
import os

_logger = logging.getLogger(__name__)

_MODULE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCHEMA_PATH = os.path.join(_MODULE_ROOT, "schema", "llm_wiki_schema.md")
_PROMPTS_DIR = os.path.join(_MODULE_ROOT, "prompts")
_cache = {}


def _read_text(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read().strip()


def load_schema(default=""):
    cache_key = ("schema", _SCHEMA_PATH)
    if cache_key in _cache:
        return _cache[cache_key]
    try:
        value = _read_text(_SCHEMA_PATH)
    except FileNotFoundError:
        _logger.warning("LLM Wiki schema file not found: %s", _SCHEMA_PATH)
        value = default or ""
    except OSError as exc:
        _logger.warning("Failed to load LLM Wiki schema %s: %s", _SCHEMA_PATH, exc)
        value = default or ""
    _cache[cache_key] = value
    return value


def load_prompt(name, default=""):
    filename = name if name.endswith(".md") else "%s.md" % name
    path = os.path.join(_PROMPTS_DIR, filename)
    cache_key = ("prompt", path)
    if cache_key in _cache:
        return _cache[cache_key]
    try:
        value = _read_text(path)
    except FileNotFoundError:
        _logger.warning("LLM prompt file not found: %s", path)
        value = default or ""
    except OSError as exc:
        _logger.warning("Failed to load LLM prompt %s: %s", path, exc)
        value = default or ""
    _cache[cache_key] = value
    return value


def build_system_prompt(task_name, default=""):
    schema = load_schema()
    file_prompt = load_prompt(task_name, default="")
    parts = []
    if schema:
        parts.append("# Canonical LLM Wiki Schema\n\n%s" % schema)
    if file_prompt:
        parts.append("# Task Prompt (file)\n\n%s" % file_prompt)
    if default and (default != file_prompt or not file_prompt):
        parts.append("# Task Prompt (fallback)\n\n%s" % default)
    if not parts:
        return default or ""
    return "\n\n---\n\n".join(parts)


def invalidate_cache():
    _cache.clear()
