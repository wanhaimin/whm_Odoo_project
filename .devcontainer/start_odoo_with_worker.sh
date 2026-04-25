#!/usr/bin/env bash
set -euo pipefail

WORKER_LOG_PATH="${CHATTER_AI_WORKER_LOG_PATH:-/tmp/chatter_ai_worker.log}"
WORKER_SCRIPT="/mnt/extra-addons/chatter_ai_assistant/tools/worker_service.py"
OPENCLAW_SOURCE_STATE_DIR="${OPENCLAW_SOURCE_STATE_DIR:-/root/.openclaw}"
OPENCLAW_RUNTIME_STATE_DIR="${OPENCLAW_RUNTIME_STATE_DIR:-/opt/openclaw-state}"
OPENCLAW_COPY_MAIN_WORKSPACE="${OPENCLAW_COPY_MAIN_WORKSPACE:-0}"
ARGS=("$@")
OPENCLAW_RUNTIME_STATE_INITIALIZED=0

load_openclaw_env() {
  local env_file="$OPENCLAW_SOURCE_STATE_DIR/.env"
  if [ ! -f "$env_file" ]; then
    return 0
  fi

  set -a
  # shellcheck disable=SC1090
  . "$env_file"
  set +a
}

init_openclaw_runtime_state() {
  local source_config="$OPENCLAW_SOURCE_STATE_DIR/openclaw.json"
  local runtime_config="$OPENCLAW_RUNTIME_STATE_DIR/openclaw.json"

  if [ "$OPENCLAW_RUNTIME_STATE_INITIALIZED" = "1" ]; then
    return 0
  fi

  if [ ! -f "$source_config" ]; then
    OPENCLAW_RUNTIME_STATE_INITIALIZED=1
    return 0
  fi

  mkdir -p "$OPENCLAW_RUNTIME_STATE_DIR"
  rm -rf "$OPENCLAW_RUNTIME_STATE_DIR/extensions" "$OPENCLAW_RUNTIME_STATE_DIR/browser"
  mkdir -p \
    "$OPENCLAW_RUNTIME_STATE_DIR/agents/main/sessions" \
    "$OPENCLAW_RUNTIME_STATE_DIR/agents/odoo-diecut-dev/sessions" \
    "$OPENCLAW_RUNTIME_STATE_DIR/agents/odoo-diecut-tds/sessions"

  sync_openclaw_state_path "identity"
  sync_openclaw_state_path "memory"
  if is_truthy "$OPENCLAW_COPY_MAIN_WORKSPACE"; then
    sync_openclaw_state_path "workspace"
  else
    rm -rf "$OPENCLAW_RUNTIME_STATE_DIR/.sync-signatures/workspace.sha256"
    mkdir -p "$OPENCLAW_RUNTIME_STATE_DIR/workspace"
  fi
  sync_openclaw_state_path "workspace-odoo-diecut-dev"
  sync_openclaw_state_path "workspace-odoo-diecut-tds"
  sync_openclaw_state_path "agents/main/agent"
  sync_openclaw_state_path "agents/odoo-diecut-dev/agent"
  sync_openclaw_state_path "agents/odoo-diecut-tds/agent"

  python3 - "$source_config" "$runtime_config" <<'PY'
import json
import os
import re
import sys
from pathlib import Path

source_path = Path(sys.argv[1])
runtime_path = Path(sys.argv[2])
runtime_root = runtime_path.parent
if not source_path.exists():
    raise SystemExit(0)

config = json.loads(source_path.read_text(encoding="utf-8-sig"))
plugins = config.get("plugins") or {}
channels = config.get("channels") or {}

WINDOWS_PATH_RE = re.compile(r"^[A-Za-z]:[\\/]")


def is_windows_path(value):
    return isinstance(value, str) and (
        WINDOWS_PATH_RE.match(value)
        or "\\Users\\" in value
        or "/Users/" in value and not value.startswith("/opt/")
    )


def is_valid_container_path(value):
    if not isinstance(value, str) or not value.strip():
        return False
    if is_windows_path(value):
        return False
    if value.startswith("/tmp/") and ":" in value:
        return False
    if value.startswith("/"):
        return os.path.exists(value)
    return False


blocked_plugins = {"openclaw-weixin", "pdf-parse-local", "obsidian-local", "browser"}
allow = [item for item in (plugins.get("allow") or []) if item not in blocked_plugins]
entries = {
    key: value for key, value in (plugins.get("entries") or {}).items() if key not in blocked_plugins
}
installs = {
    key: value for key, value in (plugins.get("installs") or {}).items() if key not in blocked_plugins
}

if allow:
    plugins["allow"] = allow
else:
    plugins.pop("allow", None)
if entries:
    plugins["entries"] = entries
else:
    plugins.pop("entries", None)
if installs:
    plugins["installs"] = installs
else:
    plugins.pop("installs", None)

if "load" in plugins and "paths" in plugins["load"]:
    valid_paths = [p for p in plugins["load"]["paths"] if is_valid_container_path(p)]
    if valid_paths:
        plugins["load"]["paths"] = valid_paths
    else:
        plugins["load"].pop("paths", None)
        if not plugins["load"]:
            plugins.pop("load", None)

blocked_channels = {"discord", "openclaw-weixin"}
channels = {key: value for key, value in channels.items() if key not in blocked_channels}
if channels:
    config["channels"] = channels
else:
    config.pop("channels", None)

agents = config.setdefault("agents", {})
allowed_agent_ids = {"main", "odoo-diecut-dev", "odoo-diecut-tds"}
sanitized_agents = []

for agent in agents.get("list") or []:
    agent_id = agent.get("id")
    if agent_id not in allowed_agent_ids:
        continue
    tools = agent.get("tools") or {}
    tools.pop("profile", None)
    also_allow = [item for item in (tools.get("alsoAllow") or []) if item not in blocked_plugins]
    if also_allow:
        tools["alsoAllow"] = also_allow
    else:
        tools.pop("alsoAllow", None)
    if tools:
        agent["tools"] = tools
        
    # Remove blocked channels from agent's active channels
    if "channels" in agent and isinstance(agent["channels"], list):
        agent["channels"] = [c for c in agent["channels"] if c not in blocked_channels]
        if not agent["channels"]:
            agent.pop("channels", None)
            
    if agent_id == "main":
        agent["workspace"] = str(runtime_root / "workspace")
        agent["agentDir"] = str(runtime_root / "agents" / "main" / "agent")
    elif agent_id == "odoo-diecut-dev":
        agent["workspace"] = str(runtime_root / "workspace-odoo-diecut-dev")
        agent["agentDir"] = str(runtime_root / "agents" / "odoo-diecut-dev" / "agent")
    elif agent_id == "odoo-diecut-tds":
        agent["workspace"] = str(runtime_root / "workspace-odoo-diecut-tds")
        agent["agentDir"] = str(runtime_root / "agents" / "odoo-diecut-tds" / "agent")
    sanitized_agents.append(agent)

agents["list"] = sanitized_agents

defaults = agents.get("defaults") or {}
defaults["workspace"] = str(runtime_root / "workspace")
agents["defaults"] = defaults

top_tools = config.get("tools") or {}
top_tools.pop("profile", None)
config["tools"] = top_tools

# Avoid validating provider blocks whose required environment is absent inside
# the container. Agents using the local chatter bridge are configured to use the
# custom provider, so removing OpenAI here prevents unrelated desktop settings
# from breaking Odoo's worker startup.
providers = ((config.get("models") or {}).get("providers") or {})
openai_provider = providers.get("openai")
if isinstance(openai_provider, dict):
    api_key = openai_provider.get("apiKey")
    if isinstance(api_key, str) and "OPENAI_API_KEY" in api_key and not os.environ.get("OPENAI_API_KEY"):
        providers.pop("openai", None)

runtime_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY

  chmod 700 "$OPENCLAW_RUNTIME_STATE_DIR" 2>/dev/null || true
  chmod 600 "$runtime_config" 2>/dev/null || true
  chmod go-w \
    "$OPENCLAW_RUNTIME_STATE_DIR" \
    "$OPENCLAW_RUNTIME_STATE_DIR/agents" \
    "$OPENCLAW_RUNTIME_STATE_DIR/agents/main" \
    "$OPENCLAW_RUNTIME_STATE_DIR/agents/odoo-diecut-dev" \
    "$OPENCLAW_RUNTIME_STATE_DIR/agents/odoo-diecut-tds" \
    "$runtime_config" \
    2>/dev/null || true
  OPENCLAW_RUNTIME_STATE_INITIALIZED=1
}

is_truthy() {
  case "${1:-}" in
    1|true|TRUE|yes|YES|on|ON)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

openclaw_path_signature() {
  local path="$1"
  python3 - "$path" <<'PY'
import hashlib
import os
import sys
from pathlib import Path

path = Path(sys.argv[1])
digest = hashlib.sha256()

if not path.exists():
    print("missing")
    raise SystemExit(0)

def add_entry(rel_path, stat):
    digest.update(rel_path.encode("utf-8", "surrogateescape"))
    digest.update(b"\0")
    digest.update(str(stat.st_mode).encode())
    digest.update(b"\0")
    digest.update(str(stat.st_size).encode())
    digest.update(b"\0")
    digest.update(str(stat.st_mtime_ns).encode())
    digest.update(b"\n")

if path.is_file():
    add_entry(path.name, path.stat())
else:
    for root, dirs, files in os.walk(path):
        dirs.sort()
        files.sort()
        root_path = Path(root)
        for name in dirs:
            item = root_path / name
            add_entry(str(item.relative_to(path)), item.stat())
        for name in files:
            item = root_path / name
            add_entry(str(item.relative_to(path)), item.stat())

print(digest.hexdigest())
PY
}

sync_openclaw_state_path() {
  local relative_path="$1"
  local source_path="$OPENCLAW_SOURCE_STATE_DIR/$relative_path"
  local runtime_path="$OPENCLAW_RUNTIME_STATE_DIR/$relative_path"
  local signature_dir="$OPENCLAW_RUNTIME_STATE_DIR/.sync-signatures"
  local signature_key="${relative_path//\//__}"
  local signature_file="$signature_dir/$signature_key.sha256"
  local current_signature

  if [ ! -e "$source_path" ]; then
    rm -rf "$runtime_path" "$signature_file"
    return 0
  fi

  mkdir -p "$signature_dir"
  current_signature="$(openclaw_path_signature "$source_path")"
  if [ -e "$runtime_path" ] \
    && [ -f "$signature_file" ] \
    && [ "$(cat "$signature_file")" = "$current_signature" ]; then
    return 0
  fi

  rm -rf "$runtime_path"
  mkdir -p "$(dirname "$runtime_path")"
  cp -a "$source_path" "$runtime_path"
  printf "%s\n" "$current_signature" > "$signature_file"
  chmod -R go-w "$runtime_path" || true
}

has_arg() {
  local needle="$1"
  shift
  for arg in "$@"; do
    if [ "$arg" = "$needle" ]; then
      return 0
    fi
  done
  return 1
}

if [ -f "$WORKER_SCRIPT" ]; then
  load_openclaw_env
  init_openclaw_runtime_state
  export OPENCLAW_SOURCE_STATE_DIR
  export OPENCLAW_STATE_DIR="$OPENCLAW_RUNTIME_STATE_DIR"
  python3 "$WORKER_SCRIPT" \
    --base-url "${CHATTER_AI_WORKER_BASE_URL:-http://127.0.0.1:8069}" \
    --token "${CHATTER_AI_WORKER_TOKEN:-chatter-ai-local-dev}" \
    --poll-seconds "${CHATTER_AI_WORKER_POLL_SECONDS:-0.5}" \
    >>"$WORKER_LOG_PATH" 2>&1 &
fi

if ! has_arg "--db_host" "${ARGS[@]}" && [ -n "${DB_HOST:-}" ]; then
  ARGS+=(--db_host "$DB_HOST")
fi
if ! has_arg "--db_user" "${ARGS[@]}" && [ -n "${DB_USER:-}" ]; then
  ARGS+=(--db_user "$DB_USER")
fi
if ! has_arg "--db_password" "${ARGS[@]}" && [ -n "${DB_PASSWORD:-}" ]; then
  ARGS+=(--db_password "$DB_PASSWORD")
fi

load_openclaw_env
init_openclaw_runtime_state
export OPENCLAW_SOURCE_STATE_DIR
export OPENCLAW_STATE_DIR="$OPENCLAW_RUNTIME_STATE_DIR"

exec odoo "${ARGS[@]}"
