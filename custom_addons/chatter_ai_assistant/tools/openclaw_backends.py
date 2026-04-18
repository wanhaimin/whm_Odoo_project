# -*- coding: utf-8 -*-

import json
import os
import shlex
import subprocess


class ChatterAiBackendError(Exception):
    """Raised when the OpenClaw backend cannot produce a usable response."""


class ChatterAiCliBackend:
    def __init__(self, *, cli_command, node_bin_path=False, timeout=180, agent_id="main", thinking="medium"):
        self.cli_command = (cli_command or "").strip()
        self.node_bin_path = (node_bin_path or "").strip()
        self.timeout = int(timeout or 180)
        self.agent_id = (agent_id or "main").strip()
        self.thinking = (thinking or "medium").strip()

    def run(self, *, session_id, message, working_directory=False, trace_path=False):
        if not self.cli_command:
            raise ChatterAiBackendError("OpenClaw CLI command is not configured.")

        workdir = working_directory or os.getcwd()
        home_dir = os.environ.get("HOME") or "/root"
        state_dir = os.environ.get("OPENCLAW_STATE_DIR") or "/root/.openclaw"
        shell_cmd = self._build_shell_command(
            session_id=session_id,
            message=message,
            working_directory=workdir,
            home_dir=home_dir,
            state_dir=state_dir,
        )
        env = os.environ.copy()
        env["HOME"] = home_dir
        env["OPENCLAW_STATE_DIR"] = state_dir
        env["PATH"] = self._build_path()
        result = subprocess.run(
            ["bash", "-lc", shell_cmd],
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=self.timeout + 30,
            check=False,
        )
        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()
        if trace_path:
            with open(trace_path, "w", encoding="utf-8") as handle:
                handle.write("COMMAND: %s\n" % shell_cmd)
                handle.write("RETURN CODE: %s\n\n" % result.returncode)
                if stdout:
                    handle.write(stdout)
                if stderr:
                    if stdout:
                        handle.write("\n\n--- STDERR ---\n")
                    handle.write(stderr)
        if result.returncode != 0:
            raise ChatterAiBackendError(stderr or stdout or "OpenClaw helper process failed.")

        parsed = self._parse_json_payload(stderr) or self._parse_json_payload(stdout)
        if parsed:
            texts = []
            for item in parsed.get("payloads") or []:
                if isinstance(item, dict) and item.get("text"):
                    texts.append(item["text"])
            reply_text = "\n".join(texts).strip()
            nested_payload = self._parse_json_payload(reply_text)
            if isinstance(nested_payload, dict):
                response = dict(nested_payload)
                reply_text = response.get("reply_text") or reply_text
                response["reply_text"] = reply_text
                response["summary"] = response.get("summary") or parsed.get("summary") or reply_text[:500]
                response["generated_files"] = response.get("generated_files") or parsed.get("generated_files") or []
                response["raw_payload"] = parsed
                return response
            return {
                "reply_text": parsed.get("reply_text") or reply_text,
                "summary": parsed.get("summary") or reply_text[:500],
                "generated_files": parsed.get("generated_files") or [],
                "raw_payload": parsed,
            }
        combined = "\n".join(part for part in [stdout, stderr] if part).strip()
        return {
            "reply_text": combined,
            "raw_output": combined,
            "generated_files": [],
        }

    def _build_path(self):
        parts = []
        if self.node_bin_path:
            parts.append(self.node_bin_path)
        cli_dir = os.path.dirname(self.cli_command)
        if cli_dir:
            parts.append(cli_dir)
        parts.extend(
            [
                "/usr/local/sbin",
                "/usr/local/bin",
                "/usr/sbin",
                "/usr/bin",
                "/sbin",
                "/bin",
            ]
        )
        seen = set()
        ordered = []
        for item in parts:
            if item and item not in seen:
                ordered.append(item)
                seen.add(item)
        return ":".join(ordered)

    def _build_shell_command(self, *, session_id, message, working_directory, home_dir, state_dir):
        return "; ".join(
            [
                "export HOME=%s" % shlex.quote(home_dir),
                "export OPENCLAW_STATE_DIR=%s" % shlex.quote(state_dir),
                "export PATH=%s" % shlex.quote(self._build_path()),
                "cd %s" % shlex.quote(working_directory),
                "exec %s agent --local --agent %s --session-id %s --json --thinking %s --timeout %s --message %s"
                % (
                    shlex.quote(self.cli_command),
                    shlex.quote(self.agent_id),
                    shlex.quote(session_id),
                    shlex.quote(self.thinking),
                    shlex.quote(str(self.timeout)),
                    shlex.quote(message),
                ),
            ]
        )

    def _parse_json_payload(self, text):
        value = (text or "").strip()
        if not value:
            return False
        try:
            return json.loads(value)
        except Exception:
            start = value.find("{")
            end = value.rfind("}")
            if start >= 0 and end > start:
                try:
                    return json.loads(value[start : end + 1])
                except Exception:
                    return False
        return False
