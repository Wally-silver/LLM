from __future__ import annotations

import statistics
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager

import redis.asyncio as redis


class Metrics:
    """Sliding-window metrics with optional Redis aggregation."""

    def __init__(self, redis_client: redis.Redis | None = None, window_size: int = 1000):
        self.redis = redis_client
        self.window_size = window_size
        self.latencies: dict[str, deque[int]] = defaultdict(lambda: deque(maxlen=window_size))
        self.requests: dict[str, int] = defaultdict(int)
        self.errors: dict[str, int] = defaultdict(int)

    @asynccontextmanager
    async def track(self, endpoint: str):
        start = time.perf_counter()
        self.requests[endpoint] += 1
        if self.redis:
            await self.redis.hincrby("metrics:req", endpoint, 1)
        try:
            yield
        except Exception:
            self.errors[endpoint] += 1
            if self.redis:
                await self.redis.hincrby("metrics:err", endpoint, 1)
            raise
        finally:
            elapsed = int((time.perf_counter() - start) * 1000)
            self.latencies[endpoint].append(elapsed)

    @staticmethod
    def _percentile(values: list[int], p: float) -> int:
        if not values:
            return 0
        values = sorted(values)
        index = int((len(values) - 1) * p)
        return values[index]

    def snapshot_local(self) -> dict:
        out = {}
        for endpoint, vals in self.latencies.items():
            arr = list(vals)
            req = self.requests.get(endpoint, 0)
            err = self.errors.get(endpoint, 0)
            out[endpoint] = {
                "requests": req,
                "errors": err,
                "error_rate": round((err / req), 4) if req else 0.0,
                "avg_ms": int(statistics.fmean(arr)) if arr else 0,
                "p95_ms": self._percentile(arr, 0.95),
                "p99_ms": self._percentile(arr, 0.99),
            }
        return out

    async def snapshot(self) -> dict:
        local = self.snapshot_local()
        if not self.redis:
            return {"local": local}
        req = await self.redis.hgetall("metrics:req")
        err = await self.redis.hgetall("metrics:err")
        aggregate = {}
        for endpoint, total_req in req.items():
            total_req_i = int(total_req)
            total_err_i = int(err.get(endpoint, 0))
            aggregate[endpoint] = {
                "requests": total_req_i,
                "errors": total_err_i,
                "error_rate": round((total_err_i / total_req_i), 4) if total_req_i else 0.0,
            }
        return {"local": local, "aggregate": aggregate}
