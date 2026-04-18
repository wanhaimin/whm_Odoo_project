# -*- coding: utf-8 -*-

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

from openclaw_backends import ChatterAiBackendError, ChatterAiCliBackend


def post_json(url, payload, timeout):
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
    return json.loads(raw)


def build_backend(run_payload):
    return ChatterAiCliBackend(
        cli_command=run_payload["cli_command"],
        node_bin_path=run_payload.get("node_bin_path") or "",
        timeout=int(run_payload["timeout_seconds"]),
        agent_id=run_payload["agent_id"],
        thinking=run_payload["thinking"],
    )


def process_one(base_url, token, http_timeout):
    claim = post_json(
        base_url.rstrip("/") + "/chatter_ai_assistant/worker/claim",
        {"token": token},
        timeout=http_timeout,
    )
    if not claim.get("ok"):
        raise RuntimeError(claim.get("error") or "Failed to claim run.")
    run_payload = claim.get("run")
    if not run_payload:
        return False

    try:
        backend = build_backend(run_payload)
        result = backend.run(
            session_id=run_payload["session_id"],
            message=run_payload["message"],
            working_directory=run_payload["working_directory"],
            trace_path=run_payload.get("trace_path") or False,
        )
        post_json(
            base_url.rstrip("/") + "/chatter_ai_assistant/worker/complete",
            {"token": token, "run_id": run_payload["run_id"], "payload": result},
            timeout=http_timeout,
        )
    except (ChatterAiBackendError, Exception) as exc:  # pylint: disable=broad-except
        post_json(
            base_url.rstrip("/") + "/chatter_ai_assistant/worker/fail",
            {"token": token, "run_id": run_payload["run_id"], "error_message": str(exc)},
            timeout=http_timeout,
        )
    return True


def main():
    parser = argparse.ArgumentParser(description="External OpenClaw worker for chatter_ai_assistant.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8069")
    parser.add_argument("--token", default="chatter-ai-local-dev")
    parser.add_argument("--poll-seconds", type=float, default=0.5)
    parser.add_argument("--http-timeout", type=int, default=30)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    while True:
        try:
            did_work = process_one(args.base_url, args.token, args.http_timeout)
        except urllib.error.URLError as exc:
            print("worker connection error: %s" % exc, file=sys.stderr)
            did_work = False
        except Exception as exc:  # pylint: disable=broad-except
            print("worker error: %s" % exc, file=sys.stderr)
            did_work = False

        if args.once:
            return 0
        if not did_work:
            time.sleep(args.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
