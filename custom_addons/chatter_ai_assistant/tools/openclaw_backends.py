# -*- coding: utf-8 -*-

import json
import os
import signal
import shlex
import shutil
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
        source_state_dir = os.environ.get("OPENCLAW_SOURCE_STATE_DIR") or ""
        state_dir = os.environ.get("OPENCLAW_STATE_DIR") or "/root/.openclaw"
        self._refresh_runtime_auth_state(source_state_dir=source_state_dir, state_dir=state_dir)
        shell_cmd = self._build_shell_command(
            session_id=session_id,
            message=message,
            working_directory=workdir,
            home_dir=home_dir,
            state_dir=state_dir,
        )
        env = os.environ.copy()
        env["HOME"] = home_dir
        if source_state_dir:
            env["OPENCLAW_SOURCE_STATE_DIR"] = source_state_dir
        env["OPENCLAW_STATE_DIR"] = state_dir
        env["PATH"] = self._build_path()
        result = self._run_process(
            ["bash", "-lc", shell_cmd],
            env=env,
            timeout=self.timeout + 30,
        )
        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()
        if trace_path:
            self._write_trace(
                trace_path,
                {
                    "home_dir": home_dir,
                    "source_state_dir": source_state_dir,
                    "state_dir": state_dir,
                    "cli_command": self.cli_command,
                    "agent_id": self.agent_id,
                    "working_directory": workdir,
                },
                result.returncode,
                stdout,
                stderr,
            )
        if result.returncode != 0:
            raise ChatterAiBackendError(stderr or stdout or "OpenClaw helper process failed.")

        parsed = self._parse_json_payload(stderr) or self._parse_json_payload(stdout)
        if parsed:
            stop_reason = (parsed.get("stopReason") or "").strip().lower()
            texts = []
            for item in parsed.get("payloads") or []:
                if isinstance(item, dict) and item.get("text"):
                    texts.append(item["text"])
            reply_text = "\n".join(texts).strip()
            if stop_reason == "error":
                raise ChatterAiBackendError(reply_text or parsed.get("error") or "OpenClaw agent returned an error.")
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
        if self._looks_like_auth_failure(combined):
            raise ChatterAiBackendError(
                "OpenClaw/Codex 登录凭据已失效，请在宿主机重新登录 OpenClaw 或 Codex 后再试。"
            )
        return {
            "reply_text": combined,
            "raw_output": combined,
            "generated_files": [],
        }

    def _run_process(self, args, *, env, timeout):
        process = subprocess.Popen(
            args,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            start_new_session=True,
        )
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            self._terminate_process_group(process)
            stdout = (exc.stdout or "")
            stderr = (exc.stderr or "")
            raise ChatterAiBackendError(
                "OpenClaw 执行超过 %s 秒未返回，已终止该任务，请稍后重试。"
                % timeout
            ) from exc
        return subprocess.CompletedProcess(args, process.returncode, stdout, stderr)

    def _terminate_process_group(self, process):
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=5)
            return
        except Exception:
            pass
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except Exception:
            try:
                process.kill()
            except Exception:
                pass

    def _refresh_runtime_auth_state(self, *, source_state_dir, state_dir):
        if not source_state_dir:
            return
        source_root = os.path.abspath(source_state_dir)
        runtime_root = os.path.abspath(state_dir)
        if source_root == runtime_root:
            return
        if not (os.path.isdir(source_root) and os.path.isdir(runtime_root)):
            return
        for relative_path in (
            "identity",
            "memory",
            os.path.join("agents", self.agent_id, "agent"),
        ):
            self._sync_state_path(source_root, runtime_root, relative_path)

    def _sync_state_path(self, source_root, runtime_root, relative_path):
        source_path = os.path.abspath(os.path.join(source_root, relative_path))
        runtime_path = os.path.abspath(os.path.join(runtime_root, relative_path))
        if os.path.commonpath([source_root, source_path]) != source_root:
            return
        if os.path.commonpath([runtime_root, runtime_path]) != runtime_root:
            return
        if not os.path.exists(source_path):
            return
        if os.path.isdir(runtime_path) and not os.path.islink(runtime_path):
            shutil.rmtree(runtime_path)
        elif os.path.exists(runtime_path):
            os.unlink(runtime_path)
        os.makedirs(os.path.dirname(runtime_path), exist_ok=True)
        if os.path.isdir(source_path) and not os.path.islink(source_path):
            shutil.copytree(source_path, runtime_path, symlinks=True)
        else:
            shutil.copy2(source_path, runtime_path, follow_symlinks=False)

    def _write_trace(self, trace_path, diagnostics, returncode, stdout, stderr):
        with open(trace_path, "w", encoding="utf-8") as handle:
            handle.write("HOME: %s\n" % (diagnostics.get("home_dir") or ""))
            handle.write("OPENCLAW_SOURCE_STATE_DIR: %s\n" % (diagnostics.get("source_state_dir") or ""))
            handle.write("OPENCLAW_STATE_DIR: %s\n" % (diagnostics.get("state_dir") or ""))
            handle.write("CLI COMMAND: %s\n" % (diagnostics.get("cli_command") or ""))
            handle.write("AGENT ID: %s\n" % (diagnostics.get("agent_id") or ""))
            handle.write("WORKING DIRECTORY: %s\n" % (diagnostics.get("working_directory") or ""))
            handle.write("RETURN CODE: %s\n\n" % returncode)
            if stdout:
                handle.write(stdout)
            if stderr:
                if stdout:
                    handle.write("\n\n--- STDERR ---\n")
                handle.write(stderr)

    def _looks_like_auth_failure(self, text):
        value = (text or "").lower()
        return any(
            token in value
            for token in (
                "token refresh failed",
                "oauth token refresh failed",
                "refresh_token_reused",
                "please try signing in again",
            )
        )

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
