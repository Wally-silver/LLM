import time
from collections import defaultdict
from contextlib import contextmanager


class Metrics:
    def __init__(self):
        self.counters = defaultdict(int)
        self.latencies_ms: list[int] = []

    @contextmanager
    def track_latency(self):
        start = time.perf_counter()
        yield
        elapsed = int((time.perf_counter() - start) * 1000)
        self.latencies_ms.append(elapsed)

    def inc(self, name: str, value: int = 1) -> None:
        self.counters[name] += value

    def snapshot(self) -> dict:
        avg = int(sum(self.latencies_ms) / len(self.latencies_ms)) if self.latencies_ms else 0
        total = self.counters.get("requests", 0)
        hits = self.counters.get("cache_hits", 0)
        hit_rate = (hits / total) if total else 0.0
        return {
            "requests": total,
            "cache_hits": hits,
            "cache_hit_rate": round(hit_rate, 4),
            "avg_latency_ms": avg,
        }
