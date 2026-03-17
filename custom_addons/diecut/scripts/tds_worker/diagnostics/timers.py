# -*- coding: utf-8 -*-
from __future__ import annotations

import time
from contextlib import contextmanager


class StageTimer:
    def __init__(self):
        self.metrics = {}

    @contextmanager
    def track(self, name: str):
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            self.metrics[name] = elapsed_ms

