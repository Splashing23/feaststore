"""A dependency-free Prometheus-style metrics collector.

We avoid pulling in the full prometheus_client for what amounts to three numbers.
This exposes request count, entity throughput, and a small latency histogram in
the text exposition format that Prometheus scrapes.
"""

from __future__ import annotations

import threading
from bisect import bisect_left

# Latency buckets in milliseconds (Prometheus expects cumulative "le" buckets).
_BUCKETS_MS = [1, 2, 5, 10, 25, 50, 100, 250, 500, 1000]


class Metrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._requests = 0
        self._entities = 0
        self._latency_sum = 0.0
        self._bucket_counts = [0] * (len(_BUCKETS_MS) + 1)  # +1 for +Inf

    def observe_request(self, n_entities: int, latency_ms: float) -> None:
        idx = bisect_left(_BUCKETS_MS, latency_ms)
        with self._lock:
            self._requests += 1
            self._entities += n_entities
            self._latency_sum += latency_ms
            self._bucket_counts[idx] += 1

    def render(self) -> str:
        with self._lock:
            requests = self._requests
            entities = self._entities
            latency_sum = self._latency_sum
            buckets = list(self._bucket_counts)

        lines = [
            "# HELP feaststore_requests_total Total online feature requests.",
            "# TYPE feaststore_requests_total counter",
            f"feaststore_requests_total {requests}",
            "# HELP feaststore_entities_total Total entity rows served.",
            "# TYPE feaststore_entities_total counter",
            f"feaststore_entities_total {entities}",
            "# HELP feaststore_request_latency_ms Request latency histogram (ms).",
            "# TYPE feaststore_request_latency_ms histogram",
        ]
        cumulative = 0
        for i, le in enumerate(_BUCKETS_MS):
            cumulative += buckets[i]
            lines.append(f'feaststore_request_latency_ms_bucket{{le="{le}"}} {cumulative}')
        cumulative += buckets[-1]
        lines.append(f'feaststore_request_latency_ms_bucket{{le="+Inf"}} {cumulative}')
        lines.append(f"feaststore_request_latency_ms_sum {latency_sum:.3f}")
        lines.append(f"feaststore_request_latency_ms_count {cumulative}")
        return "\n".join(lines) + "\n"
