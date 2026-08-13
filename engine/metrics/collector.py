import collections
import threading
import time
from django.conf import settings
from prometheus_client import Counter, Gauge, Histogram

# Retrieve local node ID dynamically from Django settings
try:
    NODE_ID = getattr(settings, 'SHARD_NODE_ID', 'Node-A')
except Exception:
    NODE_ID = 'Node-A'

# Declare Prometheus metrics globally
# Gauge for active keys currently in memory
shard_keys_total = Gauge(
    'shard_cache_keys_total',
    'Number of keys currently present in the cache',
    ['node']
)

# Counter for cache hits (labeled by node and eviction policy)
shard_hits_total = Counter(
    'shard_cache_hits_total',
    'Total number of cache hits',
    ['node', 'eviction_policy']
)

# Counter for cache misses
shard_misses_total = Counter(
    'shard_cache_misses_total',
    'Total number of cache misses',
    ['node']
)

# Counter for evictions (labeled by reason: 'policy' or 'ttl')
shard_evictions_total = Counter(
    'shard_cache_evictions_total',
    'Total number of cache evictions',
    ['node', 'reason']
)

# Histogram for request latency in milliseconds
shard_latency = Histogram(
    'shard_cache_latency_milliseconds',
    'Cache request latency in milliseconds',
    ['node', 'operation'],
    buckets=(0.1, 0.5, 1.0, 5.0, 10.0, 25.0, 50.0, 100.0, 250.0, 500.0, 1000.0)
)


class MetricsCollector:
    """
    Thread-safe collector wrapping Prometheus metric updates.
    """
    def __init__(self, node_id: str):
        self.node_id = node_id
        # Capped sliding window queue for client-side latency percentile calculations
        self.latency_history = collections.deque(maxlen=1000)
        self.latency_lock = threading.Lock()

    def record_hit(self, policy: str) -> None:
        shard_hits_total.labels(node=self.node_id, eviction_policy=policy).inc()

    def record_miss(self) -> None:
        shard_misses_total.labels(node=self.node_id).inc()

    def record_eviction(self, reason: str) -> None:
        shard_evictions_total.labels(node=self.node_id, reason=reason).inc()

    def record_latency(self, operation: str, duration_ms: float) -> None:
        shard_latency.labels(node=self.node_id, operation=operation).observe(duration_ms)
        # Store in rolling history for local JSON percentile calculations
        with self.latency_lock:
            self.latency_history.append(duration_ms)

    def set_keys_count(self, count: int) -> None:
        shard_keys_total.labels(node=self.node_id).set(count)

    def get_latency_percentiles(self) -> dict[str, float]:
        """
        Calculates and returns MAX, P50, P95, and P99 quantiles in milliseconds.
        """
        # Note: Summary quantiles calculated over a sliding window are not identical
        # to Cairn's decaying reservoir, which is documented here as a design difference.
        with self.latency_lock:
            history = sorted(list(self.latency_history))
            
        if not history:
            return {"MAX": 0.0, "P50": 0.0, "P95": 0.0, "P99": 0.0}
            
        n = len(history)
        def percentile(p: float) -> float:
            idx = int(p * (n - 1))
            return float(history[idx])
            
        return {
            "MAX": float(max(history)),
            "P50": percentile(0.50),
            "P95": percentile(0.95),
            "P99": percentile(0.99)
        }


# Global metrics collector instance
metrics_collector = MetricsCollector(NODE_ID)
