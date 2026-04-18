#!/usr/bin/env bash
set -euo pipefail

WORKER_LOG_PATH="${CHATTER_AI_WORKER_LOG_PATH:-/tmp/chatter_ai_worker.log}"
WORKER_SCRIPT="/mnt/extra-addons/chatter_ai_assistant/tools/worker_service.py"
OPENCLAW_SOURCE_STATE_DIR="${OPENCLAW_SOURCE_STATE_DIR:-/root/.openclaw}"
OPENCLAW_RUNTIME_STATE_DIR="${OPENCLAW_RUNTIME_STATE_DIR:-/opt/openclaw-state}"
ARGS=("$@")

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

  if [ ! -f "$source_config" ]; then
    return 0
  fi

  mkdir -p "$OPENCLAW_RUNTIME_STATE_DIR"
  rm -rf "$OPENCLAW_RUNTIME_STATE_DIR/extensions" "$OPENCLAW_RUNTIME_STATE_DIR/browser"
  mkdir -p \
    "$OPENCLAW_RUNTIME_STATE_DIR/agents/main" \
    "$OPENCLAW_RUNTIME_STATE_DIR/agents/odoo-diecut-dev" \
    "$OPENCLAW_RUNTIME_STATE_DIR/agents/odoo-diecut-tds"

  if [ -d "$OPENCLAW_SOURCE_STATE_DIR/identity" ]; then
    rm -rf "$OPENCLAW_RUNTIME_STATE_DIR/identity"
    cp -a "$OPENCLAW_SOURCE_STATE_DIR/identity" "$OPENCLAW_RUNTIME_STATE_DIR/identity"
  fi
  if [ -d "$OPENCLAW_SOURCE_STATE_DIR/memory" ]; then
    rm -rf "$OPENCLAW_RUNTIME_STATE_DIR/memory"
    cp -a "$OPENCLAW_SOURCE_STATE_DIR/memory" "$OPENCLAW_RUNTIME_STATE_DIR/memory"
  fi
  if [ -d "$OPENCLAW_SOURCE_STATE_DIR/workspace" ]; then
    rm -rf "$OPENCLAW_RUNTIME_STATE_DIR/workspace"
    cp -a "$OPENCLAW_SOURCE_STATE_DIR/workspace" "$OPENCLAW_RUNTIME_STATE_DIR/workspace"
  fi
  if [ -d "$OPENCLAW_SOURCE_STATE_DIR/workspace-odoo-diecut-dev" ]; then
    rm -rf "$OPENCLAW_RUNTIME_STATE_DIR/workspace-odoo-diecut-dev"
    cp -a "$OPENCLAW_SOURCE_STATE_DIR/workspace-odoo-diecut-dev" "$OPENCLAW_RUNTIME_STATE_DIR/workspace-odoo-diecut-dev"
  fi
  if [ -d "$OPENCLAW_SOURCE_STATE_DIR/workspace-odoo-diecut-tds" ]; then
    rm -rf "$OPENCLAW_RUNTIME_STATE_DIR/workspace-odoo-diecut-tds"
    cp -a "$OPENCLAW_SOURCE_STATE_DIR/workspace-odoo-diecut-tds" "$OPENCLAW_RUNTIME_STATE_DIR/workspace-odoo-diecut-tds"
  fi
  if [ -d "$OPENCLAW_SOURCE_STATE_DIR/agents/main/agent" ]; then
    rm -rf "$OPENCLAW_RUNTIME_STATE_DIR/agents/main/agent"
    cp -a "$OPENCLAW_SOURCE_STATE_DIR/agents/main/agent" "$OPENCLAW_RUNTIME_STATE_DIR/agents/main/agent"
  fi
  if [ -d "$OPENCLAW_SOURCE_STATE_DIR/agents/odoo-diecut-dev/agent" ]; then
    rm -rf "$OPENCLAW_RUNTIME_STATE_DIR/agents/odoo-diecut-dev/agent"
    cp -a "$OPENCLAW_SOURCE_STATE_DIR/agents/odoo-diecut-dev/agent" "$OPENCLAW_RUNTIME_STATE_DIR/agents/odoo-diecut-dev/agent"
  fi
  if [ -d "$OPENCLAW_SOURCE_STATE_DIR/agents/odoo-diecut-tds/agent" ]; then
    rm -rf "$OPENCLAW_RUNTIME_STATE_DIR/agents/odoo-diecut-tds/agent"
    cp -a "$OPENCLAW_SOURCE_STATE_DIR/agents/odoo-diecut-tds/agent" "$OPENCLAW_RUNTIME_STATE_DIR/agents/odoo-diecut-tds/agent"
  fi

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


blocked_plugins = {"openclaw-weixin", "pdf-parse-local"}
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

blocked_channels = {"openclaw-weixin"}
channels = {key: value for key, value in channels.items() if key not in blocked_channels}
if channels:
    config["channels"] = channels
else:
    config.pop("channels", None)

for agent in (config.get("agents") or {}).get("list") or []:
    tools = agent.get("tools") or {}
    tools.pop("profile", None)
    also_allow = [item for item in (tools.get("alsoAllow") or []) if item != "pdf-parse-local"]
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
            
    agent_id = agent.get("id")
    if agent_id == "main":
        agent["workspace"] = str(runtime_root / "workspace")
        agent["agentDir"] = str(runtime_root / "agents" / "main" / "agent")
    elif agent_id == "odoo-diecut-dev":
        agent["workspace"] = str(runtime_root / "workspace-odoo-diecut-dev")
        agent["agentDir"] = str(runtime_root / "agents" / "odoo-diecut-dev" / "agent")
    elif agent_id == "odoo-diecut-tds":
        agent["workspace"] = str(runtime_root / "workspace-odoo-diecut-tds")
        agent["agentDir"] = str(runtime_root / "agents" / "odoo-diecut-tds" / "agent")

defaults = (config.get("agents") or {}).get("defaults") or {}
defaults["workspace"] = str(runtime_root / "workspace")

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

  chmod -R go-w "$OPENCLAW_RUNTIME_STATE_DIR" || true
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
export OPENCLAW_STATE_DIR="$OPENCLAW_RUNTIME_STATE_DIR"

exec odoo "${ARGS[@]}"
