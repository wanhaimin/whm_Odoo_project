# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse

from .pipeline import run_once
from .settings import load_settings


def build_parser():
    parser = argparse.ArgumentParser(description="OpenClaw TDS worker")
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--worker-token", default=None)
    parser.add_argument("--db", default=None)
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument("--source-id", type=int, default=0)
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    settings = load_settings(
        odoo_base_url=args.base_url,
        worker_token=args.worker_token,
        db_name=args.db,
    )
    if not settings.worker_token:
        raise SystemExit("Missing worker token. Set DIECUT_TDS_WORKER_TOKEN or OPENCLAW_GATEWAY_TOKEN.")
    run_once(settings, limit=args.limit, source_id=args.source_id or None)


if __name__ == "__main__":
    main()

