# -*- coding: utf-8 -*-
"""
Thin compatibility entrypoint.

All worker logic has moved to `scripts/tds_worker/`.
This file intentionally keeps the historical script path stable for Odoo runtime callers.
"""

from tds_worker.main import main


if __name__ == "__main__":
    main()

